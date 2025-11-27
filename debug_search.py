#!/usr/bin/env python3
"""
Script de diagnóstico para la búsqueda en el codebase.
"""
import os
import sys

# Add project to path
sys.path.insert(0, os.getcwd())

from kogniterm.core.context.vector_db_manager import VectorDBManager
from kogniterm.core.embeddings_service import EmbeddingsService

def main():
    workspace = os.getcwd()
    print(f"🔍 Diagnóstico de búsqueda en: {workspace}\n")
    
    # 1. Check if vector DB exists and has data
    print("=" * 60)
    print("1. Verificando Base de Datos Vectorial...")
    print("=" * 60)
    
    try:
        vector_db = VectorDBManager(workspace)
        count = vector_db.collection.count()
        print(f"✅ Colección encontrada: '{vector_db.collection.name}'")
        print(f"📊 Total de chunks indexados: {count}")
        
        if count == 0:
            print("⚠️  La base de datos está VACÍA. Necesitas indexar primero.")
            return
            
        # Get a sample
        sample = vector_db.collection.peek(limit=3)
        print(f"\n📝 Muestra de datos (primeros 3 chunks):")
        for i, doc in enumerate(sample['documents'][:3]):
            meta = sample['metadatas'][i]
            print(f"\n  Chunk {i+1}:")
            print(f"    Archivo: {meta.get('file_path', 'N/A')}")
            print(f"    Lenguaje: {meta.get('language', 'N/A')}")
            print(f"    Líneas: {meta.get('start_line', 'N/A')}-{meta.get('end_line', 'N/A')}")
            print(f"    Contenido (primeros 100 chars): {doc[:100]}...")
            
    except Exception as e:
        print(f"❌ Error al acceder a la base de datos: {e}")
        return
    
    # 2. Test embedding generation
    print("\n" + "=" * 60)
    print("2. Probando generación de embeddings...")
    print("=" * 60)
    
    try:
        embeddings_service = EmbeddingsService()
        test_query = "función para leer archivos"
        print(f"Query de prueba: '{test_query}'")
        
        embeddings = embeddings_service.generate_embeddings([test_query])
        if embeddings and len(embeddings) > 0:
            print(f"✅ Embedding generado correctamente")
            print(f"   Dimensiones: {len(embeddings[0])}")
            print(f"   Primeros 5 valores: {embeddings[0][:5]}")
        else:
            print(f"❌ No se pudo generar embedding")
            return
            
    except Exception as e:
        print(f"❌ Error al generar embedding: {e}")
        return
    
    # 3. Test search
    print("\n" + "=" * 60)
    print("3. Probando búsqueda...")
    print("=" * 60)
    
    try:
        results = vector_db.search(embeddings[0], k=5)
        print(f"📊 Resultados encontrados: {len(results)}")
        
        if len(results) == 0:
            print("⚠️  No se encontraron resultados. Posibles causas:")
            print("   - Los embeddings del índice no coinciden con el modelo actual")
            print("   - El contenido indexado no es relevante para la query")
            print("   - Problema con la configuración del modelo de embeddings")
        else:
            print("\n✅ Búsqueda exitosa! Primeros 3 resultados:")
            for i, result in enumerate(results[:3]):
                meta = result.get('metadata', {})
                content = result.get('content', '')
                distance = result.get('distance', 'N/A')
                print(f"\n  Resultado {i+1}:")
                print(f"    Archivo: {meta.get('file_path', 'N/A')}")
                print(f"    Distancia: {distance}")
                print(f"    Contenido (primeros 150 chars): {content[:150]}...")
                
    except Exception as e:
        print(f"❌ Error durante la búsqueda: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n" + "=" * 60)
    print("✅ Diagnóstico completado")
    print("=" * 60)

if __name__ == "__main__":
    main()
