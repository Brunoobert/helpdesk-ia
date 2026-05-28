import json
import os
import time
from typing import Any

from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.prompts import CLASSIFY_SYSTEM_PROMPT
from app.schemas import ClassificationResult, TicketInput

load_dotenv()

_llm: BaseChatModel | None = None


class LLMUnavailableError(Exception):
    """Raised when the LLM API is unavailable or times out."""


def _build_llm() -> BaseChatModel:
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()

    if provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0,
        )

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=os.getenv("OLLAMA_MODEL", "llama3.2"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            temperature=0,
        )

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            google_api_key=os.getenv("GEMINI_API_KEY"),
            temperature=0,
        )

    raise ValueError(f"LLM_PROVIDER nao suportado: {provider}")


def _get_llm() -> BaseChatModel:
    global _llm
    if _llm is None:
        _llm = _build_llm()
    return _llm


def _message_content_to_str(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and "text" in block:
                parts.append(block["text"])
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content)


def _invoke_llm(text: str) -> str:
    llm = _get_llm()
    response = llm.invoke(
        [
            SystemMessage(content=CLASSIFY_SYSTEM_PROMPT),
            HumanMessage(content=text),
        ]
    )
    return _message_content_to_str(response.content).strip()


def classify_ticket(ticket: TicketInput) -> ClassificationResult:
    start = time.time()

    try:
        raw_text = _invoke_llm(ticket.text)
    except Exception as exc:
        raise LLMUnavailableError("LLM API indisponivel") from exc

    elapsed_ms = int((time.time() - start) * 1000)
    raw = json.loads(raw_text)

    # Enforcement das regras de negocio: nunca confiar apenas no LLM.
    if raw.get("urgency") == "Alta":
        raw["auto_resolve"] = False
    if raw.get("confidence", 0) < float(os.getenv("AUTO_RESOLVE_CONFIDENCE_THRESHOLD", "0.7")):
        raw["auto_resolve"] = False

    return ClassificationResult(
        ticket_id=ticket.ticket_id,
        category=raw["category"],
        urgency=raw["urgency"],
        suggested_action=raw["suggested_action"],
        auto_resolve=raw["auto_resolve"],
        confidence=raw["confidence"],
        rag_context_used=False,
        processing_ms=elapsed_ms,
    )
