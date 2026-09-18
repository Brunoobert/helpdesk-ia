import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, Integer, Numeric, DateTime
from app.database import Base

class TicketLogModel(Base):
    __tablename__ = "ticket_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_id = Column(String(100), nullable=False)
    input_text = Column(Text, nullable=False)
    category = Column(String(255), nullable=False)
    urgency = Column(String(20), nullable=False)
    suggested_action = Column(Text, nullable=True)
    auto_resolved = Column(Boolean, default=False)
    correct_classification = Column(Boolean, nullable=True) # Campo para feedback manual futuro
    tokens_used = Column(Integer, default=0)
    cost_usd = Column(Numeric(10, 6), default=0.0)
    processing_ms = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
