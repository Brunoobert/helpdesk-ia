from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime


class TicketInput(BaseModel):
    ticket_id: str
    text: str
    source: Literal["email", "webhook", "manual"]


class ClassificationResult(BaseModel):
    ticket_id: str
    category: Literal["Rede", "Acesso", "Hardware", "Software", "Outro"]
    urgency: Literal["Alta", "Média", "Baixa"]
    suggested_action: str
    auto_resolve: bool
    confidence: float = Field(ge=0.0, le=1.0)
    rag_context_used: bool = False
    processing_ms: int


class HealthResponse(BaseModel):
    status: str
    services: dict