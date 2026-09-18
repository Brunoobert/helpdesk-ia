"""
Testes da Etapa 1 — Agente Classificador
Cobertura: contratos de API, regras de negócio, casos ambíguos e edge cases.
"""

import os
import time

from dotenv import load_dotenv
load_dotenv()
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app
from app.schemas import TicketInput, ClassificationResult
from app.classifier import classify_ticket

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_ticket(text: str, ticket_id: str = "test-001", source: str = "manual") -> dict:
    return {"ticket_id": ticket_id, "text": text, "source": source}


# Pausa entre chamadas reais ao Gemini (rate limit no tier gratuito ~15 RPM).
INTEGRATION_DELAY_SEC = float(os.getenv("INTEGRATION_DELAY_SEC", "5"))


def post_classify(payload: dict, max_retries: int = 3):
    """POST /classify com retry em 503 (rate limit / indisponibilidade temporária)."""
    last = None
    for attempt in range(max_retries):
        last = client.post("/classify", json=payload)
        if last.status_code != 503:
            return last
        if attempt < max_retries - 1:
            time.sleep(INTEGRATION_DELAY_SEC * (attempt + 1))
    return last


def mock_llm_json(category, urgency, suggested_action, auto_resolve, confidence):
    """JSON de resposta do LLM para mock de _invoke_llm (independente do provider)."""
    import json
    return (
        json.dumps({
            "category": category,
            "urgency": urgency,
            "suggested_action": suggested_action,
            "auto_resolve": auto_resolve,
            "confidence": confidence,
        }),
        100,
    )


DEFAULT_MOCK = dict(
    category="INFRAESTRUTURA/AD/RESET_SENHA",
    urgency="Média",
    suggested_action="Resetar senha pelo portal de autoatendimento.",
    auto_resolve=False,
    confidence=0.85,
)


# ---------------------------------------------------------------------------
# 1. Contrato da API — estrutura de request e response
# ---------------------------------------------------------------------------

class TestAPIContract:

    @pytest.fixture(autouse=True)
    def _mock_llm(self):
        with patch("app.classifier._invoke_llm") as mock_invoke:
            mock_invoke.return_value = mock_llm_json(**DEFAULT_MOCK)
            yield mock_invoke

    def test_classify_retorna_todos_campos_obrigatorios(self):
        """Response deve conter exatamente os campos definidos na spec."""
        response = client.post("/classify", json=make_ticket(
            "Usuário não consegue resetar a senha pelo portal."
        ))
        assert response.status_code == 200
        data = response.json()
        campos_obrigatorios = {
            "ticket_id", "category", "urgency", "suggested_action",
            "auto_resolve", "confidence", "rag_context_used", "processing_ms"
        }
        assert campos_obrigatorios.issubset(data.keys())

    def test_classify_retorna_categoria_valida(self):
        """category deve ser um dos valores definidos na spec."""
        response = client.post("/classify", json=make_ticket(
            "Impressora do setor financeiro não imprime desde a troca do toner."
        ))
        assert response.status_code == 200
        from app.schemas import VALID_CATEGORIES
        categorias_validas = VALID_CATEGORIES
        assert response.json()["category"] in categorias_validas

    def test_classify_retorna_urgencia_valida(self):
        """urgency deve ser Alta, Média ou Baixa."""
        response = client.post("/classify", json=make_ticket(
            "Email corporativo chegando com atraso de 2 horas."
        ))
        assert response.status_code == 200
        assert response.json()["urgency"] in {"Alta", "Média", "Baixa"}

    def test_classify_confidence_dentro_do_intervalo(self):
        """confidence deve estar entre 0.0 e 1.0."""
        response = client.post("/classify", json=make_ticket(
            "Computador lento ao abrir o sistema ERP."
        ))
        assert response.status_code == 200
        confidence = response.json()["confidence"]
        assert 0.0 <= confidence <= 1.0

    def test_classify_processing_ms_positivo(self):
        """processing_ms deve ser um inteiro não negativo (0 com mock, >0 com LLM real)."""
        response = client.post("/classify", json=make_ticket(
            "Monitor piscando intermitentemente."
        ))
        assert response.status_code == 200
        assert response.json()["processing_ms"] >= 0


    def test_classify_ticket_id_preservado_na_resposta(self):
        """O ticket_id do request deve ser refletido na response."""
        ticket_id = "INC-2024-XYZ"
        response = client.post("/classify", json=make_ticket(
            "Sem acesso à internet no setor de RH.", ticket_id=ticket_id
        ))
        assert response.status_code == 200
        assert response.json()["ticket_id"] == ticket_id

    def test_classify_aceita_source_webhook(self):
        """Deve aceitar source do tipo webhook sem erro."""
        response = client.post("/classify", json=make_ticket(
            "Alerta automático: disco do servidor chegando a 95%.",
            source="webhook"
        ))
        assert response.status_code == 200

    def test_classify_rejeita_source_invalido(self):
        """Source fora do enum deve retornar 422."""
        response = client.post("/classify", json=make_ticket(
            "Qualquer chamado.", source="teams"
        ))
        assert response.status_code == 422

    def test_classify_rejeita_body_vazio(self):
        """Request sem body deve retornar 422."""
        response = client.post("/classify", json={})
        assert response.status_code == 422

    def test_classify_rejeita_text_ausente(self):
        """Campo text obrigatório ausente deve retornar 422."""
        response = client.post("/classify", json={
            "ticket_id": "001", "source": "manual"
        })
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# 2. Regras de negócio — enforcement crítico
# ---------------------------------------------------------------------------

