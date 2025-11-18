from functools import lru_cache

@lru_cache(maxsize=100)
def get_welcome_message() -> str:
    """Obtener mensaje de bienvenida del dashboard"""
    try:
        from dashboard.routes import get_bot_config
        bot_config = get_bot_config()
        
        welcome_msg = bot_config.get("welcome_message", "").strip()
        
        if welcome_msg:
            return welcome_msg
        else:
            return get_default_welcome_message()
            
    except Exception as e:
        print(f"⚠️ Error obteniendo mensaje del dashboard: {e}")
        return get_default_welcome_message()

def get_default_welcome_message() -> str:
    """Mensaje de bienvenida por defecto"""
    return """👋 ¡Hola! Soy TOmi, tu asistente virtual especializado en procedimientos académicos y administrativos.

Estoy aquí para ayudarte con información sobre:
• Convalidación de asignaturas
• Procesos de intercambio internacional  
• Trámites académicos y documentación
• Procedimientos administrativos universitarios

¿En qué puedo ayudarte hoy?"""

def get_correction_response() -> str:
    """Respuesta cuando el usuario corrige/aclara"""
    return """😊 ¡Tienes razón! Disculpa por adelantarme con información no solicitada.

Entiendo que solo me estabas saludando. ¡Hola! 👋

Estaré aquí cuando necesites ayuda con algún procedimiento académico o administrativo específico.

¿Hay algo en particular en lo que pueda asistirte?"""

@lru_cache(maxsize=100)
def get_handoff_message() -> str:
    """Obtener mensaje de transferencia"""
    try:
        from dashboard.routes import get_bot_config
        bot_config = get_bot_config()
        return bot_config.get("handoff_message", """🔄 Te voy a transferir con un agente humano que podrá ayudarte mejor.

Un momento por favor...""")
    except Exception:
        return "🔄 Transfiriendo a agente humano..."

def get_general_info_response(documents: list) -> str:
    """Respuesta concisa para consultas generales basada en documentos reales"""
    if not documents:
        return """📚 **Actualmente no tengo documentos cargados.**

Contacta al administrador para que agregue la documentación necesaria."""
    
    # ✅ RESPUESTA BASADA EN DOCUMENTOS REALES
    response = """📚 **Tengo información sobre los siguientes documentos:**

"""
    
    for doc in documents[:5]:  # Mostrar máximo 5 documentos
        # Limpiar nombre del documento
        clean_name = doc.replace('.pdf', '').replace('_', ' ')
        response += f"• **{clean_name}**\n"
    
    response += """
💬 **¿Sobre qué documento específico te gustaría saber más?**

Simplemente dime el tema que te interesa y te daré información detallada."""
    
    return response
