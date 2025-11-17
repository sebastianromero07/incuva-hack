# CARGAR .env ANTES DE CUALQUIER IMPORT
from dotenv import load_dotenv
load_dotenv()

import requests
import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from utils.llm import generate_reply, get_welcome_message
from dashboard.routes import router as dashboard_router
from typing import Set

# Variables de entorno
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://tu-app.railway.app")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
PORT = int(os.getenv("PORT", 8000))

app = FastAPI(title="TOmi - RAG Bot Dashboard")

# Cache para mensajes duplicados
processed_messages: Set[int] = set()

def cleanup_old_messages():
    global processed_messages
    if len(processed_messages) > 1000:
        processed_messages.clear()

# Incluir rutas del dashboard
app.include_router(dashboard_router)

# Servir archivos estáticos
try:
    app.mount("/static", StaticFiles(directory="templates/static"), name="static")
    print("✅ Archivos estáticos configurados")
except Exception as e:
    print(f"⚠️ Error configurando archivos estáticos: {e}")

@app.on_event("startup")
async def startup_event():
    """Configurar webhook automáticamente"""
    print("🚀 Iniciando TOmi...")
    
    if TELEGRAM_TOKEN and WEBHOOK_URL and WEBHOOK_URL != "https://tu-app.railway.app":
        try:
            webhook_endpoint = f"{WEBHOOK_URL}/webhook"
            webhook_response = requests.post(
                f"{TELEGRAM_API}/setWebhook",
                json={"url": webhook_endpoint},
                timeout=10
            )
            result = webhook_response.json()
            print(f"🔗 Webhook configurado: {result}")
            
        except Exception as e:
            print(f"⚠️ Error configurando webhook: {e}")
    else:
        print("⚠️ Webhook no configurado (desarrollo local)")

# ...existing code...

@app.post("/webhook")
async def webhook(request: Request):
    """Webhook de Telegram - PÚBLICO"""
    try:
        data = await request.json()
        
        if "message" in data:
            message = data["message"]
            message_id = message.get("message_id")
            chat_id = message["chat"]["id"]
            user_text = message.get("text", "")
            
            # Deduplicación
            if message_id in processed_messages:
                return {"status": "duplicated"}
            
            processed_messages.add(message_id)
            cleanup_old_messages()
            
            print(f"📩 [{message_id}]: {user_text}")
            
            # Verificar bot activo
            from dashboard.routes import get_bot_config
            from utils.llm import is_handoff_request, get_handoff_message
            
            bot_config = get_bot_config()
            
            if bot_config.get('status') != 'active':
                print("🔴 Bot inactivo")
                return {"status": "bot_inactive"}
            
            # Generar respuesta basada en el tipo de mensaje
            if user_text.lower() in ["/start", "start", "hola", "hello", "hi", "inicio"]:
                # Usar mensaje de bienvenida del dashboard
                bot_reply = get_welcome_message()
                print("👋 Enviando mensaje de bienvenida (desde config)")
                
            elif is_handoff_request(user_text):
                # Transferencia a agente humano
                bot_reply = get_handoff_message()
                print("🔄 Enviando mensaje de transferencia (desde config)")
                
            else:
                # Generar respuesta estricta basada en PDFs
                bot_reply = generate_reply(user_text)
            
            # Enviar respuesta
            send_response = requests.post(
                f"{TELEGRAM_API}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": bot_reply,
                    "parse_mode": "HTML"  # Para formateo básico
                },
                timeout=15
            )
            
            print(f"📤 [{message_id}]: {send_response.status_code}")
        
        return {"status": "ok"}
        
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return {"status": "error"}

# ...existing code...
@app.get("/health")
async def health():
    """Health check - PÚBLICO"""
    try:
        from utils.llm import rag
        return {
            "status": "healthy",
            "webhook_url": WEBHOOK_URL,
            "documents": len(rag.list_documents()),
            "chunks": len([c for c in rag.chunks if c.strip()]),
            "telegram_configured": bool(TELEGRAM_TOKEN),
            "bot_mode": "strict_pdf_only"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)