import json
import os
import re
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
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    if public_key and secret_key:
        return CallbackHandler(
            public_key=public_key,
            secret_key=secret_key,
            host=os.getenv("LANGFUSE_HOST", "http://localhost:3000"),
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
    # Extrai estritamente a partir do primeiro '{' até o último '}'
    # Isso evita que blocos markdown internos no suggested_action confundam o parser
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return text[first_brace : last_brace + 1].strip()
    return text


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
    
    try:
        raw = json.loads(cleaned_text)
        if not isinstance(raw, dict):
            raw = {}
    except Exception as e:
        print(f"Aviso: LLM retornou texto que não é JSON ({e}). Aplicando fallback de segurança.")
        raw = {
            "category": "HELPDESK/SO/CORRIGIR_ERRO_WINDOWS",
            "urgency": "Média",
            "suggested_action": f"Mensagem não estruturada ou recusa do modelo: '{raw_text[:200]}'. Necessário análise manual do analista.",
            "auto_resolve": False,
            "confidence": 0.0,
        }

    # Validação e saneamento dos campos obrigatórios caso o LLM omita chaves (ex: prompt injection / jailbreak)
    category = raw.get("category", "HELPDESK/SO/CORRIGIR_ERRO_WINDOWS")
    urgency = raw.get("urgency", "Média")
    suggested_action = raw.get("suggested_action", "Não foi possível determinar a ação recomendada.")
    auto_resolve = bool(raw.get("auto_resolve", False))
    confidence = float(raw.get("confidence", 0.0))

    # Enforcement das regras de negocio: nunca confiar apenas no LLM.
    if urgency == "Alta" or confidence < float(os.getenv("AUTO_RESOLVE_CONFIDENCE_THRESHOLD", "0.7")):
        auto_resolve = False

    # 4. Grava histórico na tabela do Postgres (se a sessão do banco estiver disponível)
    if db:
        try:
            from app.models import TicketLogModel
            log = TicketLogModel(
                ticket_id=ticket.ticket_id,
                input_text=ticket.text,
                category=category,
                urgency=urgency,
                suggested_action=suggested_action,
                auto_resolved=auto_resolve,
                tokens_used=tokens_used,
                cost_usd=0.0, # Deixamos zerado; Langfuse cuidará de calcular o custo no painel
                processing_ms=elapsed_ms
            )
            db.add(log)
            db.commit()
            print(f"Log do ticket '{ticket.ticket_id}' salvo com sucesso no banco de dados.")
        except Exception as db_err:
            print(f"Aviso: Erro ao persistir ticket no banco de dados: {db_err}")
            db.rollback()

    return ClassificationResult(
        ticket_id=ticket.ticket_id,
        category=category,
        urgency=urgency,
        suggested_action=suggested_action,
        auto_resolve=auto_resolve,
        confidence=confidence,
        rag_context_used=rag_used,
        processing_ms=elapsed_ms,
    )
