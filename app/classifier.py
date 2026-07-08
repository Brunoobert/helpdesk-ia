import json
import os
import time
from typing import Any

from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.prompts import CLASSIFY_SYSTEM_PROMPT
from app.schemas import ClassificationResult, TicketInput
from sqlalchemy.orm import Session
from langfuse.callback import CallbackHandler

load_dotenv()

_llm: BaseChatModel | None = None


class LLMUnavailableError(Exception):
    """Raised when the LLM API is unavailable or times out."""


def _get_langfuse_handler() -> CallbackHandler | None:
    """Retorna o handler do Langfuse se as credenciais estiverem no ambiente."""
    if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
        return CallbackHandler(
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
            host=os.getenv("LANGFUSE_HOST", "http://localhost:3000")
        )
    return None


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


def _invoke_llm(text: str, context: str = "", callbacks: list = None) -> tuple[str, int]:
    llm = _get_llm()
    
    human_text = f"Chamado do usuário:\n{text}"
    if context:
        human_text += f"\n\n--- CONTEXTO DA BASE DE CONHECIMENTO ---\n{context}"
        
    config = {}
    if callbacks:
        config["callbacks"] = callbacks
        
    response = llm.invoke(
        [
            SystemMessage(content=CLASSIFY_SYSTEM_PROMPT),
            HumanMessage(content=human_text),
        ],
        config=config
    )
    
    # Tenta extrair quantidade total de tokens consumidos
    tokens = 0
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        tokens = response.usage_metadata.get("total_tokens", 0)
    elif hasattr(response, "response_metadata") and "token_usage" in response.response_metadata:
        token_usage = response.response_metadata["token_usage"]
        if isinstance(token_usage, dict):
            tokens = token_usage.get("total_tokens", 0)
            
    return _message_content_to_str(response.content).strip(), tokens


def _clean_json_text(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def classify_ticket(ticket: TicketInput, db: Session = None) -> ClassificationResult:
    start = time.time()
    
    rag_context = ""
    rag_used = False
    
    # 1. Busca na Base de Conhecimento (RAG)
    try:
        from app.rag import search_knowledge_base
        results = search_knowledge_base(ticket.text, top_k=2)
        
        docs = []
        for r in results:
            # Filtra resultados pouco relevantes (ajuste fino para Gemini)
            if r["score"] > 0.50:
                docs.append(f"Fonte: {r['source']}\nConteúdo: {r['text']}")
        
        if docs:
            rag_context = "\n\n".join(docs)
            rag_used = True
    except Exception as e:
        print(f"Aviso: Erro ao buscar na base de conhecimento (RAG ignorado): {e}")

    # 2. Configura handler opcional do Langfuse
    handler = _get_langfuse_handler()
    callbacks = [handler] if handler else None

    # 3. Envia para o LLM classificar
    try:
        raw_text, tokens_used = _invoke_llm(ticket.text, context=rag_context, callbacks=callbacks)
    except Exception as exc:
        raise LLMUnavailableError("LLM API indisponivel") from exc

    elapsed_ms = int((time.time() - start) * 1000)
    print(f"DEBUG: Raw LLM response: {repr(raw_text)}")
    cleaned_text = _clean_json_text(raw_text)
    raw = json.loads(cleaned_text)

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
        rag_context_used=rag_used,
        processing_ms=elapsed_ms,
    )
