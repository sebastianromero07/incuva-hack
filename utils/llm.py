import os
import requests
import hashlib
from functools import lru_cache
from .rag_system import RAGSystem
from .conversation_memory import conversation_memory

# Inicializar RAG globalmente
rag = RAGSystem()
rag.load_database()

# Cache OPTIMIZADO para respuestas frecuentes
response_cache = {}

def get_cache_key(user_text: str, chunks: list) -> str:
    """Crear clave de cache OPTIMIZADA"""
    chunks_text = "".join(chunks[:1]) if chunks else ""
    content = f"{user_text[:80]}:{chunks_text[:150]}"
    return hashlib.md5(content.encode()).hexdigest()

@lru_cache(maxsize=100)
def get_welcome_message() -> str:
    """Obtener mensaje de bienvenida (CACHED)"""
    try:
        from dashboard.routes import get_bot_config
        bot_config = get_bot_config()
        return bot_config.get("welcome_message", get_default_welcome_message())
    except Exception as e:
        return get_default_welcome_message()

def get_default_welcome_message() -> str:
    return """👋 ¡Hola! Soy TOmi, tu asistente virtual de soporte técnico.

Estoy aquí para ayudarte con información específica de nuestra documentación técnica. 

¿En qué puedo ayudarte hoy?"""

@lru_cache(maxsize=100)
def get_handoff_message() -> str:
    """Obtener mensaje de transferencia (CACHED)"""
    try:
        from dashboard.routes import get_bot_config
        bot_config = get_bot_config()
        return bot_config.get("handoff_message", """🔄 Te voy a transferir con un agente humano que podrá ayudarte mejor.

Un momento por favor...""")
    except Exception:
        return "🔄 Transfiriendo a agente humano..."

def is_handoff_request(user_text: str) -> bool:
    """Detectar solicitud de agente humano (SÚPER OPTIMIZADO)"""
    user_lower = user_text.lower()
    
    # Solo palabras más comunes para salida temprana
    if any(word in user_lower for word in ["agente", "persona", "humano", "transferir"]):
        return True
    
    return False

def is_greeting(user_text: str) -> bool:
    """Detectar si es un saludo simple"""
    user_lower = user_text.lower().strip()
    greetings = ["hola", "hello", "hi", "buenas", "saludos", "hey"]
    
    # Solo saludos MUY simples (1 palabra)
    if len(user_text.split()) == 1 and any(greeting in user_lower for greeting in greetings):
        return True
    
    return False

