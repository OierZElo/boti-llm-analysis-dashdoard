from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import json
import traceback
import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

# =========================
# CARGA DE VARIABLES .env
# =========================
BASE_DIR = Path(__file__).resolve().parent
env_path = find_dotenv(str(BASE_DIR / ".env"))
load_dotenv(env_path)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # React/Vite
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# CONFIGURACIÓN
# =========================
OPEN_WEBUI_BASE_URL = os.getenv("OPEN_WEBUI_BASE_URL")  # ej: http://localhost:3000
API_KEY = os.getenv("OPEN_WEBUI_API_KEY")
MODEL_ID = os.getenv("MODEL_ID")
PORT = int(os.getenv("PORT", 8000))

REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", 120.0))
PROCESS_POLL_INTERVAL = float(os.getenv("PROCESS_POLL_INTERVAL", 1.5))
PROCESS_POLL_MAX_TRIES = int(os.getenv("PROCESS_POLL_MAX_TRIES", 120))

# =========================
# VALIDACIÓN AL ARRANCAR
# =========================
missing_vars = []
if not OPEN_WEBUI_BASE_URL:
    missing_vars.append("OPEN_WEBUI_BASE_URL")
if not API_KEY:
    missing_vars.append("OPEN_WEBUI_API_KEY")
if not MODEL_ID:
    missing_vars.append("MODEL_ID")

if missing_vars:
    print("\n" + "=" * 60)
    print("❌ CONFIGURACIÓN INCOMPLETA")
    print("Faltan las siguientes variables en el .env:")
    for var in missing_vars:
        print(f" - {var}")
    print("=" * 60 + "\n")
    raise RuntimeError("Faltan variables de entorno obligatorias.")

OPEN_WEBUI_BASE_URL = OPEN_WEBUI_BASE_URL.rstrip("/")

FILES_UPLOAD_URL = f"{OPEN_WEBUI_BASE_URL}/api/v1/files/"
CHAT_COMPLETIONS_URL = f"{OPEN_WEBUI_BASE_URL}/api/chat/completions"

# =========================
# ENDPOINT DE SALUD
# =========================
@app.get("/health")
async def health():
    return {"status": "ok"}

# =========================
# HELPERS
# =========================
def build_headers():
    return {
        "Authorization": f"Bearer {API_KEY}"
    }


def extraer_texto_content(content):
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        partes = []
        for item in content:
            if isinstance(item, str) and item.strip():
                partes.append(item.strip())
            elif isinstance(item, dict):
                txt = item.get("text") or item.get("content") or item.get("value") or ""
                if isinstance(txt, str) and txt.strip():
                    partes.append(txt.strip())
        return "\n".join(partes).strip()

    if isinstance(content, dict):
        txt = content.get("text") or content.get("content") or content.get("value") or ""
        if isinstance(txt, str):
            return txt.strip()

    return ""


def ordenar_mensajes(mensajes):
    return sorted(
        mensajes,
        key=lambda x: (
            x.get("timestamp", 0) if x.get("timestamp") is not None else 0,
            x.get("create_time", 0) if x.get("create_time") is not None else 0,
            str(x.get("id", "")),
            str(x.get("role", "")),
        )
    )


def extraer_mensajes_de_chat(chat):
    mensajes = chat.get("messages", [])
    if isinstance(mensajes, list) and mensajes:
        return ordenar_mensajes(mensajes)

    mensajes_dict = chat.get("chat", {}).get("history", {}).get("messages", {})
    if isinstance(mensajes_dict, dict) and mensajes_dict:
        return ordenar_mensajes(list(mensajes_dict.values()))

    return []


