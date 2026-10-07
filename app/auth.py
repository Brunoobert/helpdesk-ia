import os
import secrets
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(_api_key_header)) -> str:
    """
    Dependencia do FastAPI que valida o header X-API-Key (ADR-006).

    - GET /health permanece publico (nao injeta esta dependencia).
    - Todos os endpoints operacionais (POST /classify, POST /ingest)
      devem declarar Depends(verify_api_key).
    """
    expected_key = os.getenv("API_AUTH_KEY")

    if not expected_key:
        raise HTTPException(
            status_code=500,
            detail="API_AUTH_KEY nao configurada no servidor. Verifique o .env.",
        )

    # Mitigacao de Timing Attack: comparacao em tempo constante
    if not api_key or not secrets.compare_digest(api_key, expected_key):
        raise HTTPException(
            status_code=401,
            detail="X-API-Key ausente ou invalida.",
        )

    return api_key
