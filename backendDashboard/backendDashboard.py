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
# DASHBOARD HTML
# =========================
@app.get("/dashboard", response_class=HTMLResponse)
async def home():
    return """
    <html>
    <head>
        <title>Dashboard Auditoría</title>
        <style>
            body { margin: 0; display: flex; justify-content: center; align-items: center; height: 100vh; background-color: #f4f6f8; font-family: Arial, sans-serif; }
            #container { text-align: center; width: 800px; }
            #drop-zone { border: 2px dashed #4a90e2; padding: 60px; border-radius: 12px; background: white; cursor: pointer; transition: 0.3s; margin: 0 auto 20px auto; width: 60%; }
            #drop-zone.dragover { background-color: #e3f2fd; }
            #response { text-align: left; background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); display: none; max-height: 500px; overflow-y: auto; white-space: pre-wrap; line-height: 1.5; }
            .loading { color: #4a90e2; font-weight: bold; }
        </style>
    </head>
    <body>
        <div id="container">
            <h2>Analizador de Conversaciones</h2>
            <div id="drop-zone">Arrastra tu archivo JSON de chats aquí</div>
            <div id="response"></div>
        </div>

        <script>
            const dropZone = document.getElementById("drop-zone");
            const responseDiv = document.getElementById("response");

            dropZone.addEventListener("dragover", (e) => {
                e.preventDefault();
                dropZone.classList.add("dragover");
            });

            dropZone.addEventListener("dragleave", () => {
                dropZone.classList.remove("dragover");
            });

            dropZone.addEventListener("drop", async (e) => {
                e.preventDefault();
                dropZone.classList.remove("dragover");

                const file = e.dataTransfer.files[0];
                if (!file) return;

                const formData = new FormData();
                formData.append("file", file);

                responseDiv.style.display = "block";
                responseDiv.innerHTML = "<p class='loading'>⏳ Filtrando chats y analizando con la IA...</p>";

                try {
                    const res = await fetch("/process-conversations", {
                        method: "POST",
                        body: formData
                    });

                    const data = await res.json();

                    if (res.ok) {
                        responseDiv.innerHTML = "<div>" + data.content + "</div>";
                    } else {
                        responseDiv.innerHTML = "<h3 style='color:red'>Error:</h3>" + (data.detail || "Error desconocido");
                    }
                } catch (err) {
                    responseDiv.innerHTML = "<h3>Error:</h3> No se pudo conectar con el servidor.";
                }
            });
        </script>
    </body>
    </html>
    """

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

        # 2. Recortamos a 15000 caracteres.
        resumen_datos = texto_limpio[:15000]

        if not resumen_datos.strip():
            raise HTTPException(status_code=400, detail="No se encontró texto de chat válido en el archivo. ¿Estás seguro de que es una exportación de chats?")

        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }

        # 3. Separamos los roles: El Sistema da la orden, el Usuario pasa el archivo
        mensaje_sistema = (
            "Eres un AUDITOR DE DATOS informático, no un profesor ni un asistente de chat. "
            "Tu única tarea es leer el historial de conversación adjunto y devolver un OBJETO JSON VÁLIDO "
            "con las métricas de auditoría (temas, dificultad, alertas, etc.). "
            "BAJO NINGÚN CONCEPTO debes continuar la conversación, ni responder a las preguntas del historial, "
            "ni dar saludos. Devuelve SOLO el código JSON."
        )

        mensaje_usuario = f"Analiza este historial y devuelve el JSON:\n\n<historial>\n{resumen_datos}\n</historial>"

        payload = {
            "model": MODEL_ID,
            "messages": [
                {"role": "system", "content": mensaje_sistema},
                {"role": "user", "content": mensaje_usuario}
            ],
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
        respuesta_ia = result["choices"][0]["message"]["content"].strip()

        return {"content": respuesta_ia.strip()}

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="El archivo no es un JSON válido")

    except Exception as e:
        print("❌ ERROR CRÍTICO:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))