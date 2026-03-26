import chromadb
import os

db_path = "/home/gato/Gemini-Interpreter/.kogniterm/vector_db"
try:
    client = chromadb.PersistentClient(path=db_path)
    print("✅ ChromaDB se ha inicializado correctamente.")
    print(f"Colecciones disponibles: {client.list_collections()}")
except Exception as e:
    print(f"❌ Error al inicializar ChromaDB: {e}")
