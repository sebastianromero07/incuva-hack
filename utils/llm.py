import os
import requests
import hashlib
from .rag_system import RAGSystemOpenAI
from .conversation_memory import conversation_memory
from .message_handlers import (
    is_greeting, is_user_correction_or_clarification, is_handoff_request,
    is_general_info_request, is_conversation_memory_query, should_use_conversation_context
)
from .response_message import (
    get_welcome_message, get_correction_response, get_handoff_message,
    get_general_info_response
)

# Inicializar RAG globalmente
rag = RAGSystemOpenAI()
rag.load_database()

# Cache OPTIMIZADO
response_cache = {}

def get_cache_key(user_text: str, chunks: list) -> str:
    """Crear clave de cache"""
    chunks_text = "".join(chunks[:1]) if chunks else ""
    content = f"{user_text[:80]}:{chunks_text[:150]}"
    return hashlib.md5(content.encode()).hexdigest()

def generate_reply(user_text: str, chat_id: str) -> str:
    """✅ IA INTELIGENTE que distingue entre consultas de memoria vs. base de datos"""
    
    print(f"⚡ Procesando: '{user_text[:25]}...' [Chat: {chat_id}]")
    
    # Agregar mensaje a memoria
    conversation_memory.add_message_to_memory(chat_id, user_text, is_user=True)
    
    # 1. PRIORIDAD MÁXIMA: Correcciones del usuario
    if is_user_correction_or_clarification(user_text):
        print("🔄 Corrección del usuario detectada")
        return get_correction_response()
    
    # 2. PRIORIDAD: Saludos
    if is_greeting(user_text):
        print("👋 Saludo detectado - mensaje del dashboard")
        return get_welcome_message()
    
    # 3. PRIORIDAD: Transferencia a agente humano
    if is_handoff_request(user_text):
        print("🔄 Transferencia detectada")
        conversation_memory.clear_chat_context(chat_id)
        return get_handoff_message()
    
    # 4. Consulta general de información
    if is_general_info_request(user_text):
        print("📋 Consulta general de información detectada")
        documents = rag.list_documents()
        return get_general_info_response(documents)
    
    # ✅ 5. NUEVO: Consulta sobre memoria de conversación
    if is_conversation_memory_query(user_text):
        print("🧠 Consulta sobre memoria de conversación detectada")
        return handle_conversation_memory_query(user_text, chat_id)
    
    # 6. Verificar documentos cargados
    if not rag.chunks:
        return """❌ Lo siento, actualmente no tengo información cargada.

Contacta al administrador para que agregue los documentos necesarios."""
    
    # ✅ 7. BÚSQUEDA INTELIGENTE - Determinar si usar contexto
    similar_chunks = rag.search_similar(user_text, k=5)
    
    # Determinar si debe usar contexto de conversación
    use_context = should_use_conversation_context(user_text)
    has_memory = conversation_memory.should_use_context(chat_id, user_text) if use_context else False
    
    # 8. Verificar cache
    cache_key = get_cache_key(user_text, similar_chunks)
    
    if cache_key in response_cache and not has_memory:
        print("⚡ CACHE HIT")
        return response_cache[cache_key]
    
    # ✅ 9. GENERAR RESPUESTA INTELIGENTE
    return generate_intelligent_response(user_text, chat_id, similar_chunks, has_memory, use_context)


def handle_conversation_memory_query(user_text: str, chat_id: str) -> str:
    """✅ COMPLETADO: Manejar consultas con mejor contexto histórico"""
    
    if chat_id in conversation_memory.chat_message_history:
        # ✅ AUMENTAR: Obtener más mensajes para mejor contexto
        recent_messages = conversation_memory.chat_message_history[chat_id][-12:]
        
        if recent_messages:
            # ✅ MEJORAR: Detectar qué nivel de "antes" pregunta
            user_lower = user_text.lower()
            
            user_questions = []
            for timestamp, message, _ in reversed(recent_messages):
                if 'usuario:' in message:
                    message_clean = message.replace('usuario:', '').strip()
                    if user_text.lower().strip() not in message_clean.lower():
                        user_questions.append(f"[{timestamp[:16]}] {message_clean}")
                        if len(user_questions) >= 5:  # Hasta 5 preguntas anteriores
                            break
            
            if user_questions:
                conversation_context = f"PREGUNTAS ANTERIORES DEL USUARIO (más reciente primero):\n"
                for i, question in enumerate(user_questions):
                    conversation_context += f"{i+1}. {question}\n"
            else:
                return "🤔 No encuentro preguntas anteriores recientes."
        else:
            return "🤔 No hay mensajes anteriores en la conversación."
    else:
        return "🤔 No hay historial de conversación."
    
    # ✅ COMPLETAR: Configurar OpenAI para consulta de memoria
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        return "❌ Error de configuración. Contacta al administrador."
    
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {openai_api_key}",
        "Content-Type": "application/json"
    }
    
    # ✅ PROMPT ESPECÍFICO PARA MEMORIA DE CONVERSACIÓN RECIENTE
    system_prompt = f"""Eres TOmi, asistente especializado. El usuario te está preguntando sobre SUS PREGUNTAS ANTERIORES en la conversación reciente.

CONTEXTO DE CONVERSACIÓN RECIENTE:
{conversation_context}

INSTRUCCIONES ESPECÍFICAS:
1. **NO repitas la pregunta del usuario en tu respuesta**
2. **Sé conciso y directo**
3. **Si pregunta "qué pregunté hace un momento" → menciona la pregunta #1 (más reciente)**
4. **Si pregunta "hace dos preguntas" → menciona la pregunta #2**
5. **Si pregunta "hace dos conversaciones" → menciona la pregunta #3**
6. **Responde solo sobre las preguntas que aparecen en el contexto reciente**
7. **Si no encuentra preguntas suficientes, dilo claramente**

El usuario quiere saber sobre sus preguntas ANTERIORES específicas."""
    
    current_message = f"""El usuario pregunta: "{user_text}"

Analiza las preguntas anteriores del contexto y responde de manera concisa sobre cuál fue su pregunta específica según lo que solicita."""
    
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": current_message}
        ],
        "temperature": 0.2,  # ✅ Muy baja para precisión
        "max_tokens": 200,   # ✅ Respuesta muy concisa
        "top_p": 0.9
    }
    
    # ✅ COMPLETAR: Llamada a OpenAI
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if "choices" in data and len(data["choices"]) > 0:
                reply = data["choices"][0]["message"]["content"].strip()
                
                # Agregar respuesta a memoria
                conversation_memory.add_message_to_memory(chat_id, reply, is_user=False)
                
                print(f"✅ Consulta de memoria reciente respondida: {len(reply)} chars")
                return reply
        else:
            print(f"❌ Error OpenAI: {response.status_code}")
            return "❌ No pude procesar tu consulta sobre la conversación anterior."
        
    except Exception as e:
        print(f"❌ Error en consulta de memoria: {e}")
        return "❌ Error procesando tu consulta sobre la conversación."

