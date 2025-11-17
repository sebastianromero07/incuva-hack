import os
import requests
import hashlib
from functools import lru_cache
from .rag_system import RAGSystemOpenAI
from .conversation_memory import conversation_memory
import re

# Inicializar RAG globalmente
rag = RAGSystemOpenAI()
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
    """Genera respuesta INTELIGENTE CON EXTRACCIÓN DE INFORMACIÓN"""
    
    print(f"⚡ Procesando: '{user_text[:25]}...' [Chat: {chat_id}]")
    
    # ✅ NUEVO: Agregar mensaje del usuario a la memoria vectorial INMEDIATAMENTE
    conversation_memory.add_message_to_memory(chat_id, user_text, is_user=True)
    
    # 1. PRIORIDAD: Solo saludos de UNA palabra
    if is_greeting(user_text):
        print("👋 Saludo simple detectado - respuesta rápida")
        return get_welcome_message()
    
    # 2. PRIORIDAD: Verificar solicitud de agente humano (RÁPIDO)
    if is_handoff_request(user_text):
        print("🔄 Transferencia detectada")
        conversation_memory.clear_chat_context(chat_id)
        return get_handoff_message()
    
    # ✅ MODIFICADO: Validación más inteligente - Solo rechazar temas CLARAMENTE externos
    if is_clearly_out_of_scope(user_text):
        print("⚠️ Consulta claramente fuera de alcance detectada")
        return get_out_of_scope_message()
    
    # 3. Verificar documentos cargados (RÁPIDO)
    if not rag.chunks:
        return """❌ Lo siento, actualmente no tengo información técnica cargada en mi sistema.

Por favor, contacta con el administrador para que agregue los documentos necesarios."""
    
    # 4. Buscar información SÚPER OPTIMIZADA
    similar_chunks = rag.search_similar(user_text, k=3)  # ✅ AUMENTADO a 3 para más contexto
    
    # ✅ MODIFICADO: Validación más permisiva - Si encuentra chunks relevantes, continuar
    if not similar_chunks or not has_minimum_relevance(user_text, similar_chunks):
        print("⚠️ No se encontró información relevante en la documentación")
        return f"""❌ No encontré información específica sobre "{user_text}" en la documentación disponible.

📚 **Tengo información sobre:**
{', '.join(rag.list_documents())}

¿Hay algo específico de estos documentos en lo que pueda ayudarte?"""
    
    # 5. VERIFICAR CACHE SÚPER RÁPIDO (pero considerando memoria)
    cache_key = get_cache_key(user_text, similar_chunks)
    
    # ✅ MODIFICADO: Solo usar cache si NO hay memoria relevante
    has_memory = conversation_memory.should_use_context(chat_id, user_text)
    if cache_key in response_cache and not has_memory:
        print("⚡ CACHE HIT - RESPUESTA INSTANTÁNEA")
        return response_cache[cache_key]
    
    # 6. ✅ MEJORADO: Determinar contexto con memoria vectorial
    use_context = has_memory
    conversation_context = ""
    
    if use_context:
        # Obtener contexto de conversación previa
        conversation_context = conversation_memory.get_conversation_context(chat_id, user_text)
        print(f"🧠 Usando contexto de memoria vectorial")
    else:
        print("🆕 Nueva consulta independiente - sin contexto")
    
    # 7. Configurar OpenAI oficial
    openai_api_key = os.getenv("OPENAI_API_KEY")
    
    if not openai_api_key:
        return "❌ Error de configuración de OpenAI. Contacta al administrador."
    
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {openai_api_key}",
        "Content-Type": "application/json"
    }
    
    # 8. ✅ MEJORADO: Contexto más rico con múltiples chunks
    document_context = ""
    if similar_chunks:
        document_context = "INFORMACIÓN ENCONTRADA EN DOCUMENTOS:\n\n"
        for i, chunk in enumerate(similar_chunks[:3]):
            document_context += f"**Fuente {i+1}:** {chunk}\n\n"
    
    documents = rag.list_documents()
    
    # 9. ✅ COMPLETAMENTE REDISEÑADO: Sistema prompt INTELIGENTE Y ÚTIL
    system_prompt = f"""Eres TOmi, asistente técnico especializado e INTELIGENTE.

INSTRUCCIONES PRINCIPALES:
- Tu trabajo es SER ÚTIL y EXTRAER información relevante de los documentos
- Si encuentras información relacionada con la consulta, PRESÉNTALA de manera clara y organizada
- ANALIZA la información disponible y responde de la manera más útil posible
- Si hay listas, países, universidades, procedimientos, etc. - COMPÁRTELOS completamente
- Usa la memoria de conversación para dar respuestas contextualizadas
- Sé profesional pero ÚTIL y COMPLETO en tus respuestas
- Organiza la información con viñetas, números, o formato claro
- Si no tienes información específica, dilo claramente y sugiere alternativas

DOCUMENTOS DISPONIBLES: {', '.join(documents) if documents else 'Ninguno'}

{conversation_context}

Tu objetivo es ser el asistente MÁS ÚTIL posible usando la información disponible."""
    
    # 10. ✅ MEJORADO: Mensaje optimizado para extracción de información
    if conversation_context:
        current_message = f"""CONSULTA DEL USUARIO: {user_text}

{document_context}

INSTRUCCIONES ESPECÍFICAS:
- Extrae y presenta TODA la información relevante que encuentres
- Si hay listas (universidades, países, procedimientos), muéstralas COMPLETAS
- Organiza la información de manera clara y útil
- Usa la conversación previa para dar mejor contexto"""
    else:
        current_message = f"""CONSULTA: {user_text}

{document_context}

INSTRUCCIONES:
- Analiza la información disponible y presenta TODO lo relevante
- Si hay listas, procedimientos, requisitos, etc. - compártelos de manera organizada
- Sé completo y útil en tu respuesta"""
    
    # 11. ✅ MEJORADO: Payload optimizado para respuestas más completas
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": current_message}
        ],
        "temperature": 0.3,  # ✅ Aumentado para más creatividad en presentación
        "max_tokens": 600,   # ✅ AUMENTADO significativamente para respuestas completas
        "top_p": 0.9         # ✅ Aumentado para más flexibilidad
    }
    
    # ... resto del código igual hasta la respuesta ...
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)  # ✅ Timeout aumentado
        
        if response.status_code == 200:
            data = response.json()
            if "choices" in data and len(data["choices"]) > 0:
                reply = data["choices"][0]["message"]["content"].strip()
                
                # ✅ NUEVO: Agregar respuesta del bot a la memoria vectorial
                conversation_memory.add_message_to_memory(chat_id, reply, is_user=False)
                
                # 14. Guardar response_id para contexto futuro
                response_id = data.get("id")
                if response_id:
                    conversation_memory.set_response_id(chat_id, response_id, user_text)
                    print(f"💭 Response ID actualizado para chat {chat_id}: {response_id[:15]}...")
                
                print(f"✅ OpenAI: {len(reply)} chars")
                
                # 15. ✅ MEJORADO: Cache INTELIGENTE (solo para consultas sin memoria)
                if not has_memory:
                    response_cache[cache_key] = reply
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


