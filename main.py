# CARGAR .env ANTES DE CUALQUIER IMPORT
from dotenv import load_dotenv
load_dotenv()

import requests
import os
import asyncio
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from utils.llm import generate_reply, get_welcome_message
from dashboard.routes import router as dashboard_router
from typing import Set

# Variables de entorno
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
PORT = int(os.getenv("PORT", 8000))

app = FastAPI(title="TOmi - RAG Bot Dashboard")

# Cache OPTIMIZADO para mensajes duplicados
processed_messages: Set[int] = set()

def cleanup_old_messages():
    """Limpieza OPTIMIZADA de mensajes"""
    global processed_messages
    if len(processed_messages) > 500:  # REDUCIDO de 1000 a 500
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
    print("🚀 Iniciando TOmi OPTIMIZADO...")
    
    if TELEGRAM_TOKEN and WEBHOOK_URL and WEBHOOK_URL != "https://tu-app.railway.app":
        try:
            webhook_endpoint = f"{WEBHOOK_URL}/webhook"
            webhook_response = requests.post(
                f"{TELEGRAM_API}/setWebhook",
                json={"url": webhook_endpoint},
                timeout=5  # REDUCIDO de 10 a 5
            )
            result = webhook_response.json()
            print(f"🔗 Webhook configurado: {result}")
            
        except Exception as e:
            print(f"⚠️ Error configurando webhook: {e}")
    else:
        print("⚠️ Webhook no configurado (desarrollo local)")

def send_telegram_message_background(chat_id: str, text: str, message_id: int):
    """Enviar mensaje en background para no bloquear"""
    try:
        response = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML"
            },
            timeout=10  # REDUCIDO de 15 a 10
        )
        print(f"📤 [{message_id}]: {response.status_code}")
    except Exception as e:
        print(f"❌ Error enviando mensaje: {e}")

@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    """Webhook OPTIMIZADO de Telegram"""
    try:
        data = await request.json()
        
        if "message" in data:
            message = data["message"]
            message_id = message.get("message_id")
            chat_id = str(message["chat"]["id"])
            user_text = message.get("text", "")
            
            # Deduplicación OPTIMIZADA
            if message_id in processed_messages:
                return {"status": "duplicated"}
            
            processed_messages.add(message_id)
            cleanup_old_messages()
            
            print(f"📩 [{message_id}] Chat-{chat_id}: {user_text[:50]}...")
            
            # IMPORTS LOCALES para velocidad inicial
            from dashboard.routes import get_bot_config
            from utils.llm import is_handoff_request, get_handoff_message
            
            bot_config = get_bot_config()
            
            if bot_config.get('status') != 'active':
                print("🔴 Bot inactivo")
                return {"status": "bot_inactive"}
            
            # GENERACIÓN OPTIMIZADA de respuesta
            if user_text.lower() in ["/start", "start", "hola", "hello", "hi", "inicio"]:
                bot_reply = get_welcome_message()
                print("👋 Mensaje de bienvenida (CACHE)")
                
            elif is_handoff_request(user_text):
                bot_reply = get_handoff_message()
                print("🔄 Mensaje de transferencia (CACHE)")
                
            else:
                # RESPUESTA PRINCIPAL - La más optimizada
                bot_reply = generate_reply(user_text, chat_id)
            
            # ENVÍO EN BACKGROUND - No bloquea la respuesta del webhook
            background_tasks.add_task(
                send_telegram_message_background,
                chat_id,
                bot_reply,
                message_id
            )
            
            # RESPUESTA INMEDIATA al webhook de Telegram
            return {"status": "ok"}
        
        return {"status": "no_message"}
        
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return {"status": "error", "error": str(e)}

@app.get("/health")
async def health():
    """Health check OPTIMIZADO"""
    try:
        from utils.llm import rag, response_cache
        from utils.conversation_memory import conversation_memory
        
        memory_stats = conversation_memory.get_stats()
        
        return {
            "status": "healthy",
            "webhook_url": WEBHOOK_URL,
            "documents": len(rag.list_documents()),
            "chunks": len([c for c in rag.chunks if c.strip()]),
            "telegram_configured": bool(TELEGRAM_TOKEN),
            "bot_mode": "optimized_strict_pdf_only",
            "memory_stats": memory_stats,
            "cache_entries": len(response_cache),
            "processed_messages": len(processed_messages)
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/clear-cache")
async def clear_cache():
    """Endpoint para limpiar cache manualmente"""
    try:
        from utils.llm import response_cache
        response_cache.clear()
        processed_messages.clear()
        return {"status": "cache_cleared"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    # CONFIGURACIÓN OPTIMIZADA de uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=PORT,
        access_log=False,  # Desactivar logs de acceso para velocidad
        workers=1  # Un solo worker para desarrollo
    )