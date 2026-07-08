import os
import pdfplumber
import uuid
from typing import List, Dict, Any
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
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

def ingest_document(file_path: str):
    """
    Fluxo de Ingestão:
    1. Lê o arquivo (suporta .pdf, .md, .txt).
    2. Remove os dados antigos desse mesmo arquivo do banco (evita duplicidade).
    3. Extrai todo o texto dele.
    4. Quebra o texto em chunks (pedaços menores).
    5. Converte cada chunk em um vetor numérico (embedding).
    6. Salva o vetor e o texto original atrelado a ele no banco de dados (Qdrant).
    """
    source_name = os.path.basename(file_path)
    print(f"Lendo documento: {source_name}")
    
    # Remove registros antigos desse arquivo para permitir re-ingestão (atualizações) sem duplicar
    try:
        qdrant_client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="source",
                        match=MatchValue(value=source_name)
                    )
                ]
            )
        )
    except Exception as e:
        print(f"Aviso: Não foi possível limpar registros antigos do Qdrant: {e}")
        
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
    
    print(f"Gerando embeddings para {len(chunks_data)} chunks e salvando no Qdrant...")
    points = []
    for i, item in enumerate(chunks_data):
        chunk_text = item["text"]
        chunk_meta = item["metadata"]
        
        # Transforma o pedaço de texto numérico
        vector = embeddings_model.embed_query(chunk_text)
        
        # Payload base
        payload = {
            "source": os.path.basename(file_path),
            "text": chunk_text,
            "chunk_index": i
        }
        # Mesclar metadados da seção (do MarkdownHeaderTextSplitter) sem apagar a base
        payload.update(chunk_meta)
        
        # Cria um ponto estruturado para o Qdrant
        point_id = str(uuid.uuid4())
        points.append(
            PointStruct(
                id=point_id,
                vector=vector,
                payload=payload
            )
        )
    
    # Salva todos os pontos em lote no banco
    if points:
        qdrant_client.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        )
        print(f"Ingestão do arquivo {os.path.basename(file_path)} concluída com sucesso!")

def search_knowledge_base(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Fluxo de Busca (Retriever):
    1. Recebe a pergunta do usuário.
    2. Transforma essa pergunta em um vetor usando o mesmo modelo (Google Embeddings).
    3. Busca no banco de dados Qdrant quais são os vetores mais próximos (semelhantes) ao vetor da pergunta.
    4. Retorna os textos originais (os chunks) encontrados.
    """
    # Transforma a pergunta em vetor
    query_vector = embeddings_model.embed_query(query)
    
    # Faz a busca no banco vetorial (usando a API moderna do qdrant)
    search_result = qdrant_client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k
    )
    
    # Formata a resposta para retornar apenas o que importa (o texto e a fonte)
    results = []
    # search_result.points contém a lista de documentos encontrados
    for hit in search_result.points:
        results.append({
            "score": hit.score,             # Grau de semelhança (quanto maior, melhor)
            "text": hit.payload["text"],    # O texto do manual que foi encontrado
            "source": hit.payload["source"] # De qual PDF isso veio
        })
        
    return results