def clear_chat_memory(chat_id: str):
    """Limpiar memoria COMPLETA de un chat específico"""
    conversation_memory.clear_chat_context(chat_id)
    global response_cache
    response_cache.clear()
    print(f"🗑️ Memoria completa y cache limpiados para chat {chat_id}")

def get_memory_stats(chat_id: str):
    """✅ NUEVO: Obtener estadísticas de memoria para un chat"""
    return conversation_memory.get_memory_stats(chat_id)

def setup_rag(pdf_folder: str = "data/pdfs"):
    """Función para configurar RAG"""
    global rag
    if os.path.exists(pdf_folder) and os.listdir(pdf_folder):
        rag.create_vector_database(pdf_folder)
        print("✅ RAG configurado correctamente")
    else:
        print(f"⚠️ No se encontraron PDFs en {pdf_folder}")

# ✅ NUEVO: Función para debug de memoria
def debug_chat_memory(chat_id: str):
    """Debug de memoria para un chat específico"""
    stats = get_memory_stats(chat_id)
    print(f"🔍 Debug memoria chat {chat_id}:")
    print(f"   📝 Mensajes en memoria: {stats['message_count']}")
    print(f"   🆔 Tiene response_id: {stats['has_response_id']}")
    print(f"   📋 Tiene topic: {stats['has_topic']}")
    
    # Mostrar últimos mensajes si existen
    if chat_id in conversation_memory.chat_message_history:
        recent_messages = conversation_memory.chat_message_history[chat_id][-3:]
        print(f"   📚 Últimos mensajes:")
        for timestamp, message, _ in recent_messages:
            preview = message[:80] + "..." if len(message) > 80 else message
            print(f"     • {timestamp[:16]} - {preview}")

def is_out_of_scope(user_text: str) -> bool:
    """Detectar consultas fuera del alcance ANTES de procesar"""
    user_lower = user_text.lower().strip()
    
    # Palabras clave que indican consultas fuera de alcance
    out_of_scope_indicators = [
        # Matemáticas y ciencias
        "matemática", "matemáticas", "ecuación", "fórmula", "calcular", "resolver",
        "física", "química", "biología", "estadística", "álgebra", "geometría",
        
        # Programación y tecnología
        "programar", "código", "python", "javascript", "html", "css", "sql",
        "algoritmo", "programación", "software", "aplicación", "app",
        
        # Consultas generales
        "receta", "cocinar", "tiempo", "clima", "noticias", "chiste", "juego",
        "película", "música", "deporte", "fútbol", "entretenimiento",
        
        # Salud y consejos personales
        "enfermo", "dolor", "medicina", "doctor", "síntoma", "tratamiento",
        "dieta", "ejercicio", "consejo personal", "relación", "amor",
        
        # Otras áreas
        "legal", "abogado", "derecho", "inversión", "dinero", "negocio",
        "viaje", "turismo", "hotel", "restaurant"
    ]
    
    # Si contiene indicadores de fuera de alcance
    for indicator in out_of_scope_indicators:
        if indicator in user_lower:
            return True
    
    # Patrones específicos
    math_patterns = [
        r'\b\d+\s*[\+\-\*\/]\s*\d+',  # Operaciones matemáticas
        r'x\s*=',  # Ecuaciones
        r'f\(x\)',  # Funciones
        r'derivada|integral',
        r'problema.*matemática'
    ]
    
    for pattern in math_patterns:
        if re.search(pattern, user_lower):
            return True
    
    return False

