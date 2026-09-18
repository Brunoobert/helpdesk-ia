"""
Testes unitarios para E4-06 (Model Switching) e E4-03 (Versionamento RAG).

Estes testes NAO precisam de Docker, Qdrant ou chaves de API rodando.
Mockam as dependencias externas para testar apenas a logica interna.

Execucao:
    .venv\\Scripts\\pytest tests/test_e4_unit.py -v
"""

import os
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Bloco 1 - E4-06: _resolve_llm e _build_llm
# ---------------------------------------------------------------------------

class TestModelSwitching:
    """
    Testa a logica de selecao de LLM por requisicao (E4-06).
    Nao faz chamadas reais - apenas verifica se o provider correto e instanciado.
    """

    def test_build_llm_groq_usa_modelo_do_env(self):
        """_build_llm('groq') deve usar GROQ_MODEL do env quando model=None."""
        with patch.dict(os.environ, {"GROQ_MODEL": "openai/gpt-oss-120b", "GROQ_API_KEY": "fake"}):
            with patch("langchain_groq.ChatGroq") as mock_groq:
                from app.classifier import _build_llm
                _build_llm(provider="groq")
                mock_groq.assert_called_once()
                call_kwargs = mock_groq.call_args.kwargs
                assert call_kwargs["model"] == "openai/gpt-oss-120b"

    def test_build_llm_groq_com_override_de_modelo(self):
        """_build_llm('groq', model='llama-3.3-70b') deve usar o modelo informado."""
        with patch.dict(os.environ, {"GROQ_MODEL": "openai/gpt-oss-120b", "GROQ_API_KEY": "fake"}):
            with patch("langchain_groq.ChatGroq") as mock_groq:
                from app.classifier import _build_llm
                _build_llm(provider="groq", model="llama-3.3-70b")
                call_kwargs = mock_groq.call_args.kwargs
                assert call_kwargs["model"] == "llama-3.3-70b"

    def test_build_llm_provider_invalido_levanta_erro(self):
        """Provider desconhecido deve levantar ValueError."""
        from app.classifier import _build_llm
        with pytest.raises(ValueError, match="nao suportado"):
            _build_llm(provider="openai")

    def test_resolve_llm_sem_override_retorna_singleton(self):
        """
        _resolve_llm() sem provider deve retornar o singleton cacheado.
        Garante zero regressao: requisicoes sem header continuam no fluxo original.
        """
        import app.classifier as clf
        fake_llm = MagicMock()
        clf._llm = fake_llm
        try:
            result = clf._resolve_llm(provider=None, model=None)
            assert result is fake_llm
        finally:
            clf._llm = None

    def test_resolve_llm_com_provider_cria_instancia_nova(self):
        """
        _resolve_llm('groq') deve criar um LLM novo (descartavel),
        independente do singleton atual.
        """
        import app.classifier as clf
        fake_singleton = MagicMock()
        clf._llm = fake_singleton
        try:
            with patch.dict(os.environ, {"GROQ_API_KEY": "fake"}):
                with patch("langchain_groq.ChatGroq") as mock_groq:
                    mock_groq.return_value = MagicMock()
                    result = clf._resolve_llm(provider="groq", model=None)
                    assert result is not fake_singleton
                    mock_groq.assert_called_once()
        finally:
            clf._llm = None


# ---------------------------------------------------------------------------
# Bloco 2 - E4-06: TicketInput aceita os novos campos
# ---------------------------------------------------------------------------

class TestTicketInputSchema:
    """Valida que o schema foi atualizado corretamente (E4-06)."""

    def test_ticket_sem_provider_e_valido(self):
        """Requisicoes sem llm_provider/llm_model devem continuar funcionando."""
        from app.schemas import TicketInput
        ticket = TicketInput(ticket_id="TKT-001", text="VPN nao conecta", source="manual")
        assert ticket.llm_provider is None
        assert ticket.llm_model is None

    def test_ticket_com_provider_groq(self):
        """Campo llm_provider deve aceitar 'groq' e llm_model um modelo especifico."""
        from app.schemas import TicketInput
        ticket = TicketInput(
            ticket_id="TKT-002",
            text="Impressora offline",
            source="webhook",
            llm_provider="groq",
            llm_model="llama-3.3-70b",
        )
        assert ticket.llm_provider == "groq"
        assert ticket.llm_model == "llama-3.3-70b"

    def test_ticket_com_provider_gemini_sem_modelo(self):
        """Provider informado sem modelo especifico - llm_model deve ser None."""
        from app.schemas import TicketInput
        ticket = TicketInput(
            ticket_id="TKT-003",
            text="Sem acesso ao sistema",
            source="email",
            llm_provider="gemini",
        )
        assert ticket.llm_provider == "gemini"
        assert ticket.llm_model is None


# ---------------------------------------------------------------------------
# Bloco 3 - E4-03: Logica de versionamento (mock do Qdrant)
# ---------------------------------------------------------------------------

