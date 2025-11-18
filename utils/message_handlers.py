import re

def is_greeting(user_text: str) -> bool:
    """Detectar si es un saludo simple"""
    user_lower = user_text.lower().strip()
    
    greeting_patterns = [
        r'^(hola|hello|hi|buenas|saludos|hey)$',
        r'^(hola|hello|hi|buenas|hey)\s+(tomi|tom)$',
        r'^(hola|hello|hi|buenas|hey)\s+(tomi|tom)[!.]*$',
        r'^buenas\s+(tardes|noches|días)$',
        r'^buen\s+(día|dia)$'
    ]
    
    for pattern in greeting_patterns:
        if re.match(pattern, user_lower):
            return True
    
    return False

def is_user_correction_or_clarification(user_text: str) -> bool:
    """Detectar cuando el usuario está corrigiendo o aclarando"""
    user_lower = user_text.lower().strip()
    
    correction_indicators = [
        "todavía no", "aún no", "no te he preguntado", "no te pregunté",
        "no quería", "no necesito", "no era eso", "eso no era",
        "solo saludé", "solo dije hola", "era solo un saludo",
        "no necesito información", "no pedí información",
        "te confundiste", "no entendiste", "malentendiste",
        "no era necesario", "demasiada información"
    ]
    
    for indicator in correction_indicators:
        if indicator in user_lower:
            return True
    
    return False

def is_handoff_request(user_text: str) -> bool:
    """Detectar solicitud de agente humano"""
    user_lower = user_text.lower()
    
    if any(word in user_lower for word in ["agente", "persona", "humano", "transferir"]):
        return True
    
    return False

def is_general_info_request(user_text: str) -> bool:
    """Detectar SOLO consultas muy generales, no específicas"""
    user_lower = user_text.lower().strip()
    
    # ✅ SOLO consultas MUY GENERALES sin temas específicos
    very_general_patterns = [
        # Solo preguntas completamente abiertas
        r'^(que|qué)\s+(información|info)\s+tienes\s*\??$',
        r'^(que|qué)\s+(tienes|sabes)\s*\??$',
        r'^(en\s+que|en\s+qué)\s+(puedes\s+ayudar|ayudas)\s*\??$',
        r'^(cuéntame|informame|infórmame)\s*$',
        
        # Muy genérico sin tema específico
        r'^(que|qué)\s+(hay|existe)\s*\??$',
        r'^(que|qué)\s+(me\s+puedes\s+decir)\s*\??$'
    ]
    
    # ✅ EXCLUIR si menciona temas específicos
    specific_topics = [
        "beca", "crédito", "educativo", "convalidación", "intercambio",
        "internacional", "trámite", "procedimiento", "silabo", "curso"
    ]
    
    # Si menciona un tema específico, NO es general
    for topic in specific_topics:
        if topic in user_lower:
            return False
    
    # Solo es general si coincide con patrones muy generales
    import re
    for pattern in very_general_patterns:
        if re.match(pattern, user_lower):
            return True
    
    return False

def is_conversation_memory_query(user_text: str) -> bool:
    """✅ NUEVO: Detectar consultas sobre la conversación previa"""
    user_lower = user_text.lower().strip()
    
    memory_indicators = [
        # Preguntas sobre preguntas anteriores
        "que pregunt", "qué pregunt", "que te pregunt", "qué te pregunt",
        "pregunta anterior", "pregunta previa", "pregunta pasada",
        "hace un momento", "hace unos instantes", "hace poco", "antes",
        "anteriormente", "previamente",
        
        # Referencias temporales a la conversación
        "dijiste", "respondiste", "contestaste", "mencionaste",
        "hablamos de", "conversamos sobre", "tratamos",
        
        # Contexto de conversación
        "en base a lo que", "basándote en lo que", "según lo que",
        "como mencioné", "como dije", "como pregunté",
        
        # Referencias directas a mensajes anteriores
        "mi pregunta anterior", "lo que te dije", "lo que pregunté"
    ]
    
    for indicator in memory_indicators:
        if indicator in user_lower:
            return True
    
    return False

def should_use_conversation_context(user_text: str) -> bool:
    """✅ NUEVO: Determinar si debe usar contexto de conversación"""
    user_lower = user_text.lower().strip()
    
    context_indicators = [
        "en base a", "basándote en", "según", "como mencioné",
        "relacionado con", "sobre lo que", "acerca de lo que",
        "continuando", "además", "también", "y", "pero",
        "entonces", "así que", "por eso", "por tanto"
    ]
    
    # Si es una consulta de memoria, definitivamente usar contexto
    if is_conversation_memory_query(user_text):
        return True
    
    # Si tiene indicadores de contexto, usar contexto
    for indicator in context_indicators:
        if indicator in user_lower:
            return True
    
    return False