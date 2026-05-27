# 📋 Spec — Help Desk IA com RAG, n8n e AWS

> **Versão:** 1.0  
> **Status:** Em desenvolvimento  
> **Última atualização:** ___________

---

## 1. Visão do Produto

### O que é
Um agente de IA que recebe chamados de suporte, classifica urgência e categoria, consulta uma base de conhecimento interna (RAG) com runbooks e histórico de chamados resolvidos, e resolve automaticamente casos simples — com observabilidade completa de custo e performance.

### Problema que resolve
Chamados repetitivos consomem tempo do time de infra. Muitas resoluções já existem em runbooks e histórico, mas ficam em arquivos perdidos. O agente centraliza esse conhecimento e o aplica automaticamente.

### O que não é
- Não é um chatbot de atendimento ao cliente
- Não substitui analistas para chamados complexos
- Não treina modelos proprietários (usa LLMs via API)

---

## 2. Arquitetura

```
[Fonte do chamado]
  Email / Webhook / n8n
        │
        ▼
[Orquestrador — n8n]
  Recebe, formata e roteia
        │
        ▼
[Agente Python — FastAPI]
  Classifica + consulta RAG + decide ação
        │
   ┌────┴────┐
   ▼         ▼
[Qdrant]  [LLM API]
Vector DB  Gemini / Bedrock
        │
        ▼
[LangFuse]
  Observabilidade e custo
        │
        ▼
[Ação]
  Resolver automaticamente OU notificar humano
```

### Serviços e responsabilidades

| Serviço | Responsabilidade | Onde roda |
|---|---|---|
| FastAPI | API do agente | Docker / ECS |
| Qdrant | Banco vetorial para RAG | Docker / ECS |
| n8n | Orquestração de fluxos | Docker / ECS |
| LangFuse | Observabilidade de LLM | Docker / Cloud |
| PostgreSQL | Metadados e logs | Docker / RDS |
| S3 | Storage dos documentos | AWS |
| GitHub Actions | CI/CD | GitHub |

### Decisões de arquitetura

| Decisão | Escolha | Alternativa descartada | Motivo |
|---|---|---|---|
| Vector DB | Qdrant | Pinecone | Self-hosted, sem custo por requisição |
| Orquestração | n8n | Airflow | Já tenho experiência, mais visual |
| Observabilidade | LangFuse | Phoenix | Open source, self-hosted disponível |
| Cloud | AWS | GCP | Maior demanda no mercado BR |
| LLM | Gemini | Claude / OpenAI gpt-4o-mini| Custo-benefício, trocar por Bedrock no deploy |

---

## 3. Contratos de API

### `POST /classify`

Recebe o texto de um chamado e retorna classificação estruturada.

**Request**
```json
{
  "ticket_id": "string",
  "text": "string",
  "source": "email | webhook | manual"
}
```

**Response 200**
```json
{
  "ticket_id": "string",
  "category": "Rede | Acesso | Hardware | Software | Outro",
  "urgency": "Alta | Média | Baixa",
  "suggested_action": "string",
  "auto_resolve": true,
  "confidence": 0.95,
  "rag_context_used": true,
  "processing_ms": 1240
}
```

**Erros**
| Código | Motivo |
|---|---|
| 422 | Campo obrigatório ausente ou tipo inválido |
| 503 | LLM API indisponível |
| 500 | Erro interno |

---

### `POST /ingest`

Recebe um documento (PDF ou TXT) e indexa no banco vetorial.

**Request** — `multipart/form-data`
```
file: <arquivo PDF ou TXT>
doc_type: "runbook" | "policy" | "resolved_ticket"
tags: ["rede", "acesso"] (opcional)
```

**Response 200**
```json
{
  "doc_id": "string",
  "chunks_indexed": 42,
  "status": "success"
}
```

**Erros**
| Código | Motivo |
|---|---|
| 415 | Formato de arquivo não suportado |
| 413 | Arquivo maior que 10MB |
| 500 | Falha ao gerar embeddings |

---

### `GET /health`

Verifica se todos os serviços dependentes estão saudáveis.

**Response 200**
```json
{
  "status": "ok",
  "services": {
    "qdrant": "ok",
    "llm_api": "ok",
    "langfuse": "ok",
    "database": "ok"
  }
}
```

---

## 4. Schema de Dados

### Ticket (entrada)

```python
class TicketInput(BaseModel):
    ticket_id: str
    text: str                          # Descrição do chamado
    source: Literal["email", "webhook", "manual"]
```

