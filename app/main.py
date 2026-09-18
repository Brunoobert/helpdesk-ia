import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Header
import shutil
from pathlib import Path
from app.rag import ingest_document

from app.database import Base, engine, get_db
from app.models import TicketLogModel  # noqa: F401 – registra o modelo no Base.metadata
from sqlalchemy.orm import Session

from app.classifier import LLMUnavailableError, classify_ticket
from app.schemas import ClassificationResult, HealthResponse, TicketInput

load_dotenv()

app = FastAPI(title="Help Desk IA")


@app.on_event("startup")
def on_startup():
    # Cria as tabelas do banco se não existirem no startup da aplicação
    Base.metadata.create_all(bind=engine)


@app.post("/classify", response_model=ClassificationResult)
def classify(
    ticket: TicketInput,
    db: Session = Depends(get_db),
    x_llm_provider: Optional[str] = Header(default=None, alias="X-LLM-Provider"),
    x_llm_model: Optional[str] = Header(default=None, alias="X-LLM-Model"),
) -> ClassificationResult:
    """
    Classifica um chamado de suporte.

    Suporta override dinâmico de modelo (E4-06) via headers opcionais:
    - X-LLM-Provider: "groq" | "gemini" | "ollama"
    - X-LLM-Model: nome específico do modelo dentro do provider

    Os headers têm prioridade sobre os campos `llm_provider`/`llm_model` do payload.
    Se nenhum for informado, usa o provider configurado no .env (comportamento padrão).
    """
    # Headers têm prioridade sobre os campos equivalentes no payload
    if x_llm_provider:
        ticket.llm_provider = x_llm_provider
    if x_llm_model:
        ticket.llm_model = x_llm_model

    try:
        return classify_ticket(ticket, db)
    except LLMUnavailableError:
        raise HTTPException(status_code=503, detail="LLM API indisponível")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")


@app.post("/ingest")
async def ingest(file: UploadFile = File(...)):
    if not (file.filename.lower().endswith(".pdf") or file.filename.lower().endswith(".md") or file.filename.lower().endswith(".txt")):
        raise HTTPException(status_code=400, detail="Formato não suportado. Envie .pdf, .md ou .txt.")
    
    temp_dir = Path("temp_docs")
    temp_dir.mkdir(exist_ok=True)
    file_path = temp_dir / file.filename
    
    try:
        # Salva o arquivo temporariamente
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Chama a função do RAG para ingerir o documento
        ingest_document(str(file_path))
        
        return {"message": f"Arquivo '{file.filename}' processado e salvo na base de conhecimento com sucesso."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro durante a ingestão: {str(e)}")
    finally:
        # Limpa o arquivo temporário
        if file_path.exists():
            file_path.unlink()


def _llm_api_status() -> str:
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    if provider == "groq":
        return "ok" if os.getenv("GROQ_API_KEY") else "error"
    if provider == "ollama":
        return "ok"
    return "ok" if os.getenv("GEMINI_API_KEY") else "error"


def _qdrant_status() -> str:
    import httpx
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    try:
        response = httpx.get(f"{qdrant_url}/readyz", timeout=2.0)
        return "ok" if response.status_code == 200 else "error"
    except Exception:
        return "error"


def _database_status() -> str:
    from sqlalchemy import text
    from app.database import SessionLocal
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return "ok"
    except Exception:
        return "error"


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    services = {
        "qdrant": _qdrant_status(),
        "llm_api": _llm_api_status(),
        "langfuse": "ok" if os.getenv("LANGFUSE_SECRET_KEY") else "error",
        "database": _database_status(),
    }
    status = "ok" if all(v == "ok" for v in services.values()) else "degraded"
    return HealthResponse(status=status, services=services)