def generate_reply(user_text: str, chat_id: str) -> str:
    """Genera respuesta SÚPER OPTIMIZADA usando OpenAI oficial"""
    
    print(f"⚡ Procesando: '{user_text[:25]}...' [Chat: {chat_id}]")
    
    # 1. PRIORIDAD: Solo saludos de UNA palabra
    if is_greeting(user_text):
        print("👋 Saludo simple detectado - respuesta rápida")
        return get_welcome_message()
    
    # 2. PRIORIDAD: Verificar solicitud de agente humano (RÁPIDO)
    if is_handoff_request(user_text):
        print("🔄 Transferencia detectada")
        conversation_memory.clear_chat_context(chat_id)
        return get_handoff_message()
    
    # 3. Verificar documentos cargados (RÁPIDO)
    if not rag.chunks:
        return """❌ Lo siento, actualmente no tengo información técnica cargada en mi sistema.

Por favor, contacta con el administrador para que agregue los documentos necesarios."""
    
    # 4. Buscar información SÚPER OPTIMIZADA
    similar_chunks = rag.search_similar(user_text, k=1)  # REDUCIDO a solo 1 chunk
    
    # 5. VERIFICAR CACHE SÚPER RÁPIDO
    cache_key = get_cache_key(user_text, similar_chunks)
    if cache_key in response_cache:
        print("⚡ CACHE HIT - RESPUESTA INSTANTÁNEA")
        return response_cache[cache_key]
    
    # 6. DETERMINAR SI USAR CONTEXTO (INTELIGENTE MEJORADO)
    use_context = conversation_memory.should_use_context(chat_id, user_text)
    
    # 7. Configurar OpenAI oficial
    openai_api_key = os.getenv("OPENAI_API_KEY")
    
    if not openai_api_key:
        return "❌ Error de configuración de OpenAI. Contacta al administrador."
    
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {openai_api_key}",
        "Content-Type": "application/json"
    }
    
    # 8. Contexto SÚPER OPTIMIZADO
    context = f"Documentación disponible:\n{similar_chunks[0]}" if similar_chunks else "Sin documentación relevante encontrada."
    documents = rag.list_documents()
    
    # 9. Sistema prompt SÚPER CONCISO - QUE LA IA ANALICE TODO
    system_prompt = f"""Eres TOmi, asistente técnico inteligente.

REGLAS:
- Analiza la consulta del usuario y responde de la mejor manera
- Si tienes información en los documentos, úsala
- Si no tienes información específica, dilo claramente
- Si te preguntan qué información tienes, lista los documentos disponibles
- Si te saludan con más de una palabra, responde naturalmente
- Sé conciso y útil
- Responde en español

DOCUMENTOS DISPONIBLES: {', '.join(documents) if documents else 'Ninguno'}

Responde de manera inteligente y natural."""
    
    # 10. Mensaje OPTIMIZADO
    current_message = f"Usuario: {user_text}\n\n{context}"
    
    # 11. Payload SÚPER OPTIMIZADO
    payload = {
        "model": "gpt-4o-mini",  # Modelo más rápido
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": current_message}
        ],
        "temperature": 0.1,
        "max_tokens": 200,  # AUMENTADO un poco para respuestas más completas
        "top_p": 0.9
    }
    
    # 12. CLAVE: Solo usar previous_response_id si hay continuidad Y si está disponible
    if use_context:
        previous_response_id = conversation_memory.get_previous_response_id(chat_id)
        if previous_response_id:
            # TEMPORALMENTE DESHABILITADO hasta que OpenAI lo active
            # payload["previous_response_id"] = previous_response_id
            print(f"🔗 Contexto disponible: {previous_response_id[:15]}... (pero deshabilitado)")
    
    try:
        # 13. Request SÚPER OPTIMIZADO
        response = requests.post(url, headers=headers, json=payload, timeout=8)
        
        if response.status_code == 200:
            data = response.json()
            if "choices" in data and len(data["choices"]) > 0:
                reply = data["choices"][0]["message"]["content"].strip()
                
                # 14. Guardar response_id para futura implementación
                response_id = data.get("id")
                if response_id:
                    conversation_memory.set_response_id(chat_id, response_id, user_text)
                
                print(f"✅ OpenAI: {len(reply)} chars")
                
                # 15. CACHE OPTIMIZADO
                response_cache[cache_key] = reply
                if len(response_cache) > 30:
                    # Mantener solo los 15 más recientes
                    items = list(response_cache.items())
                    response_cache.clear()
                    response_cache.update(dict(items[-15:]))
                
                return reply
        else:
            print(f"❌ OpenAI error: {response.status_code}")            
            return "Disculpa, tengo problemas técnicos temporales. Inténtalo de nuevo."
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return "Error de conectividad. Por favor, inténtalo nuevamente."

def clear_chat_memory(chat_id: str):
    """Limpiar memoria de un chat específico"""
    conversation_memory.clear_chat_context(chat_id)
    global response_cache
    response_cache.clear()
    print(f"🗑️ Memoria y cache limpiados para chat {chat_id}")

def setup_rag(pdf_folder: str = "data/pdfs"):
    """Función para configurar RAG"""
    global rag
    if os.path.exists(pdf_folder) and os.listdir(pdf_folder):
        rag.create_vector_database(pdf_folder)
        print("✅ RAG configurado correctamente")
    else:
        print(f"⚠️ No se encontraron PDFs en {pdf_folder}")

print("⚡ Sistema RAG SÚPER OPTIMIZADO - OpenAI + Contexto Inteligente + Cache")