class TestRAGVersionamento:
    """
    Testa a logica de versionamento e soft invalidation (E4-03) sem Qdrant real.
    Mocka o qdrant_client para verificar quais metodos sao chamados.
    """

    @patch("app.rag.qdrant_client")
    def test_get_current_version_retorna_zero_se_nao_existe(self, mock_client):
        """Documento nunca indexado deve retornar versao 0."""
        mock_client.scroll.return_value = ([], None)
        from app.rag import _get_current_version
        assert _get_current_version("novo_doc.md") == 0

    @patch("app.rag.qdrant_client")
    def test_get_current_version_retorna_versao_atual(self, mock_client):
        """Documento com versao 3 ativa deve retornar 3."""
        ponto = MagicMock()
        ponto.payload = {"source": "manual_vpn.md", "version": 3, "is_active": True}
        mock_client.scroll.return_value = ([ponto], None)
        from app.rag import _get_current_version
        assert _get_current_version("manual_vpn.md") == 3

    @patch("app.rag.qdrant_client")
    def test_deactivate_chama_set_payload_nao_delete(self, mock_client):
        """
        Soft invalidation deve chamar set_payload com is_active=False usando
        FilterSelector - NAO deve chamar delete (corrige o bug original).
        """
        from app.rag import _deactivate_current_version
        from qdrant_client.models import FilterSelector
        _deactivate_current_version("manual_vpn.md")
        mock_client.set_payload.assert_called_once()
        call_kwargs = mock_client.set_payload.call_args.kwargs
        assert call_kwargs["payload"] == {"is_active": False}
        assert isinstance(call_kwargs["points"], FilterSelector)
        mock_client.delete.assert_not_called()

    @patch("app.rag.embeddings_model")
    @patch("app.rag.qdrant_client")
    def test_primeira_ingestao_salva_version_1(self, mock_client, mock_emb):
        """
        Primeira ingestao:
        - Nao chama set_payload (nada a desativar)
        - Salva chunks com is_active=True e version=1
        """
        import tempfile
        mock_client.scroll.return_value = ([], None)
        mock_emb.embed_query.return_value = [0.0] * 3072

        with tempfile.NamedTemporaryFile(
            suffix=".txt", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write("Conteudo do runbook de teste para primeira ingestao.")
            tmp_path = f.name

        try:
            from app.rag import ingest_document
            result = ingest_document(tmp_path)
        finally:
            os.unlink(tmp_path)

        mock_client.set_payload.assert_not_called()
        mock_client.upsert.assert_called_once()
        primeiro_payload = mock_client.upsert.call_args.kwargs["points"][0].payload
        assert primeiro_payload["is_active"] is True
        assert primeiro_payload["version"] == 1
        assert "created_at" in primeiro_payload
        assert result["version"] == 1

    @patch("app.rag.embeddings_model")
    @patch("app.rag.qdrant_client")
    def test_segunda_ingestao_incrementa_versao_e_invalida_anterior(self, mock_client, mock_emb):
        """
        Segunda ingestao:
        - Deve chamar set_payload para marcar v1 como is_active=False
        - Novos chunks devem ter version=2 e is_active=True
        """
        import tempfile
        ponto_v1 = MagicMock()
        ponto_v1.payload = {"source": "runbook.txt", "version": 1, "is_active": True}
        mock_client.scroll.return_value = ([ponto_v1], None)
        mock_emb.embed_query.return_value = [0.0] * 3072

        with tempfile.NamedTemporaryFile(
            suffix=".txt", mode="w", delete=False, encoding="utf-8", prefix="runbook"
        ) as f:
            f.write("Versao 2 do runbook, com passos atualizados.")
            tmp_path = f.name

        try:
            from app.rag import ingest_document
            result = ingest_document(tmp_path)
        finally:
            os.unlink(tmp_path)

        mock_client.set_payload.assert_called_once()
        novo_payload = mock_client.upsert.call_args.kwargs["points"][0].payload
        assert novo_payload["version"] == 2
        assert novo_payload["is_active"] is True
        assert result["version"] == 2

    @patch("app.rag.embeddings_model")
    @patch("app.rag.qdrant_client")
    def test_search_inclui_filtro_is_active_true(self, mock_client, mock_emb):
        """
        search_knowledge_base deve sempre passar query_filter com is_active=True,
        garantindo que versoes obsoletas sejam invisiveis para o agente.
        """
        from qdrant_client.models import Filter
        mock_emb.embed_query.return_value = [0.0] * 3072
        mock_hit = MagicMock()
        mock_hit.score = 0.9
        mock_hit.payload = {
            "text": "texto do chunk", "source": "manual.md",
            "version": 2, "created_at": "2026-09-18T10:00:00+00:00",
        }
        mock_client.query_points.return_value.points = [mock_hit]

        from app.rag import search_knowledge_base
        results = search_knowledge_base("VPN nao conecta", top_k=3)

        call_kwargs = mock_client.query_points.call_args.kwargs
        assert "query_filter" in call_kwargs, "search_knowledge_base deve passar query_filter"
        filtro = call_kwargs["query_filter"]
        assert isinstance(filtro, Filter)
        chaves = [c.key for c in filtro.must]
        assert "is_active" in chaves, "Filtro is_active=True deve estar presente na busca"
        assert results[0]["version"] == 2
        assert results[0]["created_at"] is not None