def extraer_conversaciones_limpias(raw_data):
    chats_limpios = []

    if isinstance(raw_data, list):
        for i, chat in enumerate(raw_data, start=1):
            if not isinstance(chat, dict):
                continue

            titulo = chat.get("title", f"Chat {i}")
            mensajes = extraer_mensajes_de_chat(chat)

            dialogo = []
            for msg in mensajes:
                rol = msg.get("role")
                texto = extraer_texto_content(msg.get("content"))
                if rol and texto:
                    dialogo.append(f"[{str(rol).upper()}]: {texto}")

            if dialogo:
                texto_chat = f"--- {str(titulo).upper()} ---\n" + "\n".join(dialogo)
                chats_limpios.append(texto_chat)

    return "\n\n".join(chats_limpios)


def calcular_metricas_generales(raw_data):
    total_conversaciones = 0
    total_interacciones = 0

    if isinstance(raw_data, list):
        for chat in raw_data:
            if not isinstance(chat, dict):
                continue

            mensajes = extraer_mensajes_de_chat(chat)

            interacciones_validas = 0
            for msg in mensajes:
                rol = msg.get("role")
                texto = extraer_texto_content(msg.get("content"))
                if rol and texto:
                    interacciones_validas += 1

            if interacciones_validas > 0:
                total_conversaciones += 1
                total_interacciones += interacciones_validas

    promedio = 0
    if total_conversaciones > 0:
        promedio = round(total_interacciones / total_conversaciones, 2)

    return {
        "total_conversaciones_analizadas": total_conversaciones,
        "promedio_interacciones_por_chat": promedio
    }


def intentar_parsear_json(texto):
    texto = texto.strip()

    try:
        data = json.loads(texto)
        if not isinstance(data, dict):
            raise ValueError("La respuesta JSON no es un objeto")
        return data
    except Exception:
        pass

    first = texto.find("{")
    last = texto.rfind("}")
    if first != -1 and last != -1 and last > first:
        candidate = texto[first:last + 1]
        data = json.loads(candidate)
        if not isinstance(data, dict):
            raise ValueError("La respuesta JSON rescatada no es un objeto")
        return data

    raise ValueError("No se pudo parsear la respuesta como JSON")

# =========================
# OPEN WEBUI FILES
# =========================
async def subir_archivo_temporal(client: httpx.AsyncClient, filename: str, contenido: str):
    files = {
        "file": (filename, contenido.encode("utf-8"), "text/plain")
    }

    response = await client.post(
        FILES_UPLOAD_URL,
        params={
            "process": "true",
            "process_in_background": "true"
        },
        files=files,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Accept": "application/json"
        }
    )

    if response.status_code not in (200, 201):
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Error subiendo archivo: {response.text}"
        )

    data = response.json()
    file_id = data.get("id")

    if not file_id:
        raise HTTPException(
            status_code=500,
            detail=f"No se pudo obtener file_id. Respuesta: {data}"
        )

    return file_id


async def esperar_archivo_procesado(client: httpx.AsyncClient, file_id: str):
    url = f"{OPEN_WEBUI_BASE_URL}/api/v1/files/{file_id}/process/status"

    for _ in range(PROCESS_POLL_MAX_TRIES):
        response = await client.get(url, headers=build_headers())

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Error consultando estado del archivo: {response.text}"
            )

        data = response.json()

        status = (
            data.get("status")
            or data.get("state")
            or data.get("data", {}).get("status")
            or data.get("data", {}).get("state")
        )

        if isinstance(status, str):
            s = status.lower()
            if s in ("processed", "completed", "done", "success", "finished"):
                return
            if s in ("failed", "error"):
                raise HTTPException(
                    status_code=500,
                    detail=f"El procesado del archivo falló: {data}"
                )

        if data.get("processed") is True or data.get("done") is True:
            return

        await asyncio.sleep(PROCESS_POLL_INTERVAL)

    raise HTTPException(
        status_code=504,
        detail="Timeout esperando a que Open WebUI procese el archivo"
    )


async def borrar_archivo_temporal(client: httpx.AsyncClient, file_id: str):
    url = f"{OPEN_WEBUI_BASE_URL}/api/v1/files/{file_id}"
    response = await client.delete(url, headers=build_headers())

    # Si falla el borrado no rompemos el análisis principal
    if response.status_code not in (200, 202, 204):
        print(f"⚠ No se pudo borrar el archivo temporal {file_id}: {response.text}")


