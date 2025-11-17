import os
import json
import pickle
from typing import List, Dict, Optional
from PyPDF2 import PdfReader
import io

class RAGSystem:
    def __init__(self, db_path: str = "faiss_db"):
        self.db_path = db_path
        self.documents = {}
        self.chunks = []
        self.chunk_to_doc = {}
        
        # Crear directorio si no existe
        os.makedirs(db_path, exist_ok=True)
    
    def _split_text(self, text: str, chunk_size: int = 500) -> List[str]:
        """Dividir texto en chunks por palabras"""
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            if chunk.strip():
                chunks.append(chunk.strip())
        
        return chunks
    
    def _simple_search(self, query: str, chunks: List[str], k: int = 3) -> List[str]:
        """Búsqueda simple basada en palabras clave con mejor scoring"""
        query_words = set(query.lower().split())
        
        # Palabras de parada en español
        stop_words = {"el", "la", "de", "que", "y", "en", "un", "es", "se", "no", "te", "lo", "le", "da", "su", "por", "son", "con", "para", "como", "al", "del", "si", "me", "mi", "tu", "este", "esta", "hay", "pero", "más", "o", "muy", "ya", "todo", "bien", "puede", "ser", "tiene", "hacer", "vez", "dos", "aquí", "cómo", "qué", "dónde", "cuándo"}
        
        # Filtrar palabras de parada
        query_words = query_words - stop_words
        
        if not query_words:
            return []
        
        # Calcular puntuaciones mejoradas
        scores = []
        for i, chunk in enumerate(chunks):
            chunk_words = set(chunk.lower().split()) - stop_words
            
            # Calcular diferentes tipos de coincidencias
            exact_matches = len(query_words.intersection(chunk_words))
            partial_matches = sum(1 for qw in query_words for cw in chunk_words if qw in cw or cw in qw)
            
            # Puntuación combinada
            exact_score = exact_matches / max(len(query_words), 1)
            partial_score = partial_matches / max(len(query_words), 1) * 0.3
            total_score = exact_score + partial_score
            
            if total_score > 0:
                scores.append((total_score, i, chunk))
        
        # Ordenar por puntuación y devolver top k
        scores.sort(key=lambda x: x[0], reverse=True)
        
        # Solo devolver chunks con puntuación mínima
        min_score = 0.1  # Umbral mínimo de relevancia
        return [chunk for score, idx, chunk in scores[:k] if score >= min_score]
        
    def add_pdf_from_upload(self, file_content: bytes, filename: str) -> bool:
        """Agregar PDF desde upload"""
        try:
            # Leer PDF
            pdf_reader = PdfReader(io.BytesIO(file_content))
            text_content = ""
            
            for page in pdf_reader.pages:
                text_content += page.extract_text() + "\n"
            
            if not text_content.strip():
                print(f"❌ No se pudo extraer texto de {filename}")
                return False
            
            # Dividir en chunks
            chunks = self._split_text(text_content, chunk_size=500)
            
            # Guardar chunks
            start_idx = len(self.chunks)
            self.chunks.extend(chunks)
            
            # Mapear documento a chunks
            chunk_indices = list(range(start_idx, len(self.chunks)))
            self.documents[filename] = chunk_indices
            
            # Mapear chunks a documento
            for idx in chunk_indices:
                self.chunk_to_doc[idx] = filename
            
            # Guardar en disco
            self.save_database()
            
            print(f"✅ {filename}: {len(chunks)} chunks agregados")
            return True
            
        except Exception as e:
            print(f"❌ Error procesando {filename}: {e}")
            return False
    
    def search_similar(self, query: str, k: int = 3) -> List[str]:
        """Buscar chunks similares usando búsqueda simple"""
        if not self.chunks:
            return []
        
        return self._simple_search(query, self.chunks, k)
    
    def delete_document(self, filename: str) -> bool:
        """Eliminar documento"""
        try:
            if filename not in self.documents:
                return False
            
            # Obtener índices de chunks del documento
            doc_chunks = self.documents[filename]
            
            # Crear nuevas listas sin los chunks del documento
            new_chunks = []
            new_chunk_to_doc = {}
            new_documents = {}
            
            # Reindexar todos los chunks excepto los del documento eliminado
            new_idx = 0
            for old_idx, chunk in enumerate(self.chunks):
                if old_idx not in doc_chunks:
                    new_chunks.append(chunk)
                    doc_name = self.chunk_to_doc.get(old_idx)
                    if doc_name and doc_name != filename:
                        new_chunk_to_doc[new_idx] = doc_name
                        
                        # Actualizar mapeo de documentos
                        if doc_name not in new_documents:
                            new_documents[doc_name] = []
                        new_documents[doc_name].append(new_idx)
                    
                    new_idx += 1
            
            # Actualizar estructuras
            self.chunks = new_chunks
            self.chunk_to_doc = new_chunk_to_doc
            self.documents = new_documents
            
            # Guardar cambios
            self.save_database()
            
            print(f"✅ Documento {filename} eliminado")
            return True
            
        except Exception as e:
            print(f"❌ Error eliminando {filename}: {e}")
            return False
    
    def list_documents(self) -> List[str]:
        """Listar documentos cargados"""
        return list(self.documents.keys())
    
    def get_stats(self) -> Dict:
        """Obtener estadísticas"""
        return {
            "pdf_count": len(self.documents),
            "chunks_count": len(self.chunks),
            "rag_status": len(self.chunks) > 0
        }
    
    def save_database(self):
        """Guardar base de datos"""
        try:
            # Guardar chunks
            with open(os.path.join(self.db_path, "chunks.pkl"), "wb") as f:
                pickle.dump(self.chunks, f)
            
            # Guardar mapeos
            with open(os.path.join(self.db_path, "documents.json"), "w") as f:
                json.dump({
                    "documents": self.documents,
                    "chunk_to_doc": self.chunk_to_doc
                }, f, indent=2)
            
            print("💾 Base de datos guardada")
            
        except Exception as e:
            print(f"❌ Error guardando BD: {e}")
    
    def load_database(self):
        """Cargar base de datos existente"""
        try:
            chunks_file = os.path.join(self.db_path, "chunks.pkl")
            docs_file = os.path.join(self.db_path, "documents.json")
            
            if os.path.exists(chunks_file) and os.path.exists(docs_file):
                # Cargar chunks
                with open(chunks_file, "rb") as f:
                    self.chunks = pickle.load(f)
                
                # Cargar mapeos
                with open(docs_file, "r") as f:
                    data = json.load(f)
                    self.documents = data.get("documents", {})
                    self.chunk_to_doc = {int(k): v for k, v in data.get("chunk_to_doc", {}).items()}
                
                print(f"📚 BD cargada: {len(self.documents)} docs, {len(self.chunks)} chunks")
            else:
                print("📝 Nueva base de datos creada")
                
        except Exception as e:
            print(f"❌ Error cargando BD: {e}")
            self.chunks = []
            self.documents = {}
            self.chunk_to_doc = {}
    
    def create_vector_database(self, pdf_folder: str):
        """Crear BD desde carpeta de PDFs"""
        if not os.path.exists(pdf_folder):
            print(f"❌ Carpeta {pdf_folder} no existe")
            return
        
        pdf_files = [f for f in os.listdir(pdf_folder) if f.endswith('.pdf')]
        
        for pdf_file in pdf_files:
            pdf_path = os.path.join(pdf_folder, pdf_file)
            try:
                with open(pdf_path, 'rb') as f:
                    self.add_pdf_from_upload(f.read(), pdf_file)
            except Exception as e:
                print(f"❌ Error con {pdf_file}: {e}")
        
        print(f"✅ Procesados {len(pdf_files)} PDFs")