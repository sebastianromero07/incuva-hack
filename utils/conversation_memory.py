import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional

class ConversationMemory:
    def __init__(self, memory_file: str = "data/conversation_ids.json"):
        self.memory_file = memory_file
        # Solo almacenamos el último response_id por chat
        self.chat_response_ids: Dict[str, str] = {}
        self.chat_last_topics: Dict[str, str] = {}  # Último tema por chat
        self.memory_duration_hours = 2  # REDUCIDO para optimizar
        
        os.makedirs("data", exist_ok=True)
        self.load_response_ids()
    
    def should_use_context(self, chat_id: str, current_text: str) -> bool:
        """Determinar si debe usar contexto previo basado en continuidad REAL"""
        if chat_id not in self.chat_response_ids:
            return False
        
        current_lower = current_text.lower().strip()
        
        # 1. EXCLUIR preguntas independientes comunes (NO necesitan contexto)
        independent_patterns = [
            "qué información tienes", "que información tienes",
            "qué puedes hacer", "que puedes hacer",
            "ayúdame con", "ayudame con",
            "necesito información", "necesito informacion",
            "cuéntame sobre", "cuentame sobre",
            "explícame", "explicame",
            "dime sobre", "háblame de", "hablame de"
        ]
        
        for pattern in independent_patterns:
            if pattern in current_lower:
                print(f"🆕 Pregunta independiente detectada: '{pattern}'")
                return False
        
        # 2. Solo indicadores de continuidad FUERTES
        strong_continuity = [
            "también", "además", "pero", "sin embargo", "ahora bien",
            "entonces", "después de eso", "siguiente", "continúa",
            "¿y qué más?", "¿qué más?", "¿cómo así?", "¿por qué?",
            "anteriormente mencionaste", "dijiste que", "mencionaste"
        ]
        
        for indicator in strong_continuity:
            if indicator in current_lower:
                print(f"🔗 Continuidad FUERTE detectada: '{indicator}'")
                return True
        
        # 3. Preguntas MUY cortas de seguimiento (máximo 3 palabras)
        words = current_text.split()
        if len(words) <= 3 and any(word in current_lower for word in ["¿cómo?", "¿por qué?", "¿cuándo?", "¿dónde?", "más", "otro"]):
            print("🔗 Pregunta de seguimiento muy corta")
            return True
        
        # 4. Por defecto: NO usar contexto para maximizar velocidad
        print("🆕 Nueva consulta independiente - sin contexto")
        return False
    
    def set_response_id(self, chat_id: str, response_id: str, topic: str = ""):
        """Almacenar el último response_id y tema para un chat"""
        self.chat_response_ids[chat_id] = response_id
        if topic:
            self.chat_last_topics[chat_id] = topic[:100]  # Truncar tema
        self.save_response_ids()
        print(f"💭 Response ID actualizado para chat {chat_id}: {response_id[:20]}...")
    
    def get_previous_response_id(self, chat_id: str) -> Optional[str]:
        """Obtener el último response_id para mantener contexto"""
        return self.chat_response_ids.get(chat_id)
    
    def clear_chat_context(self, chat_id: str):
        """Limpiar contexto de un chat específico"""
        if chat_id in self.chat_response_ids:
            del self.chat_response_ids[chat_id]
        if chat_id in self.chat_last_topics:
            del self.chat_last_topics[chat_id]
        self.save_response_ids()
        print(f"🗑️ Contexto limpiado para chat {chat_id}")
    
    def get_stats(self) -> Dict:
        """Estadísticas de memoria"""
        return {
            "active_chats_with_context": len(self.chat_response_ids),
            "memory_duration_hours": self.memory_duration_hours
        }
    
    def save_response_ids(self):
        """Guardar response IDs en archivo"""
        try:
            data = {
                "response_ids": self.chat_response_ids,
                "last_topics": self.chat_last_topics,
                "last_updated": datetime.now().isoformat()
            }
            
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        
        except Exception as e:
            print(f"❌ Error guardando response IDs: {e}")
    
    def load_response_ids(self):
        """Cargar response IDs desde archivo"""
        try:
            if os.path.exists(self.memory_file):
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                self.chat_response_ids = data.get("response_ids", {})
                self.chat_last_topics = data.get("last_topics", {})
                
                print(f"💭 Response IDs cargados: {len(self.chat_response_ids)} chats con contexto")
            else:
                print("💭 Nueva memoria de response IDs creada")
        
        except Exception as e:
            print(f"❌ Error cargando response IDs: {e}")
            self.chat_response_ids = {}
            self.chat_last_topics = {}

# Instancia global
conversation_memory = ConversationMemory()