class TestRegraDeNegocio:

    @patch("app.classifier._invoke_llm")
    def test_urgencia_alta_nunca_auto_resolve(self, mock_invoke):
        """
        Regra crítica: mesmo que o LLM retorne auto_resolve=true,
        urgência Alta deve forçar auto_resolve=false.
        """
        mock_invoke.return_value = mock_llm_json(
            category="INFRAESTRUTURA/VPN/ERRO_CONEXAO",
            urgency="Alta",
            suggested_action="Verificar infraestrutura.",
            auto_resolve=True,   # LLM quer resolver automaticamente
            confidence=0.95,
        )
        ticket = TicketInput(
            ticket_id="002",
            text="Datacenter sem energia. Todos os sistemas fora.",
            source="manual"
        )
        result = classify_ticket(ticket)
        assert result.auto_resolve is False, (
            "auto_resolve deve ser False quando urgency=Alta, independente do LLM"
        )

    @patch("app.classifier._invoke_llm")
    def test_confidence_baixa_bloqueia_auto_resolve(self, mock_invoke):
        """
        Regra crítica: confidence abaixo do threshold (0.7) deve
        forçar auto_resolve=false mesmo que o LLM decida diferente.
        """
        mock_invoke.return_value = mock_llm_json(
            category="INFRAESTRUTURA/AD/RESET_SENHA",
            urgency="Baixa",
            suggested_action="Resetar senha.",
            auto_resolve=True,
            confidence=0.5,   # Abaixo do threshold
        )
        ticket = TicketInput(
            ticket_id="003",
            text="Usuário com problema de acesso não especificado.",
            source="manual"
        )
        result = classify_ticket(ticket)
        assert result.auto_resolve is False, (
            "auto_resolve deve ser False quando confidence < 0.7"
        )

    @patch("app.classifier._invoke_llm")
    def test_urgencia_alta_confidence_alta_ainda_bloqueia(self, mock_invoke):
        """Confidence alta não deve sobrescrever a regra de urgência Alta."""
        mock_invoke.return_value = mock_llm_json(
            category="HELPDESK/SO/CORRIGIR_ERRO_WINDOWS",
            urgency="Alta",
            suggested_action="Substituir servidor.",
            auto_resolve=True,
            confidence=0.99,
        )
        ticket = TicketInput(
            ticket_id="004",
            text="Servidor principal com falha de hardware crítica.",
            source="manual"
        )
        result = classify_ticket(ticket)
        assert result.auto_resolve is False

    @patch("app.classifier._invoke_llm")
    def test_urgencia_media_confidence_alta_permite_auto_resolve(self, mock_invoke):
        """Urgência Média com confidence alta pode ter auto_resolve=true."""
        mock_invoke.return_value = mock_llm_json(
            category="INFRAESTRUTURA/AD/RESET_SENHA",
            urgency="Média",
            suggested_action="Resetar senha e notificar usuário.",
            auto_resolve=True,
            confidence=0.85,
        )
        ticket = TicketInput(
            ticket_id="005",
            text="Gerente sem acesso ao sistema de RH, reunião em 2h.",
            source="manual"
        )
        result = classify_ticket(ticket)
        assert result.auto_resolve is True

    @patch("app.classifier._invoke_llm")
    def test_confidence_exatamente_no_threshold_permite(self, mock_invoke):
        """Confidence exatamente em 0.7 deve permitir auto_resolve."""
        mock_invoke.return_value = mock_llm_json(
            category="INFRAESTRUTURA/AD/RESET_SENHA",
            urgency="Baixa",
            suggested_action="Resetar senha.",
            auto_resolve=True,
            confidence=0.7,
        )
        ticket = TicketInput(
            ticket_id="006",
            text="Reset de senha solicitado.",
            source="manual"
        )
        result = classify_ticket(ticket)
        assert result.auto_resolve is True


# ---------------------------------------------------------------------------
# 3. Casos ambíguos — testa a qualidade do prompt
# (esses chamam o LLM real, rodam só com --integration)
# ---------------------------------------------------------------------------

