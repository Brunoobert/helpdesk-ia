import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from app.classifier import LLMUnavailableError, classify_ticket
from app.schemas import ClassificationResult, HealthResponse, TicketInput

load_dotenv()

app = FastAPI(title="Help Desk IA")


@app.post("/classify", response_model=ClassificationResult)
def classify(ticket: TicketInput) -> ClassificationResult:
    try:
        return classify_ticket(ticket)
    except LLMUnavailableError:
        raise HTTPException(status_code=503, detail="LLM API indisponível")
    except Exception:
        raise HTTPException(status_code=500, detail="Erro interno")


def _llm_api_status() -> str:
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    if provider == "groq":
        return "ok" if os.getenv("GROQ_API_KEY") else "error"
    if provider == "ollama":
        return "ok"
    return "ok" if os.getenv("GEMINI_API_KEY") else "error"


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    services = {
        "qdrant": "ok",
        "llm_api": _llm_api_status(),
        "langfuse": "ok" if os.getenv("LANGFUSE_SECRET_KEY") else "error",
        "database": "ok" if os.getenv("DATABASE_URL") else "error",
    }
    status = "ok" if all(v == "ok" for v in services.values()) else "degraded"
    return HealthResponse(status=status, services=services)
