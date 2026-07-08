import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.classifier import classify_ticket
from app.schemas import TicketInput
from app.models import TicketLogModel

@pytest.fixture
def db_session():
    """Cria uma base SQLite temporária e limpa para cada execução de teste."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()

def test_ticket_log_saved_in_database(db_session):
    """
    Verifica se a chamada ao classify_ticket de fato insere os registros
    corretamente no banco de dados quando passamos a Session do SQLAlchemy.
    """
    ticket = TicketInput(
        ticket_id="TKT-TEST-DB-001",
        text="Gostaria de resetar minha senha de rede",
        source="manual"
    )
    
    with patch("app.classifier.search_knowledge_base") as mock_rag, \
         patch("app.classifier._invoke_llm") as mock_llm:
         
        mock_rag.return_value = []
        mock_llm.return_value = (
            '{"category": "INFRAESTRUTURA/AD/RESET_SENHA", "urgency": "Baixa", "suggested_action": "Acesse aka.ms/ssprsetup", "auto_resolve": true, "confidence": 1.0}',
            150  # Mock de 150 tokens consumidos
        )
        
        # Executa a classificação passando a sessão de testes do banco
        result = classify_ticket(ticket, db=db_session)
        
        assert result.ticket_id == "TKT-TEST-DB-001"
        assert result.auto_resolve is True
        
        # Recupera o registro inserido na tabela 'ticket_logs'
        db_log = db_session.query(TicketLogModel).filter_by(ticket_id="TKT-TEST-DB-001").first()
        
        assert db_log is not None, "O log deveria ter sido salvo no banco de dados"
        assert db_log.category == "INFRAESTRUTURA/AD/RESET_SENHA"
        assert db_log.urgency == "Baixa"
        assert db_log.auto_resolved is True
        assert db_log.suggested_action == "Acesse aka.ms/ssprsetup"
        assert db_log.tokens_used == 150
        assert db_log.processing_ms > 0