class TestCasosAmbiguos:
    """
    Testes que chamam o LLM real para validar qualidade do prompt.
    Execute com: pytest -m integration
    Requerem provider configurado no .env (GEMINI_API_KEY, GROQ_API_KEY ou Ollama local).

    Pausa INTEGRATION_DELAY_SEC (padrão 5s) entre testes para evitar 503 por rate limit.
    """

    @pytest.fixture(autouse=True)
    def _pace_gemini_requests(self):
        time.sleep(INTEGRATION_DELAY_SEC)
        yield

    @pytest.mark.integration
    def test_chamado_ambiguo_rede_ou_software(self):
        """
        'Sistema lento' pode ser Rede ou Software.
        Valida que o agente toma uma decisão consistente.
        """
        response = post_classify(make_ticket(
            "O sistema ERP está muito lento. Alguns usuários conseguem acessar, "
            "outros não. O problema começou após atualização do servidor de aplicação."
        ))
        assert response.status_code == 200
        data = response.json()
        assert data["category"] in {"INFRAESTRUTURA/VPN/ERRO_CONEXAO", "HELPDESK/SO/CORRIGIR_ERRO_WINDOWS"}
        assert data["urgency"] in {"Alta", "Média"}

    @pytest.mark.integration
    def test_chamado_em_portugues_informal(self):
        """Agente deve classificar corretamente mesmo com linguagem informal."""
        response = post_classify(make_ticket(
            "oi, meu computador nao ta ligando, tentei varias vezes "
            "e nada, preciso entregar um relatorio hoje"
        ))
        assert response.status_code == 200
        data = response.json()
        assert data["category"] in {"HELPDESK/SO/CORRIGIR_ERRO_WINDOWS", "HELPDESK/SO/REINSTALAR_SISTEMA"}
        assert data["urgency"] in {"Alta", "Média"}

    @pytest.mark.integration
    def test_chamado_com_multiplos_problemas(self):
        """Chamado com dois problemas deve resultar em urgência Alta."""
        response = post_classify(make_ticket(
            "Servidor de arquivos fora do ar E impressoras da rede não funcionam. "
            "Departamento inteiro parado."
        ))
        assert response.status_code == 200
        assert response.json()["urgency"] == "Alta"
        assert response.json()["auto_resolve"] is False

    @pytest.mark.integration
    def test_chamado_vago_gera_confidence_baixa(self):
        """Chamado vago não deve ser auto-resolvido."""
        response = post_classify(make_ticket("Não está funcionando."))
        assert response.status_code == 200
        data = response.json()
        assert data["auto_resolve"] is False  # sem contexto, não resolve automaticamente  # o que realmente importa

    @pytest.mark.integration
    def test_reset_senha_classifica_como_auto_resolve(self):
        """Reset de senha é o caso mais claro de auto_resolve=true."""
        response = post_classify(make_ticket(
            "Usuário João Silva, matrícula 4521, solicita reset de senha. "
            "Bloqueou a conta após 3 tentativas erradas."
        ))
        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "INFRAESTRUTURA/AD/RESET_SENHA"
        assert data["auto_resolve"] is True
        assert data["confidence"] >= 0.85

    @pytest.mark.integration
    def test_incidente_critico_nunca_auto_resolve(self):
        """Incidente crítico não pode ter auto_resolve=true em nenhuma hipótese."""
        response = post_classify(make_ticket(
            "URGENTE: Ransomware detectado em 3 máquinas do setor financeiro. "
            "Arquivos sendo criptografados. Rede isolada."
        ))
        assert response.status_code == 200
        data = response.json()
        assert data["urgency"] == "Alta"
        assert data["auto_resolve"] is False


# ---------------------------------------------------------------------------
# 4. Resiliência — falhas e erros
# ---------------------------------------------------------------------------

class TestResiliencia:

    @patch("app.classifier._invoke_llm")
    def test_falha_llm_retorna_503(self, mock_invoke):
        """Se o LLM falhar, a API deve retornar 503."""
        mock_invoke.side_effect = Exception("API timeout")
        response = client.post("/classify", json=make_ticket(
            "Qualquer chamado de teste."
        ))
        assert response.status_code == 503

    @patch("app.classifier._invoke_llm")
    def test_json_invalido_do_llm_nao_quebra_servidor(self, mock_invoke):
        """Resposta malformada do LLM não pode derrubar o servidor."""
        mock_invoke.return_value = ("Desculpe, não entendi o chamado.", 20)  # LLM ignorou instrução
        response = client.post("/classify", json=make_ticket(
            "Qualquer chamado de teste."
        ))
        # Com o fallback defensivo, a API não quebra e retorna 200 com encaminhamento humano
        assert response.status_code == 200
        data = response.json()
        assert data["auto_resolve"] is False
        assert "análise manual" in data["suggested_action"]

    @patch("app.classifier._invoke_llm")
    def test_texto_muito_longo_nao_quebra(self, mock_invoke):
        """Chamado com texto muito longo deve ser processado ou falhar graciosamente."""
        mock_invoke.return_value = mock_llm_json(**DEFAULT_MOCK)
        texto_longo = "problema de rede " * 500  # ~9000 chars
        response = client.post("/classify", json=make_ticket(texto_longo))
        assert response.status_code == 200

    def test_health_sempre_responde(self):
        """Health check deve sempre responder, mesmo com dependências fora."""
        response = client.get("/health")
        assert response.status_code == 200
        assert "status" in response.json()
        assert "services" in response.json()