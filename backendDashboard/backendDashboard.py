from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
import httpx
import json
import traceback
import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
from fastapi.middleware.cors import CORSMiddleware

# =========================
# CARGA DE VARIABLES .env
# =========================
BASE_DIR = Path(__file__).resolve().parent
env_path = find_dotenv(str(BASE_DIR / ".env"))
load_dotenv(env_path)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# CONFIGURACIÓN
# =========================
OPEN_WEBUI_URL = os.getenv("OPEN_WEBUI_URL")  
API_KEY = os.getenv("OPEN_WEBUI_API_KEY")
MODEL_ID = os.getenv("MODEL_ID")
PORT = int(os.getenv("PORT", 8000))

# =========================
# VALIDACIÓN AL ARRANCAR
# =========================
missing_vars = []
if not OPEN_WEBUI_URL: missing_vars.append("OPEN_WEBUI_URL")
if not API_KEY: missing_vars.append("OPEN_WEBUI_API_KEY")
if not MODEL_ID: missing_vars.append("MODEL_ID")

if missing_vars:
    print("\n" + "=" * 60)
    print("❌ CONFIGURACIÓN INCOMPLETA")
    print("Faltan las siguientes variables en el .env:")
    for var in missing_vars:
        print(f" - {var}")
    print("=" * 60 + "\n")
    raise RuntimeError("Faltan variables de entorno obligatorias.")

# =========================
# FILTRO: EXTRACCIÓN LIMPIA
# =========================
def extraer_conversaciones_limpias(raw_data):
    chats_limpios = []
    
    if isinstance(raw_data, list):
        for chat in raw_data:
            titulo = chat.get("title", "Chat sin título")
            
            # Formato nuevo: messages directamente en el chat
            mensajes = chat.get("messages", [])
            
            # Formato antiguo: chat.history.messages (dict)
            if not mensajes:
                mensajes_dict = chat.get("chat", {}).get("history", {}).get("messages", {})
                mensajes = list(mensajes_dict.values())
                mensajes.sort(key=lambda x: x.get("timestamp", 0))
            
            dialogo = []
            for msg in mensajes:
                rol = msg.get("role")
                texto = msg.get("content")
                if rol and texto and isinstance(texto, str):
                    dialogo.append(f"[{rol.upper()}]: {texto}")
            
            if dialogo:
                texto_chat = f"--- {titulo.upper()} ---\n" + "\n".join(dialogo)
                chats_limpios.append(texto_chat)
                
    return "\n\n".join(chats_limpios)

# =========================
# PROCESAMIENTO DEL JSON
# =========================
@app.post("/process-conversations")
async def process_json(file: UploadFile = File(...)):
    print(f"\nArchivo recibido: {file.filename}")

    try:
        contents = await file.read()
        raw_data = json.loads(contents)

        # 1. Filtramos la "basura" y nos quedamos solo con los guiones de chat
        texto_limpio = extraer_conversaciones_limpias(raw_data)

        # 2. Recortamos a 15000 caracteres. Como ahora el texto es puro, 
        # caben muchísimas más conversaciones reales antes de llegar al límite.
        resumen_datos = texto_limpio[:15000]

        if not resumen_datos.strip():
            raise HTTPException(status_code=400, detail="No se encontró texto de chat válido en el archivo. ¿Estás seguro de que es una exportación de chats?")

        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }

        # 3. Enviamos el texto limpio, sin prompts extra (el Agente usa el suyo)
        payload = {
            "model": MODEL_ID,
            "messages": [{"role": "user", "content": resumen_datos}],
            "stream": False,
            "temperature": 0.1
        }

        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.post(
                OPEN_WEBUI_URL,
                json=payload,
                headers=headers
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Error del servidor de IA: {response.text}"
            )

        result = response.json()
        respuesta_ia = result["choices"][0]["message"]["content"]

        return {"content": respuesta_ia}

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="El archivo no es un JSON válido")

    except Exception as e:
        print("❌ ERROR CRÍTICO:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))