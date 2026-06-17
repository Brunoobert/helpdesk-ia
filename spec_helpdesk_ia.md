# 📋 Spec — Help Desk IA com RAG, n8n e AWS

> **Versão:** 1.3.2
> **Status:** Em desenvolvimento  
> **Última atualização:** 17/06/2026

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
Vector DB  Gemini / Groq / Ollama
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
| LangFuse | Observabilidade de LLM | Docker local (v1) |
| PostgreSQL | Metadados e logs | Docker local / RDS |
| S3 | Storage dos documentos | AWS |
| GitHub Actions | CI/CD | GitHub |

### Decisões de arquitetura

| Decisão | Escolha | Alternativa descartada | Motivo |
|---|---|---|---|
| Vector DB | Qdrant | Pinecone | Self-hosted, sem custo por requisição |
| Orquestração | n8n | Airflow | Já tenho experiência, mais visual |
| Observabilidade | LangFuse | Phoenix | Open source, self-hosted via Docker local |
| Banco / ORM | PostgreSQL + SQLAlchemy | Psycopg2 puro | Persistência de logs estruturada de forma simples |
| Parser PDF | pdfplumber | PyPDF2 | Extração mais robusta de texto |
| Cloud | AWS | GCP | Maior demanda no mercado BR |
| LLM | Configurável via `LLM_PROVIDER` | Provider único hardcoded | Gemini em produção; Groq em dev; Ollama offline/local |
| Embeddings | Google `text-embedding-004` | sentence-transformers | Gratuito no free tier, sem dependência de GPU local. Configurável via `EMBEDDING_PROVIDER` |
| Taxonomia de categorias | Hierárquica em `config/categorias.yml` | Categorias flat fixas no código | Categorias em paths estruturados (AREA/SUBAREA/ACAO). Permite alinhar classificação e RAG |

### Decisão técnica — Taxonomia hierárquica e Embeddings (Etapa 2)

**Status:** Planejado para Etapa 2.

**Decisões tomadas:**
1. **Taxonomia Hierárquica:** Substituir categorias flat ("Rede", "Acesso", "Hardware"...) por paths hierárquicos no formato `AREA/SUBAREA/ACAO`, configurados via `config/categorias.yml`.
2. **Embeddings Provider:** Separação das chamadas de LLM e embeddings. Uso padrão do Google `text-embedding-004` (via `langchain-google-genai`), com Ollama (`nomic-embed-text`) apenas como fallback offline.
3. **RAG e Contexto:** Cada chunk no Qdrant recebe metadados com o path hierárquico. A busca vetorial é filtrada pelo path do chamado classificado, utilizando `RecursiveCharacterTextSplitter` (400 tokens / 60 overlap).
4. **Base Sintética:** Documentos gerados por IA mantidos em `docs/knowledge_base/` simulando casos reais.
5. **Critério de Auto-resolução (`auto_resolve_elegivel`):** Definido como `true` **SOMENTE** se:
   - O usuário comum (sem privilégio admin) consegue seguir o passo a passo sozinho.
   - Há baixo risco — errar não causa impacto grande.
   - O agente orienta com instruções — não executa nada diretamente no sistema.

**Contrato do arquivo `config/categorias.yml`:** cada entrada deve expor:

| Campo | Tipo | Descrição |
|---|---|---|
| `path` | string | Caminho da categoria (ex.: `INFRAESTRUTURA/VPN/ERRO_CONEXAO`) |
| `exemplos` | lista de strings | Exemplos de chamados típicos da categoria |
| `auto_resolve_elegivel` | bool | Se a categoria pode ser candidata a resolução automática |
| `documento_referencia` | string | Arquivo .md da base de conhecimento correspondente |

**Implementação prevista (Etapa 2):**

- `app/prompts.py` carrega `config/categorias.yml` via **PyYAML**.
- O schema `ClassificationResult` passa a usar `category: str` com um validator Pydantic (`field_validator`) validando contra os paths do YAML.
- `app/rag.py` será responsável pelo Qdrant e chamadas de embeddings.

**Exemplo ilustrativo `config/categorias.yml`:**

```yaml
categorias:
  - path: INFRAESTRUTURA/VPN/ERRO_CONEXAO
    exemplos:
      - "VPN não conecta"
      - "erro 800 na VPN"
    auto_resolve_elegivel: false  # Usuário comum não entende o erro técnico
    documento_referencia: manual_vpn.md
  - path: INFRAESTRUTURA/AD/RESET_SENHA
    exemplos:
      - "Reset de senha do AD"
    auto_resolve_elegivel: true  # Self-service via portal, sem admin
    documento_referencia: reset_senha.md
```

---

## Etapa 2 — Backlog

Tarefas planejadas para a segunda etapa (RAG + base de conhecimento). **Não implementar na Etapa 1.**

| ID | Tarefa | Prioridade | Status | Notas |
|---|---|---|---|---|
| E2-01 | Implementar RAG com Qdrant | Alta | ✅ Concluído | Ingestão com `pdfplumber` e TextSplitter; embeddings `gemini-embedding-001` |
| E2-02 | **Taxonomia configurável e hierárquica** | Alta | ✅ Concluído | `categorias.yml` com validação de path via Pydantic; busca RAG filtrada |

---

