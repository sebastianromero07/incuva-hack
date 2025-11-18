import json
import os
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
import requests

class ConversationMemory:
    def __init__(self, memory_file: str = "data/conversation_ids.json"):
        self.memory_file = memory_file
        self.chat_response_ids: Dict[str, str] = {}
        self.chat_last_topics: Dict[str, str] = {}
        
        # ✅ CORREGIDO: Memoria vectorial ampliada
        self.chat_message_history: Dict[str, List[Tuple[str, str, List[float]]]] = {}
        # Formato: chat_id -> [(timestamp, mensaje, embedding), ...]
        
        self.memory_duration_hours = 24  # 24 horas de memoria
        self.max_messages_per_chat = 20  # ✅ AUMENTADO: 20 mensajes por chat
        
        os.makedirs("data", exist_ok=True)
        self.load_response_ids()
    
    def get_embedding_for_memory(self, text: str) -> Optional[List[float]]:
        """Crear embedding para memoria de conversación"""
        try:
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if not openai_api_key:
                return None
            
            url = "https://api.openai.com/v1/embeddings"
            headers = {
                "Authorization": f"Bearer {openai_api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "text-embedding-3-large",  # Mejor modelo para memoria
                "input": text[:2000],  # Truncar para memoria
                "encoding_format": "float"
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data["data"][0]["embedding"]
            else:
                return None
                
        except Exception as e:
            print(f"❌ Error embedding memoria: {e}")
            return None
    
    def add_message_to_memory(self, chat_id: str, message: str, is_user: bool = True):
        """Agregar mensaje a la memoria vectorial"""
        try:
            # Crear embedding del mensaje
            embedding = self.get_embedding_for_memory(message)
            if not embedding:
                return
            
            # Inicializar historial si no existe
            if chat_id not in self.chat_message_history:
                self.chat_message_history[chat_id] = []
            
            # Agregar mensaje con timestamp
            timestamp = datetime.now().isoformat()
            role = "usuario" if is_user else "assistant"
            message_entry = (timestamp, f"{role}: {message}", embedding)
            
            self.chat_message_history[chat_id].append(message_entry)
            
            # ✅ CORREGIDO: Mantener más mensajes y rotación inteligente
            if len(self.chat_message_history[chat_id]) > self.max_messages_per_chat:
                # Mantener los primeros 5 (contexto inicial) + últimos 15 (conversación reciente)
                history = self.chat_message_history[chat_id]
                keep_first = history[:5]  # Primeros mensajes importantes
                keep_recent = history[-15:]  # Mensajes más recientes
                self.chat_message_history[chat_id] = keep_first + keep_recent
            
            print(f"💭 Mensaje agregado a memoria: Chat {chat_id} ({len(self.chat_message_history[chat_id])} mensajes)")
            
            # Guardar después de cada mensaje importante
            if is_user or len(self.chat_message_history[chat_id]) % 5 == 0:
                self.save_response_ids()
            
        except Exception as e:
            print(f"❌ Error agregando mensaje a memoria: {e}")

    def find_relevant_memory(self, chat_id: str, current_query: str, k: int = 5) -> List[str]:
        """✅ CORREGIDO: Buscar mensajes relevantes con mejor contexto histórico"""
        try:
            if chat_id not in self.chat_message_history:
                return []
            
            chat_history = self.chat_message_history[chat_id]
            if not chat_history:
                return []
            
            current_lower = current_query.lower()
            
            # ✅ MEJORADO: Si pregunta sobre conversación previa, mostrar MÁS contexto
            if any(keyword in current_lower for keyword in [
                'pregunte', 'pregunta', 'anterior', 'antes', 'previamente', 'hace poco',
                'y antes', 'antes de eso', 'pregunta anterior', 'dos preguntas'
            ]):
                print("🔍 Consulta de memoria ampliada detectada - mostrando más contexto")
                
                # ✅ AUMENTAR: Obtener los últimos 15 mensajes (más contexto)
                recent_messages = chat_history[-15:]
                relevant_messages = []
                
                # Filtrar preguntas del usuario (más completo)
                user_questions = []
                for timestamp, message, embedding in reversed(recent_messages):
                    if 'usuario:' in message:
                        # Excluir solo la pregunta ACTUAL
                        message_clean = message.replace('usuario:', '').strip()
                        if current_query.lower().strip() not in message_clean.lower():
                            user_questions.append((timestamp, message))
                
                # ✅ MOSTRAR múltiples preguntas anteriores (no solo la más reciente)
                if user_questions:
                    for i, (timestamp, message) in enumerate(user_questions[:5]):  # Hasta 5 preguntas
                        relevant_messages.append(f"[{timestamp[:16]}] {message}")
                
                if relevant_messages:
                    print(f"🔍 Encontradas {len(relevant_messages)} preguntas anteriores")
                    return relevant_messages
                
            # ✅ FALLBACK: Búsqueda semántica normal
            return self._semantic_search(chat_history, current_query, k)
            
        except Exception as e:
            print(f"❌ Error buscando en memoria: {e}")
            return []

    def _semantic_search(self, chat_history: List[Tuple], current_query: str, k: int) -> List[str]:
        """✅ AGREGADO: Búsqueda semántica normal"""
        try:
            query_embedding = self.get_embedding_for_memory(current_query)
            if not query_embedding:
                return []
            
            # Búsqueda semántica normal para otros casos
            semantic_matches = []
            
            for i, (timestamp, message, embedding) in enumerate(chat_history):
                if embedding:  # Solo si tiene embedding
                    similarity = self.cosine_similarity(query_embedding, embedding)
                    if similarity > 0.3:
                        semantic_matches.append((similarity, message, timestamp, i))
            
            # Ordenar por similitud
            semantic_matches.sort(key=lambda x: x[0], reverse=True)
            
            # Tomar los mejores
            relevant_messages = []
            for similarity, message, timestamp, idx in semantic_matches[:k]:
                relevant_messages.append(f"[{timestamp[:16]}] {message}")
            
            if relevant_messages:
                print(f"🔍 Encontrados {len(relevant_messages)} mensajes semánticamente relevantes")
                for msg in relevant_messages[:3]:
                    print(f"   📝 {msg[:100]}...")
            
            return relevant_messages
            
        except Exception as e:
            print(f"❌ Error en búsqueda semántica: {e}")
            return []
            
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calcular similitud coseno"""
        try:
            a = np.array(vec1, dtype=np.float32)
            b = np.array(vec2, dtype=np.float32)
            
            dot_product = np.dot(a, b)
            norm_product = np.linalg.norm(a) * np.linalg.norm(b)
            
            if norm_product == 0:
                return 0.0
            
            return float(np.clip(dot_product / norm_product, -1.0, 1.0))
            
        except Exception as e:
            return 0.0
    
    def should_use_context(self, chat_id: str, current_text: str) -> bool:
        """✅ MEJORADO: Detectar si usar contexto"""
        if chat_id not in self.chat_response_ids:
            return False
        
        current_lower = current_text.lower().strip()
        
        # 1. ✅ MEJORADO: Indicadores de memoria más específicos
        memory_indicators = [
            "que te pregunte", "que te pregunté", "que te preguntė", "que pregunté",
            "anteriormente", "antes", "previo", "previa", "anterior",
            "dijiste que", "mencionaste", "comentaste", "hablamos de", "conversamos",
            "la vez pasada", "hace rato", "recuerdas", "te acuerdas",
            "dos preguntas atrás", "pregunta anterior", "hace poco", "ya te dije"
        ]
        
        for indicator in memory_indicators:
            if indicator in current_lower:
                print(f"🧠 Indicador de memoria detectado: '{indicator}'")
                return True
        
        # 2. Continuidad conversacional
        continuity_indicators = [
            "también", "además", "pero", "sin embargo", "entonces", "y si",
            "¿y qué más?", "¿cómo así?", "¿por qué?", "explícame más", "claro"
        ]
        
        for indicator in continuity_indicators:
            if current_lower.startswith(indicator) or f" {indicator} " in current_lower:
                print(f"🔗 Continuidad detectada: '{indicator}'")
                return True
        
        # 3. Buscar en memoria vectorial si parece relacionado
        relevant_memories = self.find_relevant_memory(chat_id, current_text, k=2)
        if relevant_memories:
            print("🧠 Memoria vectorial relevante encontrada")
            return True
        
        print("🆕 Nueva consulta independiente")
        return False
    
    def get_conversation_context(self, chat_id: str, current_query: str) -> str:
        """✅ MEJORADO: Obtener contexto más rico"""
        try:
            # Buscar mensajes relevantes en memoria
            relevant_memories = self.find_relevant_memory(chat_id, current_query, k=5)
            
            if relevant_memories:
                context_lines = []
                context_lines.append("CONVERSACIÓN PREVIA RELEVANTE:")
                
                # Organizar por tipo de mensaje
                user_questions = []
                assistant_responses = []
                
                for memory in relevant_memories:
                    if "usuario:" in memory:
                        user_questions.append(memory)
                    elif "assistant:" in memory:
                        assistant_responses.append(memory)
                
                # Mostrar preguntas del usuario primero
                if user_questions:
                    context_lines.append("\nPREGUNTAS ANTERIORES DEL USUARIO:")
                    for question in user_questions[:3]:  # Máximo 3 preguntas
                        context_lines.append(question)
                
                # Luego respuestas relevantes
                if assistant_responses:
                    context_lines.append("\nRESPUESTAS PREVIAS RELEVANTES:")
                    for response in assistant_responses[:2]:  # Máximo 2 respuestas
                        # Truncar respuestas largas
                        if len(response) > 200:
                            response = response[:200] + "..."
                        context_lines.append(response)
                
                return "\n".join(context_lines)
            else:
                return ""
                
        except Exception as e:
            print(f"❌ Error obteniendo contexto: {e}")
            return ""
    
    def get_recent_conversation_summary(self, chat_id: str, limit: int = 5) -> str:
        """✅ NUEVO: Obtener resumen de conversación reciente"""
        try:
            if chat_id not in self.chat_message_history:
                return ""
            
            recent_messages = self.chat_message_history[chat_id][-limit:]
            
            if not recent_messages:
                return ""
            
            summary_lines = ["CONVERSACIÓN RECIENTE:"]
            for timestamp, message, _ in recent_messages:
                # Truncar mensajes largos
                display_message = message
                if len(display_message) > 150:
                    display_message = display_message[:150] + "..."
                summary_lines.append(f"[{timestamp[11:16]}] {display_message}")
            
            return "\n".join(summary_lines)
            
        except Exception as e:
            return ""
    
    def clear_chat_context(self, chat_id: str):
        """Limpiar contexto completo de un chat"""
        if chat_id in self.chat_response_ids:
            del self.chat_response_ids[chat_id]
        if chat_id in self.chat_last_topics:
            del self.chat_last_topics[chat_id]
        if chat_id in self.chat_message_history:
            del self.chat_message_history[chat_id]
        
        self.save_response_ids()
        print(f"🗑️ Memoria completa limpiada para chat {chat_id}")
    
    def get_memory_stats(self, chat_id: str) -> Dict:
        """Estadísticas de memoria para un chat específico"""
        return {
            "has_response_id": chat_id in self.chat_response_ids,
            "message_count": len(self.chat_message_history.get(chat_id, [])),
            "has_topic": chat_id in self.chat_last_topics
        }
    
    def set_response_id(self, chat_id: str, response_id: str, topic: str = ""):
        """Almacenar response_id"""
        self.chat_response_ids[chat_id] = response_id
        if topic:
            self.chat_last_topics[chat_id] = topic[:100]
        # No guardar en cada response_id, solo en mensajes importantes
        print(f"💭 Response ID actualizado para chat {chat_id}")
    
    def get_previous_response_id(self, chat_id: str) -> Optional[str]:
        """Obtener response_id previo"""
        return self.chat_response_ids.get(chat_id)
    
    def save_response_ids(self):
        """Guardar toda la memoria en archivo"""
        try:
            data = {
                "response_ids": self.chat_response_ids,
                "last_topics": self.chat_last_topics,
                "message_history": {
                    chat_id: [
                        {
                            "timestamp": timestamp,
                            "message": message,
                            "embedding": embedding
                        }
                        for timestamp, message, embedding in history
                    ]
                    for chat_id, history in self.chat_message_history.items()
                },
                "last_updated": datetime.now().isoformat()
            }
            
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        
        except Exception as e:
            print(f"❌ Error guardando memoria: {e}")
    
    def load_response_ids(self):
        """Cargar memoria completa desde archivo"""
        try:
            if os.path.exists(self.memory_file):
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                self.chat_response_ids = data.get("response_ids", {})
                self.chat_last_topics = data.get("last_topics", {})
                
                # Cargar historial de mensajes
                message_history_data = data.get("message_history", {})
                for chat_id, history in message_history_data.items():
                    self.chat_message_history[chat_id] = [
                        (item["timestamp"], item["message"], item["embedding"])
                        for item in history
                    ]
                
                total_messages = sum(len(history) for history in self.chat_message_history.values())
                print(f"💭 Memoria completa cargada: {len(self.chat_response_ids)} chats, {total_messages} mensajes")
            else:
                print("💭 Nueva memoria vectorial creada")
        
        except Exception as e:
            print(f"❌ Error cargando memoria: {e}")
            self.chat_response_ids = {}
            self.chat_last_topics = {}
            self.chat_message_history = {}

# Instancia global
conversation_memory = ConversationMemory()