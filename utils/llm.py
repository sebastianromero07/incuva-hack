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
    """Genera respuesta usando Groq + RAG simple"""
    
    print(f"🤖 Procesando: '{user_text[:50]}...'")
    
    # Buscar en documentos técnicos
    context = ""
    context_info = ""
    
    if rag.chunks:
        similar_chunks = rag.search_similar(user_text, k=3)
        if similar_chunks:
            context = "\n\nContexto técnico:\n" + "\n".join(similar_chunks[:2])
            context_info = f"📚 Contexto: {len(similar_chunks)} chunks de {len(rag.list_documents())} documentos"
            print(context_info)
    
    api_key = os.getenv("GROQ_API_KEY")
    
    if not api_key:
        return "❌ Error de configuración. Contacta al administrador."
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Prompt mejorado
    documents = rag.list_documents()
    doc_info = f"\n\nTienes acceso a estos documentos: {', '.join(documents)}" if documents else ""
    
    system_prompt = f"""Eres TOmi, un asistente virtual de soporte técnico amigable y eficiente.
    
    PERSONALIDAD:
    - Eres amigable, profesional y servicial
    - Hablas en español de manera natural y cercana
    - Siempre intentas ser útil y resolver problemas
    
    INSTRUCCIONES:
    - Si tienes contexto técnico específico, úsalo para dar respuestas detalladas y precisas
    - Si no tienes información específica, ofrece ayuda general pero útil
    - Mantén las respuestas claras y bien estructuradas
    - Usa emojis ocasionalmente para ser más amigable (pero sin exagerar)
    - Si la consulta es muy específica y no tienes información, sugiere alternativas o contactar soporte especializado{doc_info}"""
    
    user_message = user_text + context
    
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.4,
        "max_tokens": 400
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if "choices" in data and len(data["choices"]) > 0:
                reply = data["choices"][0]["message"]["content"].strip()
                print(f"✅ Respuesta generada: {len(reply)} caracteres")
                return reply
        else:
            print(f"❌ Groq error: {response.status_code}")
            return "Disculpa, tengo problemas técnicos en este momento 😅. Inténtalo de nuevo en unos momentos."
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return "Parece que hay un problema de conectividad 🔌. Inténtalo nuevamente por favor."
    
    return "🤖 No pude procesar tu consulta. ¿Podrías reformularla de otra manera?"

def setup_rag(pdf_folder: str = "data/pdfs"):
    """Función para configurar RAG - ejecutar una vez"""
    global rag
    if os.path.exists(pdf_folder) and os.listdir(pdf_folder):
        rag.create_vector_database(pdf_folder)
        print("✅ RAG configurado correctamente")
    else:
        print(f"⚠️ No se encontraron PDFs en {pdf_folder}")

print("🚀 Sistema usando Groq API + RAG Simple (sin sentence-transformers)")