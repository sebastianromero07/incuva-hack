import os
import PyPDF2
import pickle
import requests
import numpy as np
import re
import time



# Document Intelligence (mejor que Computer Vision)
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential

class RAGSystemOpenAI:
    def __init__(self, db_file="data/vector_database.pkl"):
        self.chunks = []
        self.embeddings = []
        self.documents = {}
        self.db_file = db_file
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        
        # Azure Document Intelligence (mejor que Computer Vision)
        self.azure_endpoint = os.getenv("AZURE_DOC_INTELLIGENCE_ENDPOINT")
        self.azure_key = os.getenv("AZURE_DOC_INTELLIGENCE_KEY")
        
        if self.azure_endpoint and self.azure_key:
            try:
                self.azure_client = DocumentIntelligenceClient(
                    endpoint=self.azure_endpoint,
                    credential=AzureKeyCredential(self.azure_key)
                )
                print("✅ Azure Document Intelligence configurado")
            except Exception as e:
                print(f"❌ Error configurando Azure: {e}")
                self.azure_client = None
        else:
            self.azure_client = None
            print("⚠️ Azure no configurado - usando PyPDF2")

    def extract_text_from_pdf_azure(self, pdf_path: str) -> str:
        """Document Intelligence - chunking semántico automático"""
        filename = os.path.basename(pdf_path)
        
        if not self.azure_client:
            return self.extract_text_from_pdf_basic(pdf_path)
        
        try:
            print(f"🔍 Analizando {filename} con Document Intelligence...")
            
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            
            # Document Intelligence con layout analysis
            poller = self.azure_client.begin_analyze_document(
                "prebuilt-layout",  # Modelo que entiende estructura del documento
                pdf_bytes,
                content_type="application/pdf"
            )
            
            result = poller.result()
            
            # Extraer texto RESPETANDO la estructura del documento
            structured_text = ""
            
            if result.paragraphs:
                # Si Document Intelligence detectó párrafos, usarlos
                print(f"   📄 {len(result.paragraphs)} párrafos detectados")
                for paragraph in result.paragraphs:
                    if paragraph.content and len(paragraph.content.strip()) > 20:
                        structured_text += paragraph.content.strip() + "\n\n"
            
            elif result.pages:
                # Fallback: extraer por páginas manteniendo estructura
                for page in result.pages:
                    if hasattr(page, 'lines') and page.lines:
                        page_text = []
                        for line in page.lines:
                            page_text.append(line.content)
                        
                        if page_text:
                            structured_text += "\n".join(page_text) + "\n\n"
            
            if len(structured_text.strip()) > 50:
                print(f"✅ Document Intelligence exitoso: {len(structured_text)} chars")
                return structured_text.strip()
            else:
                print("⚠️ Document Intelligence insuficiente, usando PyPDF2...")
                return self.extract_text_from_pdf_basic(pdf_path)
                
        except Exception as e:
            print(f"❌ Error Document Intelligence: {e}")
            return self.extract_text_from_pdf_basic(pdf_path)

    def extract_text_from_pdf_basic(self, pdf_path: str) -> str:
        """PyPDF2 fallback básico"""
        filename = os.path.basename(pdf_path)
        
        try:
            print(f"📄 Extrayendo con PyPDF2: {filename}...")
            text = ""
            
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text and len(page_text.strip()) > 10:
                            text += page_text + "\n\n"
                    except Exception as e:
                        print(f"   ⚠️ Error página {page_num + 1}: {e}")
                        continue
            
            if len(text.strip()) > 50:
                print(f"✅ PyPDF2 exitoso: {len(text)} chars")
                return text.strip()
            else:
                print(f"❌ PyPDF2 insuficiente: {len(text)} chars")
                return ""
                
        except Exception as e:
            print(f"❌ Error PyPDF2: {e}")
            return ""

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Método principal"""
        return self.extract_text_from_pdf_azure(pdf_path)

    def split_text_semantic_universal(self, text: str) -> list:
        """Chunking UNIVERSAL sin reglas hardcodeadas"""
        if not text or len(text.strip()) < 50:
            return []
        
        print("🧠 Aplicando chunking semántico universal...")
        
        # Limpiar texto preservando estructura
        cleaned_text = re.sub(r'\s+', ' ', text).strip()
        
        # ESTRATEGIA UNIVERSAL: Párrafos naturales del documento
        # Document Intelligence ya nos da párrafos bien estructurados
        
        paragraphs = []
        
        # Dividir por párrafos dobles (estructura natural)
        raw_paragraphs = re.split(r'\n\s*\n', cleaned_text)
        
        for para in raw_paragraphs:
            para = para.strip()
            if len(para) > 30:  # Filtrar párrafos muy cortos
                paragraphs.append(para)
        
        # Si no hay suficientes párrafos, dividir por oraciones
        if len(paragraphs) < 2:
            sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', cleaned_text)
            paragraphs = [s.strip() for s in sentences if len(s.strip()) > 30]
        
        print(f"📝 {len(paragraphs)} segmentos detectados")
        
        # Crear chunks respetando límites semánticos
        chunks = []
        current_chunk = ""
        optimal_size = 500  # Tamaño óptimo para text-embedding-3-large
        max_size = 800      # Máximo antes de forzar corte
        
        for paragraph in paragraphs:
            potential_size = len(current_chunk) + len(paragraph) + 1
            
            if potential_size <= optimal_size or len(current_chunk) < 100:
                # Agregar párrafo al chunk actual
                if current_chunk:
                    current_chunk += " " + paragraph
                else:
                    current_chunk = paragraph
            else:
                # Guardar chunk actual e iniciar nuevo
                if current_chunk and len(current_chunk) > 80:
                    chunks.append(current_chunk.strip())
                current_chunk = paragraph
            
            # Forzar corte si se vuelve muy largo
            if len(current_chunk) > max_size:
                chunks.append(current_chunk.strip())
                current_chunk = ""
        
        # Agregar último chunk
        if current_chunk and len(current_chunk.strip()) > 80:
            chunks.append(current_chunk.strip())
        
        print(f"✅ {len(chunks)} chunks semánticos creados")
        
        # Preview limpio
        for i, chunk in enumerate(chunks[:3]):
            preview = chunk[:150] + "..." if len(chunk) > 150 else chunk
            print(f"   📝 Chunk {i+1}: {preview}")
        
        return chunks

    def get_embedding(self, text: str) -> list:
        """Embeddings con text-embedding-3-large"""
        try:
            cleaned_text = re.sub(r'\s+', ' ', text.strip())
            
            # text-embedding-3-large maneja más tokens
            if len(cleaned_text) > 8000:
                cleaned_text = cleaned_text[:8000] + "..."
            
            url = "https://api.openai.com/v1/embeddings"
            headers = {
                "Authorization": f"Bearer {self.openai_api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "text-embedding-3-large",  # Modelo más potente
                "input": cleaned_text,
                "encoding_format": "float"
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            
            if response.status_code == 200:
                data = response.json()
                return data["data"][0]["embedding"]
            else:
                print(f"❌ Error OpenAI: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Error embedding: {e}")
            return None

    def get_batch_embeddings(self, texts: list) -> list:
        """Batch embeddings optimizado"""
        try:
            batch_size = 100  # text-embedding-3-large permite batches más grandes
            all_embeddings = []
            
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                
                url = "https://api.openai.com/v1/embeddings"
                headers = {
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "text-embedding-3-large",
                    "input": batch
                }
                
                response = requests.post(url, headers=headers, json=payload, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    batch_embeddings = [item["embedding"] for item in data["data"]]
                    all_embeddings.extend(batch_embeddings)
                    print(f"✅ Batch {i//batch_size + 1} procesado ({len(batch)} chunks)")
                else:
                    print(f"❌ Error batch: {response.status_code}")
                    return None
            
            return all_embeddings
            
        except Exception as e:
            print(f"❌ Error batch embeddings: {e}")
            return None

    def search_similar(self, query: str, k: int = 3) -> list:
        """Búsqueda semántica mejorada"""
        if not self.chunks or not self.embeddings:
            return []
        
        try:
            print(f"🔍 Búsqueda semántica: '{query}' en {len(self.chunks)} chunks")
            
            # Query embedding con modelo large
            query_embedding = self.get_embedding(query)
            if not query_embedding:
                return []
            
            # Calcular similitudes
            similarities = []
            for chunk_embedding in self.embeddings:
                similarity = self.cosine_similarity_simple(query_embedding, chunk_embedding)
                similarities.append(similarity)
            
            # Top resultados
            top_indices = np.argsort(similarities)[::-1][:k * 2]
            
            print(f"🎯 Resultados semánticos:")
            similar_chunks = []
            
            for i, idx in enumerate(top_indices[:8]):
                similarity = similarities[idx]
                chunk_preview = self.chunks[idx][:200] + "..." if len(self.chunks[idx]) > 200 else self.chunks[idx]
                print(f"   #{i+1}: {similarity:.3f} - {chunk_preview}")
                
                # Umbral más bajo para text-embedding-3-large (es más preciso)
                if similarity > 0.15 and len(similar_chunks) < k:
                    similar_chunks.append(self.chunks[idx])
            
            # Garantizar al menos 1 resultado si hay chunks
            if len(similar_chunks) == 0 and len(top_indices) > 0:
                similar_chunks.append(self.chunks[top_indices[0]])
                print("   ⚠️ Forzando mejor resultado disponible")
            
            print(f"✅ {len(similar_chunks)} chunks seleccionados")
            return similar_chunks
            
        except Exception as e:
            print(f"❌ Error búsqueda: {e}")
            return []

    def cosine_similarity_simple(self, vec1: list, vec2: list) -> float:
        """Similitud coseno optimizada"""
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

    # USAR el chunking universal en create_vector_database
    def create_vector_database(self, pdf_folder: str):
        """Crear BD con Document Intelligence + embeddings large"""
        print(f"📚 Procesando PDFs con Document Intelligence...")
        
        self.chunks = []
        self.documents = {}
        successful_docs = 0
        failed_docs = []
        
        if not os.path.exists(pdf_folder):
            os.makedirs(pdf_folder, exist_ok=True)
            return False
        
        pdf_files = [f for f in os.listdir(pdf_folder) if f.lower().endswith('.pdf')]
        
        if not pdf_files:
            print("📁 No se encontraron PDFs")
            return False
        
        for filename in pdf_files:
            pdf_path = os.path.join(pdf_folder, filename)
            
            try:
                # Document Intelligence extrae con estructura semántica
                text = self.extract_text_from_pdf(pdf_path)
                
                if not text or len(text.strip()) < 50:
                    failed_docs.append(filename)
                    continue
                
                # Chunking universal sin reglas hardcodeadas
                chunks = self.split_text_semantic_universal(text)
                
                if not chunks:
                    failed_docs.append(filename)
                    continue
                
                # Agregar chunks con metadatos
                for chunk in chunks:
                    enhanced_chunk = f"[{filename}] {chunk}"
                    self.chunks.append(enhanced_chunk)
                
                self.documents[filename] = len(chunks)
                successful_docs += 1
                print(f"✅ {filename}: {len(chunks)} chunks")
                
            except Exception as e:
                print(f"❌ Error {filename}: {e}")
                failed_docs.append(filename)
        
        if not self.chunks:
            print("❌ No se procesaron PDFs")
            return False
        
        # Embeddings con text-embedding-3-large
        print(f"\n🧠 Creando embeddings 3-large para {len(self.chunks)} chunks...")
        self.embeddings = self.get_batch_embeddings(self.chunks)
        
        if not self.embeddings:
            return False
        
        self.save_database()
        
        print(f"\n✅ BD semántica creada:")
        print(f"   📁 Documentos: {successful_docs}")
        print(f"   📝 Chunks: {len(self.chunks)}")
        if failed_docs:
            print(f"   ❌ Fallidos: {', '.join(failed_docs[:3])}")
        
        return True

    # Mantener métodos de persistencia, stats, etc. igual...
    def save_database(self):
        try:
            os.makedirs("data", exist_ok=True)
            data = {
                'chunks': self.chunks,
                'embeddings': self.embeddings,
                'documents': self.documents
            }
            
            with open(self.db_file, 'wb') as f:
                pickle.dump(data, f)
            
            print("💾 BD guardada")
            
        except Exception as e:
            print(f"❌ Error guardando: {e}")

    def load_database(self):
        try:
            if os.path.exists(self.db_file):
                with open(self.db_file, 'rb') as f:
                    data = pickle.load(f)
                
                self.chunks = data.get('chunks', [])
                self.embeddings = data.get('embeddings', [])
                self.documents = data.get('documents', {})
                
                print(f"📚 BD cargada: {len(self.documents)} docs, {len(self.chunks)} chunks")
            else:
                print("📚 BD no encontrada")
                
        except Exception as e:
            print(f"❌ Error cargando: {e}")
            self.chunks = []
            self.embeddings = []
            self.documents = {}

    def get_stats(self) -> dict:
        return {
            "total_documents": len(self.documents),
            "total_chunks": len(self.chunks),
            "documents": self.documents,
            "status": "active" if self.chunks else "empty"
        }

    def add_pdf_from_upload(self, file_content: bytes, filename: str) -> bool:
        try:
            pdf_folder = "data/pdfs"
            os.makedirs(pdf_folder, exist_ok=True)
            
            pdf_path = os.path.join(pdf_folder, filename)
            
            with open(pdf_path, 'wb') as f:
                f.write(file_content)
            
            return self.create_vector_database(pdf_folder)
            
        except Exception as e:
            print(f"❌ Error upload: {e}")
            return False

    def list_documents(self) -> list:
        return list(self.documents.keys())

    def remove_document(self, filename: str) -> bool:
        try:
            pdf_folder = "data/pdfs"
            pdf_path = os.path.join(pdf_folder, filename)
            
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
            
            self.create_vector_database(pdf_folder)
            return True
            
        except Exception as e:
            print(f"❌ Error eliminando: {e}")
            return False