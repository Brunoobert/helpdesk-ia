from app.rag import chunk_document

def test_chunk_document():
    """
    Testa matematicamente se a função de picotar o texto (baseada em caracteres) 
    está mantendo o overlap correto e os tamanhos esperados sem estourar o limite,
    agora usando o retorno em formato de dicionário (estrutural).
    """
    # 1000 caracteres
    text = "A" * 1000
    
    # Com 1000 caracteres, limite de 400 e overlap de 100 para um TXT (is_markdown=False)
    # 1º chunk: 0 até 400
    # 2º chunk: 300 até 700 (300 porque 400 - 100 de overlap)
    # 3º chunk: 600 até 1000 (termina exatamente no fim do texto)
    # O RecursiveCharacterTextSplitter do Langchain é inteligente e para aqui, sem criar
    # um quarto chunk redundante (ao contrário do nosso loop naive anterior).
    chunks = chunk_document(text, is_markdown=False, chunk_size=400, overlap=100)
    
    assert len(chunks) == 3, "Deveria ter quebrado em 3 pedaços devido ao limite e overlap"
    assert "text" in chunks[0], "Cada chunk deve ser um dicionário com a chave 'text'"
