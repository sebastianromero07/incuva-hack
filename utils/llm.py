import os
import requests
from .rag_system import RAGSystem

# Inicializar RAG globalmente
rag = RAGSystem()
rag.load_database()  # Cargar si ya existe

def get_welcome_message() -> str:
    """Mensaje de bienvenida del bot"""
    from dashboard.routes import get_bot_config
    bot_config = get_bot_config()
    return bot_config.get("welcome_message", """👋 ¡Hola soy TOmi! Tu asistente virtual de soporte técnico.
Estoy aquí para ayudarte con cualquier duda o problema que tengas.

Cuéntame qué necesitas y te ayudaré al instante.""")

def generate_reply(user_text: str) -> str:
    """Genera respuesta rápida usando Groq + RAG simple"""
    
    print(f"🤖 Procesando: '{user_text[:50]}...'")
    
    # Buscar contexto MÁS RÁPIDO (solo 2 chunks)
    context = ""
    if rag.chunks:
        similar_chunks = rag.search_similar(user_text, k=2)  # Reducir de 3 a 2
        if similar_chunks:
            context = "\n\nContexto: " + similar_chunks[0][:200]  # Solo primer chunk, truncado
    
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "❌ Error de configuración."
    
    # Prompt MÁS CORTO para respuesta rápida
    system_prompt = """Eres TOmi, asistente de soporte técnico. 
    Responde de forma concisa y útil en español. Máximo 3 párrafos."""
    
    user_message = user_text + context
    
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.3,    # Más determinístico = más rápido
        "max_tokens": 150      # Respuestas más cortas = más rápidas
    }
    
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=8  # Timeout más corto
        )
        
        if response.status_code == 200:
            data = response.json()
            if "choices" in data and len(data["choices"]) > 0:
                reply = data["choices"][0]["message"]["content"].strip()
                print(f"✅ Respuesta: {len(reply)} chars")
                return reply
        
        return "Tengo problemas técnicos 😅 Inténtalo nuevamente."
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return "Error de conectividad 🔌 Inténtalo de nuevo."
    
def setup_rag(pdf_folder: str = "data/pdfs"):
    """Función para configurar RAG - ejecutar una vez"""
    global rag
    if os.path.exists(pdf_folder) and os.listdir(pdf_folder):
        rag.create_vector_database(pdf_folder)
        print("✅ RAG configurado correctamente")
    else:
        print(f"⚠️ No se encontraron PDFs en {pdf_folder}")

print("🚀 Sistema usando Groq API + RAG Simple (sin sentence-transformers)")