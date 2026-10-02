"""
Testes unitarios para E4-07: Autenticacao de Borda via X-API-Key (ADR-006).
"""
import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

VALID_KEY = os.environ.get("API_AUTH_KEY", "test-key-for-ci")

VALID_TICKET = {
    "ticket_id": "AUTH-001",
    "text": "Reset de senha do usuario joao.silva",
    "source": "manual",
}


class TestAuthClassify:
    """Testes de autenticacao no endpoint POST /classify."""

    def test_classify_sem_api_key_retorna_401(self):
        """Requisicao sem header X-API-Key deve ser rejeitada."""
        response = client.post("/classify", json=VALID_TICKET)
        assert response.status_code == 401
        assert "X-API-Key" in response.json()["detail"]

    def test_classify_com_api_key_errada_retorna_401(self):
        """Requisicao com key invalida deve ser rejeitada."""
        response = client.post(
            "/classify",
            json=VALID_TICKET,
            headers={"X-API-Key": "chave-completamente-errada"},
        )
        assert response.status_code == 401

    @patch("app.classifier._invoke_llm")
    def test_classify_com_api_key_correta_retorna_200(self, mock_invoke):
        """Requisicao com key valida deve ser aceita."""
        from tests.test_classifier import mock_llm_json, DEFAULT_MOCK
        mock_invoke.return_value = mock_llm_json(**DEFAULT_MOCK)
        response = client.post(
            "/classify",
            json=VALID_TICKET,
            headers={"X-API-Key": VALID_KEY},
        )
        assert response.status_code == 200


class TestAuthIngest:
    """Testes de autenticacao no endpoint POST /ingest."""

    def test_ingest_sem_api_key_retorna_401(self):
        """Upload sem header X-API-Key deve ser rejeitado."""
        files = {"file": ("test.txt", b"conteudo de teste", "text/plain")}
        response = client.post("/ingest", files=files)
        assert response.status_code == 401

    @patch("app.main.ingest_document")
    def test_ingest_com_api_key_correta_retorna_200(self, mock_ingest):
        """Upload com key valida deve ser aceito."""
        mock_ingest.return_value = None
        files = {"file": ("test.txt", b"conteudo de teste", "text/plain")}
        response = client.post(
            "/ingest",
            files=files,
            headers={"X-API-Key": VALID_KEY},
        )
        assert response.status_code == 200


class TestHealthPublico:
    """GET /health deve permanecer publico (sem autenticacao)."""

    def test_health_sem_api_key_retorna_200(self):
        """Health check nao exige autenticacao."""
        response = client.get("/health")
        assert response.status_code == 200
        assert "status" in response.json()
