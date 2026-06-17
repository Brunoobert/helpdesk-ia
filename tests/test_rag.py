from app.rag import chunk_text

def test_chunk_text():
    """
    Testa matematicamente se a função de picotar o texto está mantendo o overlap correto
    e os tamanhos esperados sem estourar o limite.
    """
    text = "A" * 1000
    chunks = chunk_text(text, chunk_size=400, overlap=100)
    
    # Com 1000 caracteres, chunk de 400 e overlap de 100:
    # 1º chunk: 0 até 400
    # 2º chunk: 300 até 700 (300 porque 400 - 100 de overlap)
    # 3º chunk: 600 até 1000
    # 4º chunk: 900 até 1000
    assert len(chunks) == 4, "Deveria ter gerado 4 pedaços de texto"
    assert len(chunks[0]) == 400, "O tamanho do primeiro pedaço deveria ser o limite (400)"
    assert len(chunks[2]) == 400, "O tamanho do último pedaço deveria ser 400"
