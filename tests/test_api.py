import os
from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app

client = TestClient(app)
VALID_KEY = os.environ.get("API_AUTH_KEY", "test-key-for-ci")


@patch("app.main.ingest_document")
def test_ingest_endpoint(mock_ingest):
    """
    Simula um usuario fazendo upload de um arquivo TXT pela API,
    e mocka a gravacao no Qdrant para o teste rodar rapido.
    """
    mock_ingest.return_value = None

    fake_file_content = b"Conteudo ficticio para teste do RAG"
    files = {"file": ("manual_teste.txt", fake_file_content, "text/plain")}

    response = client.post("/ingest", files=files, headers={"X-API-Key": VALID_KEY})

    assert response.status_code == 200, "A API deveria retornar status 200 OK"

    data = response.json()
    assert "message" in data, "A resposta deve conter a chave 'message'"
    assert "manual_teste.txt" in data["message"], "O nome do arquivo deve estar na mensagem"
    mock_ingest.assert_called_once()


@patch("app.main.ingest_document")
def test_ingest_path_traversal_sanitized(mock_ingest):
    """
    Testa se tentativas de Path Traversal (ex: '../../malicious.txt')
    sao devidamente sanitizadas para apenas o nome base ('malicious.txt').
    """
    mock_ingest.return_value = None

    fake_file_content = b"Conteudo teste traversal"
    files = {"file": ("../../malicious.txt", fake_file_content, "text/plain")}

    response = client.post("/ingest", files=files, headers={"X-API-Key": VALID_KEY})

    assert response.status_code == 200
    data = response.json()
    assert "malicious.txt" in data["message"]
    assert ".." not in data["message"]


def test_ingest_formato_nao_suportado_retorna_415():
    """Arquivos que nao sejam .pdf, .md ou .txt devem retornar 415 Unsupported Media Type."""
    files = {"file": ("executavel.exe", b"fake binary", "application/octet-stream")}
    response = client.post("/ingest", files=files, headers={"X-API-Key": VALID_KEY})
    assert response.status_code == 415
    assert "Formato nao suportado" in response.json()["detail"]


def test_ingest_arquivo_maior_que_10mb_retorna_413():
    """Arquivos com mais de 10MB devem ser rejeitados com 413 Payload Too Large."""
    # Simula 10MB + 1KB
    large_content = b"A" * (10 * 1024 * 1024 + 1024)
    files = {"file": ("grande_runbook.txt", large_content, "text/plain")}
    response = client.post("/ingest", files=files, headers={"X-API-Key": VALID_KEY})
    assert response.status_code == 413
    assert "maior que 10MB" in response.json()["detail"]
