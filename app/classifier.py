import json
import time
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
from app.schemas import TicketInput, ClassificationResult
from app.prompts import CLASSIFY_SYSTEM_PROMPT

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def classify_ticket(ticket: TicketInput) -> ClassificationResult:
    start = time.time()

    response = client.models.generate_content(
        model=os.getenv("LLM_MODEL", "gemini-2.0-flash"),
        contents=ticket.text,
        config=types.GenerateContentConfig(
            system_instruction=CLASSIFY_SYSTEM_PROMPT,
            temperature=0,
            response_mime_type="application/json",
        ),
    )

    elapsed_ms = int((time.time() - start) * 1000)
    raw = json.loads(response.text)

    raw = json.loads(response.text)

# Enforcement das regras de negócio — nunca confiar só no LLM
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