def is_clearly_out_of_scope(user_text: str) -> bool:
    """Detectar SOLO consultas CLARAMENTE fuera del alcance"""
    user_lower = user_text.lower().strip()
    
    # Solo rechazar temas CLARAMENTE externos que NO tienen relación con educación/universidad
    clearly_external = [
        # Matemáticas específicas (pero no procedimientos académicos)
        "ecuación", "fórmula", "calcular", "resolver", "derivada", "integral",
        
        # Programación específica
        "código", "python", "javascript", "html", "css", "sql", "algoritmo",
        
        # Entretenimiento
        "chiste", "juego", "película", "música", "deporte", "fútbol",
        
        # Salud personal
        "enfermo", "dolor", "síntoma", "tratamiento",
        
        # Cocina y recetas
        "receta", "cocinar", "ingrediente",
        
        # Clima y noticias
        "tiempo", "clima", "noticias", "temperatura"
    ]
    
    # Palabras académicas que SÍ son relevantes (no rechazar)
    academic_terms = [
        "universidad", "intercambio", "convalidación", "trámite", "procedimiento",
        "estudiante", "asignatura", "curso", "matrícula", "certificado",
        "documentación", "requisito", "país", "países", "lista", "carrera",
        "programa", "académico", "pregrado", "postgrado", "silabo"
    ]
    
    # Si contiene términos académicos, NO rechazar
    for term in academic_terms:
        if term in user_lower:
            return False
    
    # Solo rechazar si contiene términos claramente externos
    for term in clearly_external:
        if term in user_lower:
            return True
    
    # Patrones matemáticos específicos
    math_patterns = [
        r'\b\d+\s*[\+\-\*\/]\s*\d+',  # Operaciones matemáticas
        r'x\s*=',  # Ecuaciones
        r'f\(x\)',  # Funciones
    ]
    
    for pattern in math_patterns:
        if re.search(pattern, user_lower):
            return True
    
    return False


def has_minimum_relevance(user_text: str, chunks: list) -> bool:
    """Validar si hay relevancia mínima - MÁS PERMISIVO"""
    if not chunks:
        return False
    
    # Si el sistema RAG encontró chunks con similitud decente, confiar en él
    # (El sistema ya filtró por similitud > 0.15)
    return True  # ✅ Ser más permisivo y confiar en el sistema RAG


def is_query_relevant_to_chunks(user_text: str, chunks: list) -> bool:
    """Validar si la consulta está relacionada con los chunks encontrados"""
    if not chunks:
        return False
    
    user_lower = user_text.lower()
    
    # Palabras clave académicas que SÍ son relevantes
    academic_keywords = [
        "convalidación", "trámite", "procedimiento", "universidad", "estudiante",
        "asignatura", "curso", "matrícula", "certificado", "intercambio",
        "documentación", "requisito", "costo", "tarifa", "plazo", "entrega",
        "solicitud", "pago", "académico", "pregrado", "silabo"
    ]
    
    # Si la consulta contiene palabras académicas, es relevante
    for keyword in academic_keywords:
        if keyword in user_lower:
            return True
    
    # Verificar si los chunks contienen información académica relevante
    chunks_text = " ".join(chunks[:2]).lower()  # Solo los primeros 2 chunks
    
    # Si los chunks contienen palabras académicas y la similitud es razonable, es relevante
    chunk_academic_score = sum(1 for keyword in academic_keywords if keyword in chunks_text)
    
    # Si hay al menos 2 palabras académicas en los chunks, considerar relevante
    return chunk_academic_score >= 2

@lru_cache(maxsize=1)
def get_out_of_scope_message() -> str:
    """Mensaje para consultas CLARAMENTE fuera de alcance"""
    try:
        documents = rag.list_documents()
        
        base_message = """❌ Lo siento, esa consulta está fuera de mi área de especialización en procedimientos académicos y administrativos universitarios.

No puedo ayudarte con matemáticas avanzadas, programación, entretenimiento, salud personal, cocina o temas no relacionados con la universidad."""
        
        if documents:
            docs_list = "\n".join([f"• {doc}" for doc in documents[:5]])
            base_message += f"""

📚 **Mi especialización incluye información sobre:**
{docs_list}

¿Hay algo específico de estos temas en lo que pueda ayudarte?"""
        
        return base_message
        
    except Exception:
        return """❌ Lo siento, esa consulta está fuera de mi especialización en temas académicos y administrativos universitarios.

¿Hay algo relacionado con procedimientos universitarios en lo que pueda ayudarte?"""

print("⚡ Sistema RAG SÚPER OPTIMIZADO - OpenAI + Memoria Vectorial Completa + Cache")