async def analizar_con_archivo(client: httpx.AsyncClient, file_id: str):
    mensaje_sistema = (
        "Actúa como un Analista de Datos Educativos. "
        "Tu tarea es analizar un historial de conversaciones entre estudiantes y un asistente virtual. "
        "Debes devolver ESTRICTAMENTE un JSON válido. "
        "NO incluyas saludos, explicaciones, ni markdown. "
        "La respuesta debe ser únicamente un objeto JSON parseable. "
        "NO calcules 'metricas_generales'. "
        "Devuelve igualmente la clave 'metricas_generales', pero con este contenido exacto:\n"
        '{'
        '"total_conversaciones_analizadas": 0,'
        '"promedio_interacciones_por_chat": 0'
        '}'
    )

    mensaje_usuario = (
        "Analiza el archivo adjunto completo y devuelve el JSON con la estructura esperada. "
        "Recuerda: no calcules las metricas_generales reales; deja esos dos valores a 0 "
        "porque se sustituirán en backend."
    )

    payload = {
        "model": MODEL_ID,
        "messages": [
            {"role": "system", "content": mensaje_sistema},
            {"role": "user", "content": mensaje_usuario}
        ],
        "files": [
            {"type": "file", "id": file_id}
        ],
        "stream": False,
        "temperature": 0.0,
        "top_p": 1
    }

    response = await client.post(
        CHAT_COMPLETIONS_URL,
        json=payload,
        headers={**build_headers(), "Content-Type": "application/json"},
        timeout=REQUEST_TIMEOUT
    )

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Error del servidor de IA: {response.text}"
        )

    result = response.json()

    try:
        return result["choices"][0]["message"]["content"].strip()
    except Exception:
        raise HTTPException(
            status_code=500,
            detail=f"Respuesta inesperada del backend: {result}"
        )

# =========================
# PROCESAMIENTO DEL JSON
# =========================
@app.post("/process-conversations")
async def process_json(file: UploadFile = File(...)):
    print(f"\nArchivo recibido: {file.filename}")

    file_id = None

    try:
        contents = await file.read()
        raw_data = json.loads(contents)

        # 1. Métricas exactas en Python
        metricas_generales = calcular_metricas_generales(raw_data)

        # 2. Convertimos el JSON exportado a texto legible
        texto_limpio = extraer_conversaciones_limpias(raw_data)

        if not texto_limpio.strip():
            raise HTTPException(
                status_code=400,
                detail="No se encontró texto de chat válido en el archivo. ¿Estás seguro de que es una exportación de chats?"
            )

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            # 3. Subimos archivo temporal
            file_id = await subir_archivo_temporal(
                client,
                filename="conversaciones.txt",
                contenido=texto_limpio
            )

            # 4. Esperamos a que termine el procesado asíncrono
            await esperar_archivo_procesado(client, file_id)

            # 5. Analizamos usando el file_id como adjunto
            respuesta_ia = await analizar_con_archivo(client, file_id)

            # 6. Borramos el archivo al acabar
            await borrar_archivo_temporal(client, file_id)
            file_id = None

        # 7. Parseamos respuesta y metemos las métricas de Python
        respuesta_json = intentar_parsear_json(respuesta_ia)
        respuesta_json["metricas_generales"] = metricas_generales

        return {
            "content": json.dumps(respuesta_json, ensure_ascii=False)
        }

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="El archivo no es un JSON válido")

    except HTTPException:
        raise

    except Exception as e:
        print("❌ ERROR CRÍTICO:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # Limpieza de seguridad si algo falla a mitad
        if file_id:
            try:
                async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                    await borrar_archivo_temporal(client, file_id)
            except Exception as cleanup_error:
                print(f"⚠ Error limpiando archivo temporal {file_id}: {cleanup_error}")