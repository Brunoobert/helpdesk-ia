from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional
from datetime import datetime
import yaml
from pathlib import Path

config_path = Path(__file__).parent.parent / "config" / "categorias.yml"
with open(config_path, "r", encoding="utf-8") as f:
    _categorias_data = yaml.safe_load(f)
VALID_CATEGORIES = {item["path"] for item in _categorias_data["categorias"]}


class TicketInput(BaseModel):
    ticket_id: str
    text: str
    source: Literal["email", "webhook", "manual"]


class ClassificationResult(BaseModel):
    ticket_id: str
    category: str
    urgency: Literal["Alta", "Média", "Baixa"]
    suggested_action: str
    auto_resolve: bool
    confidence: float = Field(ge=0.0, le=1.0)
    rag_context_used: bool = False
    processing_ms: int

    @field_validator("category")
    @classmethod
    def check_category(cls, v: str) -> str:
        if v not in VALID_CATEGORIES:
            raise ValueError(f"Categoria inválida. Valores esperados: {', '.join(sorted(VALID_CATEGORIES))}")
        return v


class HealthResponse(BaseModel):
    status: str
    services: dict