import os
import sys
import argparse
from pathlib import Path

# Adiciona a raiz do projeto ao PYTHONPATH para podermos importar o módulo app
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from app.rag import ingest_document, init_qdrant

def ingest_all_docs(docs_dir: str):
    """
    Varre um diretório buscando arquivos PDF, MD e TXT e realiza a ingestão de cada um deles.
    """
    # Garante que a coleção do Qdrant existe antes de tentar apagar ou inserir dados
    init_qdrant()
    path = Path(docs_dir)
    if not path.exists() or not path.is_dir():
        print(f"Erro: O diretório '{docs_dir}' não foi encontrado.")
        return

    valid_extensions = {".pdf", ".md", ".txt"}
    files_to_process = [f for f in path.iterdir() if f.is_file() and f.suffix.lower() in valid_extensions]

    if not files_to_process:
        print(f"Aviso: Nenhum arquivo suportado ({', '.join(valid_extensions)}) encontrado em '{docs_dir}'.")
        return

    print(f"Iniciando ingestão em lote de {len(files_to_process)} arquivo(s) na pasta '{docs_dir}'...\n")

    success_count = 0
    error_count = 0

    for file in files_to_process:
        try:
            print(f"--- Processando: {file.name} ---")
            ingest_document(str(file))
            success_count += 1
            print(f"--- Concluído: {file.name} ---\n")
        except Exception as e:
            print(f"Erro ao processar o arquivo '{file.name}': {e}\n")
            error_count += 1

    print("================================")
    print("Resumo da Ingestão:")
    print(f"✅ Sucesso: {success_count}")
    if error_count > 0:
        print(f"❌ Erros: {error_count}")
    print("================================")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Script para ingestão em lote de documentos na Base de Conhecimento (Qdrant).")
    parser.add_argument(
        "--dir", 
        type=str, 
        default="docs", 
        help="Caminho da pasta que contém os documentos. O padrão é a pasta 'docs' do projeto."
    )
    
    args = parser.parse_args()
    
    # Resolve o caminho em relação à raiz do projeto, a menos que seja um caminho absoluto
    target_dir = args.dir
    if not os.path.isabs(target_dir):
        target_dir = os.path.join(project_root, target_dir)
        
    ingest_all_docs(target_dir)
