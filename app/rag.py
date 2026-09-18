import os
import pdfplumber
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue, FilterSelector,
    PayloadSelectorExclude,
)
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# Carrega as variáveis do .env
load_dotenv()

# --- Configurações Iniciais ---
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = "knowledge_base"

# Inicializamos a conexão com o banco de dados (Qdrant)
qdrant_client = QdrantClient(url=QDRANT_URL)

# Inicializamos o modelo de Embeddings do Google (Gemini)
# Este novo modelo converte textos em vetores de 3072 dimensões
embeddings_model = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    google_api_key=os.getenv("GEMINI_API_KEY")
)

def init_qdrant():
    """
    Verifica se a coleção já existe no Qdrant com a dimensão correta. 
    Se não existir ou estiver com o tamanho antigo (768), cria uma nova coleção 
    configurada para vetores de tamanho 3072 e métrica de distância do Cosseno.
    """
    if qdrant_client.collection_exists(COLLECTION_NAME):
        collection_info = qdrant_client.get_collection(COLLECTION_NAME)
        # Verifica se a coleção antiga foi criada com 768 dimensões
        if collection_info.config.params.vectors.size != 3072:
            print(f"Recriando coleção '{COLLECTION_NAME}' para suportar 3072 dimensões...")
            qdrant_client.delete_collection(COLLECTION_NAME)
            qdrant_client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=3072, distance=Distance.COSINE),
            )
        else:
            print(f"Coleção '{COLLECTION_NAME}' já existe e está com o tamanho correto.")
    else:
        qdrant_client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=3072, distance=Distance.COSINE),
        )
        print(f"Coleção '{COLLECTION_NAME}' criada com sucesso no Qdrant.")

def chunk_document(text: str, is_markdown: bool = False, chunk_size: int = 800, overlap: int = 100) -> List[Dict[str, Any]]:
    """
    Divide um texto grande em pedaços menores (chunks) baseando-se no número de CARACTERES.
    Se for Markdown, preserva as seções lógicas (## Problema) para não quebrar passo a passo no meio.
    Retorna uma lista de dicionários contendo o 'text' e os 'metadata' (ex: {'secao': 'Problema X'}).
    """
    result = []
    
    if is_markdown:
        headers_to_split_on = [("##", "secao"), ("###", "subsecao")]
        md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
        secoes = md_splitter.split_text(text)
        
        splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
        chunks_finais = splitter.split_documents(secoes)
        
        for chunk in chunks_finais:
            result.append({
                "text": chunk.page_content,
                "metadata": chunk.metadata
            })
    else:
        splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
        str_chunks = splitter.split_text(text)
        for chunk in str_chunks:
            result.append({
                "text": chunk,
                "metadata": {}
            })
            
    return result

def _get_current_version(source_name: str) -> int:
    """
    Consulta o Qdrant para descobrir qual é a versão ativa mais recente
    de um documento. Retorna 0 se o documento nunca foi indexado.
    """
    try:
        results, _ = qdrant_client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="source", match=MatchValue(value=source_name)),
                    FieldCondition(key="is_active", match=MatchValue(value=True)),
                ]
            ),
            limit=1,
            with_payload=True,
            with_vectors=False,
        )
        if results:
            return int(results[0].payload.get("version", 0))
    except Exception as e:
        print(f"Aviso: Não foi possível consultar versão atual ({e}). Assumindo versão 0.")
    return 0


def _deactivate_current_version(source_name: str) -> None:
    """
    E4-03 — Soft Invalidation: marca como is_active=False todos os chunks
    da versão ativa atual de um documento, SEM DELETAR os pontos do Qdrant.

    Isso preserva o histórico completo para auditoria temporal (ADR-005).
    """
    try:
        qdrant_client.set_payload(
            collection_name=COLLECTION_NAME,
            payload={"is_active": False},
            points=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(key="source", match=MatchValue(value=source_name)),
                        FieldCondition(key="is_active", match=MatchValue(value=True)),
                    ]
                )
            ),
        )
        print(f"Versão anterior de '{source_name}' marcada como is_active=False (soft invalidation).")
    except Exception as e:
        print(f"Aviso: Não foi possível desativar versão anterior de '{source_name}': {e}")


