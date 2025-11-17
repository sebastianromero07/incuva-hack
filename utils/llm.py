import os
import requests
from .rag_system import RAGSystem

# Inicializar RAG globalmente
rag = RAGSystem()
rag.load_database()  # Cargar si ya existe

def get_welcome_message() -> str:
    """Obtener mensaje de bienvenida desde configuración del dashboard"""
    try:
        from dashboard.routes import get_bot_config
        bot_config = get_bot_config()
        return bot_config.get("welcome_message", get_default_welcome_message())
    except Exception as e:
        print(f"⚠️ Error obteniendo config: {e}")
        return get_default_welcome_message()

def get_default_welcome_message() -> str:
    """Mensaje de bienvenida por defecto"""
    return """👋 ¡Hola! Soy TOmi, tu asistente virtual de soporte técnico.

Estoy aquí para ayudarte con información específica de nuestra documentación técnica. 

¿En qué puedo ayudarte hoy?"""

def get_handoff_message() -> str:
    """Obtener mensaje de transferencia desde configuración"""
    try:
        from dashboard.routes import get_bot_config
        bot_config = get_bot_config()
        return bot_config.get("handoff_message", """🔄 Te voy a transferir con un agente humano que podrá ayudarte mejor.

Un momento por favor...""")
    except Exception as e:
        print(f"⚠️ Error obteniendo handoff config: {e}")
        return "🔄 Transfiriendo a agente humano..."

def is_handoff_request(user_text: str) -> bool:
    """Detectar si el usuario solicita un agente humano"""
    user_text_lower = user_text.lower()
    
    # Palabras clave que indican solicitud de agente humano
    handoff_keywords = [
        "agente humano", "persona real", "agente real", "hablar con persona",
        "contactar persona", "operador", "representante", "agente",
        "persona", "humano", "real", "contacto humano",
        "quiero hablar con", "necesito hablar con", "comunicarme con",
        "transferir", "derivar", "escalar", "supervisor",
        "no puedes ayudarme", "no me ayudas", "no entiendes",
        "atención al cliente", "servicio al cliente", "soporte humano"
    ]
    
    # Verificar si alguna palabra clave está presente
    for keyword in handoff_keywords:
        if keyword in user_text_lower:
            return True
    
    # Patrones más específicos
    patterns = [
        "quiero contactarme con",
        "necesito hablar con",
        "puedes conectarme con",
        "derivame a",
        "transferirme a"
    ]
    
    for pattern in patterns:
        if pattern in user_text_lower:
            return True
    
    return False

def generate_reply(user_text: str) -> str:
    """Genera respuesta SOLO basada en PDFs cargados o transferencia"""
    
    print(f"🤖 Procesando: '{user_text[:50]}...'")
    
    # 1. PRIORIDAD: Verificar solicitud de agente humano
    if is_handoff_request(user_text):
        print("🔄 Solicitud de transferencia detectada")
        return get_handoff_message()
    
    # 2. Verificar si hay documentos cargados
    if not rag.chunks:
        return """❌ Lo siento, actualmente no tengo esa información cargada en mi sistema.

Por favor, contacta con el administrador para que agregue los archivos necesarios."""
    
    # 3. Buscar información relevante en los PDFs
    similar_chunks = rag.search_similar(user_text, k=3)
    
    # 4. Verificar si encontramos información relevante
    if not similar_chunks:
        return """📚 Lo siento, no encontré información sobre tu consulta en mi base de datos.
¿Podrías reformular tu pregunta o consultar sobre algún tema específico de nuestra documentación?

Si necesitas ayuda adicional, puedes solicitar hablar con un agente humano."""
    
    # 5. Construir contexto con la información encontrada
    context = "\n\nInformación de la documentación:\n" + "\n---\n".join(similar_chunks)
    
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "❌ Error de configuración del sistema. Contacta al administrador."
    
    # 6. Prompt ESTRICTO para responder solo con info de PDFs
    documents = rag.list_documents()
    system_prompt = f"""Eres TOmi, un asistente de soporte técnico ESPECIALIZADO.

REGLAS ESTRICTAS:
- SOLO puedes responder usando la información de los documentos proporcionados
- Si la información no está en los documentos, debes decir que NO la tienes
- NO inventes información que no esté en los documentos
- NO uses conocimiento general, SOLO lo que está en los documentos
- Sé conciso y directo
- Responde en español
- Al final de respuestas complejas, sugiere que pueden solicitar un agente humano si necesitan más ayuda

DOCUMENTOS DISPONIBLES: {', '.join(documents)}

Si no puedes responder con la información de los documentos, di: "Esta información no está disponible en mi base de datos de documentación técnica. Si necesitas ayuda adicional, puedes solicitar hablar con un agente humano."
"""
    
    user_message = f"Consulta del usuario: {user_text}\n{context}"
    
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.1,    # Muy determinístico para ser preciso
        "max_tokens": 200      # Respuestas concisas
    }
    
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if "choices" in data and len(data["choices"]) > 0:
                reply = data["choices"][0]["message"]["content"].strip()
                print(f"✅ Respuesta basada en docs: {len(reply)} chars")
                return reply
        
        return "Disculpa, tengo problemas técnicos temporales. Inténtalo de nuevo."
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return "Error de conectividad. Por favor, inténtalo nuevamente."

def setup_rag(pdf_folder: str = "data/pdfs"):
    """Función para configurar RAG - ejecutar una vez"""
    global rag
    if os.path.exists(pdf_folder) and os.listdir(pdf_folder):
        rag.create_vector_database(pdf_folder)
        print("✅ RAG configurado correctamente")
    else:
        print(f"⚠️ No se encontraron PDFs en {pdf_folder}")

print("🚀 Sistema RAG ESTRICTO - Solo responde con info de PDFs + Transferencia")