def generate_intelligent_response(user_text: str, chat_id: str, similar_chunks: list, has_memory: bool, use_context: bool) -> str:
    """✅ IA INTELIGENTE que evalúa relevancia y decide respuesta"""
    
    # Contexto de memoria
    conversation_context = ""
    if has_memory and use_context:
        conversation_context = conversation_memory.get_conversation_context(chat_id, user_text)
        print(f"🧠 Usando contexto de memoria vectorial")
    else:
        print("🆕 Nueva consulta independiente")
    
    # Configurar OpenAI
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        return "❌ Error de configuración. Contacta al administrador."
    
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {openai_api_key}",
        "Content-Type": "application/json"
    }
    
    # Contexto de documentos
    document_context = ""
    if similar_chunks:
        document_context = "INFORMACIÓN ENCONTRADA EN BASE DE DATOS:\n\n"
        for i, chunk in enumerate(similar_chunks[:5]):
            document_context += f"**Fuente {i+1}:** {chunk}\n\n"
    
    documents = rag.list_documents()
    available_docs = ', '.join(documents) if documents else 'Ninguno'
    
    # ✅ SISTEMA PROMPT MEJORADO - NO REPETIR PREGUNTAS
    system_prompt = f"""Eres TOmi, asistente especializado en procedimientos académicos universitarios.

REGLAS IMPORTANTES:
1. **NO repitas la pregunta del usuario en tu respuesta**
2. **Sé conciso y directo - ve al grano**
3. **Si encuentras información relevante, preséntala de manera clara y organizada**
4. **Si no hay información relevante, explica brevemente que no tienes esa información específica**
5. **Para temas externos (matemáticas, etc.), explica educadamente tu especialización**
6. **Evalúa inteligentemente cada consulta**

DOCUMENTOS DISPONIBLES: {available_docs}

{conversation_context}

Tu objetivo: Respuestas útiles, concisas y directas."""
    
    # Mensaje para OpenAI
    if conversation_context:
        current_message = f"""Consulta: "{user_text}"

{document_context}

Responde de manera concisa y directa. No repitas la pregunta. Considera el contexto de la conversación."""
    else:
        current_message = f"""Consulta: "{user_text}"

{document_context}

Evalúa la relevancia y responde de manera concisa y directa. No repitas la pregunta."""
    
    # Payload
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": current_message}
        ],
        "temperature": 0.3,  # ✅ Más precisión, menos creatividad
        "max_tokens": 400,   # ✅ Respuestas concisas
        "top_p": 0.9
    }
    
    # Llamada a OpenAI
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        
        if response.status_code == 200:
            data = response.json()
            if "choices" in data and len(data["choices"]) > 0:
                reply = data["choices"][0]["message"]["content"].strip()
                
                # Agregar respuesta a memoria
                conversation_memory.add_message_to_memory(chat_id, reply, is_user=False)
                
                # Guardar response_id
                response_id = data.get("id")
                if response_id:
                    conversation_memory.set_response_id(chat_id, response_id, user_text)
                    print(f"💭 Response ID: {response_id[:15]}...")
                
                print(f"✅ IA Inteligente: {len(reply)} chars")
                
                # Cache
                if not has_memory:
                    response_cache[get_cache_key(user_text, similar_chunks)] = reply
                    if len(response_cache) > 30:
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

# Funciones de utilidad existentes
def clear_chat_memory(chat_id: str):
    """Limpiar memoria de un chat"""
    conversation_memory.clear_chat_context(chat_id)
    global response_cache
    response_cache.clear()
    print(f"🗑️ Memoria limpiada para chat {chat_id}")

def get_memory_stats(chat_id: str):
    """Obtener estadísticas de memoria"""
    return conversation_memory.get_memory_stats(chat_id)

def setup_rag(pdf_folder: str = "data/pdfs"):
    """Configurar RAG"""
    global rag
    if os.path.exists(pdf_folder) and os.listdir(pdf_folder):
        rag.create_vector_database(pdf_folder)
        print("✅ RAG configurado correctamente")
    else:
        print(f"⚠️ No se encontraron PDFs en {pdf_folder}")

print("⚡ IA INTELIGENTE - Distingue Memoria vs Base de Datos")