def ingest_document(file_path: str):
    """
    Fluxo de Ingestão com Versionamento Temporal (E4-03 / ADR-005):
    1. Lê o arquivo (suporta .pdf, .md, .txt).
    2. Detecta a versão ativa atual do documento no Qdrant.
    3. Executa Soft Invalidation: marca os chunks antigos como is_active=False (sem deletar).
    4. Extrai todo o texto do novo arquivo.
    5. Quebra o texto em chunks.
    6. Converte cada chunk em um vetor numérico (embedding).
    7. Salva os novos chunks com metadados de versão:
       - is_active=True, version=nova_versão, created_at=agora
    """
    source_name = os.path.basename(file_path)
    print(f"Iniciando ingestão com versionamento: {source_name}")

    # Detecta a versão atual e calcula a próxima
    current_version = _get_current_version(source_name)
    new_version = current_version + 1
    print(f"Versão atual: {current_version} → Nova versão: {new_version}")

    # Soft Invalidation: desativa os chunks da versão anterior (não deleta)
    if current_version > 0:
        _deactivate_current_version(source_name)

    full_text = ""

    if file_path.lower().endswith('.pdf'):
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    full_text += page_text + "\n"
    else:
        # Para .md e .txt, basta ler o texto diretamente
        with open(file_path, 'r', encoding='utf-8') as f:
            full_text = f.read()

    is_markdown = file_path.lower().endswith('.md')
    print("Criando chunks de texto...")
    chunks_data = chunk_document(full_text, is_markdown=is_markdown)

    ingested_at = datetime.now(timezone.utc).isoformat()
    print(f"Gerando embeddings para {len(chunks_data)} chunks e salvando no Qdrant (v{new_version})...")
    points = []
    for i, item in enumerate(chunks_data):
        chunk_text = item["text"]
        chunk_meta = item["metadata"]

        vector = embeddings_model.embed_query(chunk_text)

        # Payload base com metadados de versionamento (E4-03 / ADR-005)
        payload = {
            "source": source_name,
            "text": chunk_text,
            "chunk_index": i,
            "is_active": True,       # Versão ativa: visível para buscas
            "version": new_version,  # Inteiro incremental por documento
            "created_at": ingested_at,  # Timestamp ISO para auditoria temporal
        }
        # Mescla metadados de seção (do MarkdownHeaderTextSplitter) sem sobrescrever a base
        payload.update(chunk_meta)

        point_id = str(uuid.uuid4())
        points.append(
            PointStruct(
                id=point_id,
                vector=vector,
                payload=payload
            )
        )

    if points:
        qdrant_client.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        )
        print(f"Ingerão concluída: '{source_name}' v{new_version} ({len(points)} chunks, is_active=True).")

    return {"doc_id": source_name, "chunks_indexed": len(points), "version": new_version}

def search_knowledge_base(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Fluxo de Busca (Retriever) com filtro de versão ativa (E4-03):
    1. Recebe a pergunta do usuário.
    2. Transforma essa pergunta em um vetor usando o mesmo modelo (Google Embeddings).
    3. Busca no Qdrant apenas entre chunks com is_active=True (versões obsoletas são ignoradas).
    4. Retorna os textos originais (os chunks) encontrados.
    """
    query_vector = embeddings_model.embed_query(query)

    # Filtro obrigatório: só retorna chunks da versão ativa (ADR-005)
    active_filter = Filter(
        must=[FieldCondition(key="is_active", match=MatchValue(value=True))]
    )

    search_result = qdrant_client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=active_filter,
        limit=top_k,
    )

    results = []
    for hit in search_result.points:
        results.append({
            "score": hit.score,
            "text": hit.payload["text"],
            "source": hit.payload["source"],
            "version": hit.payload.get("version", 1),       # versão do chunk
            "created_at": hit.payload.get("created_at"),   # timestamp de indexação
        })

    return results


def get_document_history(source_name: str) -> List[Dict[str, Any]]:
    """
    E4-03 / ADR-005 — Auditoria Temporal.

    Retorna todas as versões (ativas e inativas) de um documento indexado,
    ordenadas por versão. Útil para responder:
    "Qual versão do runbook estava ativa quando o ticket TKT-123 foi classificado?"
    """
    try:
        results, _ = qdrant_client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=Filter(
                must=[FieldCondition(key="source", match=MatchValue(value=source_name))]
            ),
            limit=1000,
            with_payload=True,
            with_vectors=False,
        )
    except Exception as e:
        print(f"Erro ao consultar histórico de '{source_name}': {e}")
        return []

    # Agrupa por versão para retornar um resumo (não todos os chunks)
    versions: Dict[int, Dict[str, Any]] = {}
    for point in results:
        payload = point.payload
        v = int(payload.get("version", 0))
        if v not in versions:
            versions[v] = {
                "version": v,
                "is_active": payload.get("is_active", False),
                "created_at": payload.get("created_at"),
                "chunks_count": 0,
            }
        versions[v]["chunks_count"] += 1

    return sorted(versions.values(), key=lambda x: x["version"])
