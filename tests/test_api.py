from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app

client = TestClient(app)

@patch("app.main.ingest_document")
def test_ingest_endpoint(mock_ingest):
    """
    Simula um usuário fazendo upload de um arquivo TXT pela API,
    e "mocka" (falsifica) a gravação no Qdrant para o teste rodar rápido e não sujar o banco.
    """
    mock_ingest.return_value = None
    
    # Criamos um arquivo falso em memória
    fake_file_content = b"Conteudo ficticio para teste do RAG"
    files = {"file": ("manual_teste.txt", fake_file_content, "text/plain")}
    
    response = client.post("/ingest", files=files)
    
    assert response.status_code == 200, "A API deveria retornar status 200 OK"
    
    data = response.json()
    assert "message" in data, "A resposta deve conter a chave 'message'"
    assert "manual_teste.txt" in data["message"], "O nome do arquivo deve estar na mensagem"
    
    # Verifica se a função interna de ingestão foi chamada 1 vez
    mock_ingest.assert_called_once()