## Etapa 3 — Orquestração com n8n

**Objetivo:** Usar o n8n como camada de orquestração — recebendo chamados de fontes reais e roteando para o agente FastAPI.

| ID | Tarefa | Prioridade | Status | Notas |
|---|---|---|---|---|
| E3-01 | Container do n8n | Alta | ⏳ Pendente | Adicionar n8n ao `docker-compose.yml` e expor na porta 5678 |
| E3-02 | Fluxo Principal | Alta | ⏳ Pendente | Webhook -> POST `/classify` -> Switch de Decisão |
| E3-03 | Ação Automática | Média | ⏳ Pendente | Mock de resolução via n8n (ex: responder webhook) se `auto_resolve=true` |
| E3-04 | Alerta Humano | Média | ⏳ Pendente | Mock de notificação (ex: Telegram/Slack) para casos de urgência |

---

## Etapa 4 — Observabilidade e Persistência (MLOps)

**Objetivo:** Instrumentar o agente para registrar cada requisição com custo, latência e persistir histórico no banco.

| ID | Tarefa | Prioridade | Status | Notas |
|---|---|---|---|---|
| E4-01 | Persistência `TicketLog` | Média | ⏳ Pendente | Uso de PostgreSQL + SQLAlchemy (Migrado da Etapa 2) |
| E4-02 | Traces LangFuse | Alta | ⏳ Pendente | Rodando LangFuse via Docker local (Migrado da Etapa 2) |

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
  "category": "INFRAESTRUTURA/VPN/ERRO_CONEXAO",
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
| 422 | Campo obrigatório ausente ou tipo inválido / path de categoria inválido |
| 503 | LLM API indisponível |
| 500 | Erro interno |

---

### `POST /ingest`

Recebe um documento (PDF ou TXT) e indexa no banco vetorial.

**Request** — `multipart/form-data`
```
file: <arquivo PDF ou TXT>
doc_type: "runbook" | "policy" | "resolved_ticket"
path: "INFRAESTRUTURA/VPN/ERRO_CONEXAO"
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
    category: str                      # Path hierárquico (ex: INFRAESTRUTURA/VPN/ERRO_CONEXAO) validado via field_validator
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
2. Primeira chamada LLM: Classificar urgência e path da categoria
3. Buscar chunks similares no Qdrant (top 3) filtrando pelo path retornado
4. Segunda chamada LLM (se auto_resolve=true e RAG houver contexto): Sugerir ação baseada no runbook
5. Se auto_resolve = true E urgency != "Alta":
     → Executar ação automática
     → Logar como resolvido
6. Senão:
     → Retornar classificação para n8n
     → n8n notifica humano responsável
7. Persistir log no banco (PostgreSQL via SQLAlchemy)
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

### Providers

O agente usa **LangChain** com provider selecionado por variável de ambiente.

| Provider | Uso recomendado | Modelo padrão | API key |
|---|---|---|---|
| `gemini` | Produção | `gemini-2.5-flash` (`GEMINI_MODEL`) | `GEMINI_API_KEY` |
| `groq` | Desenvolvimento | `llama-3.1-8b-instant` (`GROQ_MODEL`) | `GROQ_API_KEY` |
| `ollama` | Local / offline | `llama3.2` (`OLLAMA_MODEL`) | Não exige |

**Embeddings:** Configurado de forma independente, utilizando `EMBEDDING_PROVIDER`.

```env
# LLM — provider: gemini (produção) | groq (dev) | ollama (local/offline)
LLM_PROVIDER=groq

# Embeddings — provider: google (dev/prod) | ollama (offline)
EMBEDDING_PROVIDER=google

# Gemini (produção)
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-2.5-flash

# Groq (desenvolvimento)
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.1-8b-instant

# Ollama (local)
OLLAMA_MODEL=llama3.2
OLLAMA_BASE_URL=http://localhost:11434

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
- **Sugestão e Recomendação Dinâmica de Categorias (Futuro):** O agente deve validar se o chamado de entrada possui alguma classificação condizente na taxonomia existente. Caso não encontre um encaixe adequado (baixa confiança), o agente deverá classificar o chamado sob um fallback genérico temporário e registrar/recomendar nos metadados da resposta a criação de uma nova categorização estruturada para posterior criação no `categorias.yml` pelos administradores.


---

## 10. Registro de Mudanças

| Data | Versão | Mudança |
|---|---|---|
| 27/05/2026 | 1.0 | Spec inicial criada |
| 28/05/2026 | 1.1 | Decisão técnica: taxonomia de categorias via YAML (Etapa 2) |
| 11/06/2026 | 1.2 | Atualização para Etapa 2: Taxonomia hierárquica (path), separação de Embeddings (Google) e LLM, Langfuse local, SQLAlchemy e pdfplumber |
| 11/06/2026 | 1.3 | Refinamento do critério de auto-resolução das categorias e definição da lista final de 21 paths |
| 11/06/2026 | 1.3.1 | Adição de funcionalidade futura de recomendação dinâmica de novas categorias na spec |
| 17/06/2026 | 1.4 | Reorganização de roadmap: n8n antecipado para Etapa 3 visando orquestração end-to-end. PostgreSQL e LangFuse movidos para Etapa 4 (Observabilidade). |