### ClassificationResult (saída do agente)

```python
class ClassificationResult(BaseModel):
    ticket_id: str
    category: Literal["Rede", "Acesso", "Hardware", "Software", "Outro"]
    urgency: Literal["Alta", "Média", "Baixa"]
    suggested_action: str              # Texto livre com ação recomendada
    auto_resolve: bool                 # Se o agente pode resolver sozinho
    confidence: float                  # 0.0 a 1.0
    rag_context_used: bool             # Se consultou o vector DB
    processing_ms: int
```

### TicketLog (persiste no banco)

```python
class TicketLog(BaseModel):
    id: str
    ticket_id: str
    input_text: str
    category: str
    urgency: str
    suggested_action: str
    auto_resolved: bool
    correct_classification: Optional[bool]   # Feedback posterior
    tokens_used: int
    cost_usd: float
    processing_ms: int
    created_at: datetime
```

---

## 5. Comportamento do Agente

### Fluxo principal

```
1. Receber chamado (texto)
2. Buscar chunks similares no Qdrant (top 3)
3. Montar prompt com: instrução + contexto RAG + texto do chamado
4. Chamar LLM e obter ClassificationResult
5. Se auto_resolve = true E urgency != "Alta":
     → Executar ação automática
     → Logar como resolvido
6. Senão:
     → Retornar classificação para n8n
     → n8n notifica humano responsável
7. Persistir log no banco
8. Enviar trace para LangFuse
```

### Regras de negócio

| Condição | Comportamento |
|---|---|
| Urgência Alta | Nunca resolver automaticamente, sempre escalar |
| Confiança < 0.7 | Não resolver automaticamente, sinalizar para revisão |
| LLM API timeout | Retornar erro 503, não tentar classificação parcial |
| Nenhum chunk RAG encontrado | Classificar sem contexto, marcar `rag_context_used: false` |

### Ações automáticas suportadas (v1)

- Registrar resolução no log
- Simular reset de senha (logar ação, não integrar AD real na v1)
- Simular liberação de acesso (idem)
- Enviar notificação via n8n webhook

---

## 6. Observabilidade

### Métricas obrigatórias por requisição (LangFuse)

| Métrica | Tipo | Descrição |
|---|---|---|
| `tokens_input` | int | Tokens enviados ao LLM |
| `tokens_output` | int | Tokens recebidos do LLM |
| `cost_usd` | float | Custo calculado por requisição |
| `latency_ms` | int | Tempo total de processamento |
| `rag_chunks_retrieved` | int | Quantos chunks o RAG retornou |
| `auto_resolved` | bool | Se o agente resolveu sozinho |
| `confidence` | float | Score de confiança retornado |

### Alertas (fase AWS)

| Alerta | Condição |
|---|---|
| Custo diário alto | Custo acumulado > $2 USD/dia |
| Latência alta | p95 > 5s nas últimas 1h |
| Taxa de acerto baixa | Acerto manual < 70% na última semana |

---

## 7. Segurança

### Fase local (Docker)
- Chaves de API em `.env`, nunca no código
- `.env` no `.gitignore`
- Qdrant sem autenticação (acesso apenas interno no docker-compose)

### Fase AWS
- Secrets no AWS Secrets Manager
- IAM com princípio do menor privilégio
- Serviços internos em subnet privada (sem acesso direto da internet)
- HTTPS obrigatório em todos os endpoints públicos

---

## 8. Variáveis de Ambiente

```env
# LLM
LLM_PROVIDER=gemini                  # gemini | bedrock
GEMINI_API_KEY=AIza...
LLM_MODEL=gemini-2.0-flash

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=helpdesk_docs

# LangFuse
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_HOST=http://localhost:3000

# Banco
DATABASE_URL=postgresql://user:pass@localhost:5432/helpdesk

# App
AUTO_RESOLVE_CONFIDENCE_THRESHOLD=0.7
MAX_UPLOAD_SIZE_MB=10
```

---

## 9. O que está fora do escopo (v1)

- Integração real com Active Directory
- Interface web para usuário final
- Fine-tuning de modelos
- Multi-idioma
- SLA e contratos de suporte
- Autenticação de usuários (OAuth / AD) — previsto para v2

---

## 10. Registro de Mudanças

| Data | Versão | Mudança |
|---|---|---|
| ___ | 1.0 | Spec inicial criada |
