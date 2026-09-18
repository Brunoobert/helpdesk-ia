# 📋 Spec — Help Desk IA com RAG, n8n e AWS

> **Versão:** 1.7.0
> **Status:** Etapa 4 Concluída | Planejamento da Etapa 4.1 (Excelência LLMOps & Evals)  
> **Última atualização:** 18/09/2026

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
2. **Embeddings Provider:** Separação das chamadas de LLM e embeddings. Uso padrão do Google `gemini-embedding-001` (3072 dim), substituindo o planejado `text-embedding-004` que não funcionou.
3. **RAG e Contexto:** A busca vetorial utiliza um particionamento inteligente em duas etapas para documentos (800 chars / 100 overlap). Para `.md`, aplica-se o `MarkdownHeaderTextSplitter` para preservar seções (garantindo que passos de troubleshooting não sejam cortados), fazendo fallback no `RecursiveCharacterTextSplitter`. Metadados estruturais como `secao` e `subsecao` são anexados nativamente a cada chunk no Qdrant.
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
| E3-01 | Container do n8n | Alta | ✅ Concluído | Adicionar n8n ao `docker-compose.yml` e expor na porta 5678 |
| E3-02 | Fluxo Principal | Alta | ✅ Concluído | Webhook -> POST `/classify` -> Switch de Decisão |
| E3-03 | Ação Automática | Média | ✅ Concluído | Mock de resolução via n8n (ex: responder webhook) se `auto_resolve=true` |
| E3-04 | Alerta Humano | Média | ✅ Concluído | Mock de notificação (ex: Telegram/Slack) para casos de urgência |

---

## Etapa 4 — Observabilidade e Persistência (MLOps)

**Objetivo:** Instrumentar o agente para registrar cada requisição com custo, latência e persistir histórico no banco.

| ID | Tarefa | Prioridade | Status | Notas |
|---|---|---|---|---|
| E4-01 | Persistência `TicketLog` | Média | ✅ Concluído | Uso de PostgreSQL + SQLAlchemy, tabela `ticket_logs` persistindo histórico |
| E4-02 | Traces LangFuse | Alta | ✅ Concluído | Langfuse v2.36.0 integrado diretamente ao PostgreSQL (sem necessidade de ClickHouse/Redis) |

---

## Etapa 4.1 — Excelência em LLMOps & Avaliação Contínua

**Objetivo:** Elevar a maturidade de MLOps/LLMOps do projeto adicionando auditoria temporal de embeddings, ciclo de feedback humano (Active Learning), suíte automatizada de testes/evals com controle de rate limit (Groq TPM) e alternância dinâmica de modelos sem reiniciar o servidor.

| ID | Tarefa | Prioridade | Status | Notas |
|---|---|---|---|---|
| E4-03 | **Versionamento & Auditoria Temporal no RAG** | Alta | ⏳ Pendente | `app/rag.py`: chunks com `is_active`, `version` e `created_at`. Pré-filtro no Qdrant HNSW (ADR-005) |
| E4-04 | **Feedback Humano (Active Learning)** | Média | ⏳ Pendente | `POST /feedback`: atualiza `correct_classification` no PostgreSQL e registra score de acurácia no Langfuse |
| E4-05 | **Golden Dataset & Evals com Pacing de Rate Limit** | Alta | ⏳ Pendente | `tests/golden_dataset.json` (20 casos) e `evals/run_evals.py` com delay entre chamadas para respeitar cotas TPM/RPM da Groq |
| E4-06 | **Troca Dinâmica de Modelo (Model Switching)** | Média | ⏳ Pendente | Header opcional `X-LLM-Provider` ou campo `llm_provider` no payload para alternar modelos em tempo de execução sem alterar `.env` |
| E4-07 | **Autenticação de Borda via API Key** | Média | ⏳ Pendente | `X-API-Key` nos endpoints operacionais do FastAPI e integração no nó HTTP do n8n (ADR-006) |

---

## 3. Contratos de API

Todos os endpoints operacionais (`/classify`, `/ingest`, `/feedback`) exigem cabeçalho de autenticação:
`X-API-Key: <token>` (validado via secret configurado em variável de ambiente `API_AUTH_KEY`).

### `POST /classify`

Recebe o texto de um chamado e retorna classificação estruturada. Permite override dinâmico do modelo via headers ou payload sem alterar `.env`.

**Headers**
```http
Content-Type: application/json
X-API-Key: string (obrigatório)
X-LLM-Provider: string (opcional: "groq" | "gemini" | "ollama" — fallback para LLM_PROVIDER do .env)
X-LLM-Model: string (opcional: modelo específico — fallback para MODEL do .env)
```

**Request**
```json
{
  "ticket_id": "string",
  "text": "string",
  "source": "email | webhook | manual",
  "llm_provider": "groq | gemini | ollama (opcional)",
  "llm_model": "string (opcional)"
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
| 401 | API Key ausente ou inválida (`X-API-Key`) |
| 422 | Campo obrigatório ausente ou tipo inválido / path de categoria inválido |
| 503 | LLM API indisponível ou rate limit (TPM/RPM) excedido |
| 500 | Erro interno |

---

### `POST /ingest`

Recebe um documento (PDF ou TXT) e indexa no banco vetorial com versionamento temporal e soft invalidation (`is_active`).

**Headers**
```http
X-API-Key: string (obrigatório)
```

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
| 401 | API Key ausente ou inválida (`X-API-Key`) |
| 415 | Formato de arquivo não suportado |
| 413 | Arquivo maior que 10MB |
| 500 | Falha ao gerar embeddings |

---

### `POST /feedback`

Registra o feedback de um operador humano sobre a acurácia da classificação do chamado (Active Learning).

**Headers**
```http
Content-Type: application/json
X-API-Key: string (obrigatório)
```

**Request**
```json
{
  "ticket_id": "string",
  "correct": true,
  "correct_category": "INFRAESTRUTURA/VPN/ERRO_CONEXAO (opcional)",
  "notes": "string (opcional)"
}
```

**Response 200**
```json
{
  "status": "success",
  "ticket_id": "string",
  "feedback_recorded": true
}
```

**Erros**
| Código | Motivo |
|---|---|
| 401 | API Key ausente ou inválida (`X-API-Key`) |
| 404 | Ticket ID não encontrado no banco de dados |
| 422 | Payload inválido |

---

### `GET /health`

Verifica se todos os serviços dependentes estão saudáveis (endpoint público / sem autenticação para probes de orquestração).

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
    llm_provider: Optional[str] = None # Override dinâmico opcional ("gemini", "groq", "ollama")
    llm_model: Optional[str] = None    # Override opcional de modelo específico


class FeedbackInput(BaseModel):
    ticket_id: str
    correct: bool
    correct_category: Optional[str] = None
    notes: Optional[str] = None
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

### Autenticação de Borda da API
- Endpoints operacionais (`POST /classify`, `POST /ingest`) protegidos por header `X-API-Key` contra acesso não autorizado (ver ADR-006).
- Chave configurada via `API_AUTH_KEY` e compartilhada de forma segura com clientes autorizados (ex: n8n).

### Fase local (Docker)
- Chaves de API em `.env`, nunca no código
- `.env` no `.gitignore`
- Qdrant sem autenticação exposto apenas na rede interna do docker-compose

### Fase AWS
- Secrets no AWS Secrets Manager / Parameter Store
- IAM com princípio do menor privilégio
- Serviços internos em subnet privada (sem acesso direto da internet)
- HTTPS obrigatório em todos os endpoints públicos via ALB ou CloudFront

---

## 8. Variáveis de Ambiente

### Providers

O agente usa **LangChain** com provider selecionado por variável de ambiente.

| Provider | Uso recomendado | Modelo padrão | API key |
|---|---|---|---|
| `gemini` | Produção | `gemini-2.5-flash` (`GEMINI_MODEL`) | `GEMINI_API_KEY` |
| `groq` | Desenvolvimento | `llama-3.1-8b-instant` / `openai/gpt-oss-120b` (`GROQ_MODEL`) | `GROQ_API_KEY` |
| `ollama` | Local / offline | `llama3.2` (`OLLAMA_MODEL`) | Não exige |

**Embeddings:** Configurado de forma independente, utilizando `EMBEDDING_PROVIDER`.

```env
# Segurança e Autenticação da API
API_AUTH_KEY=seu_token_secreto_aqui

# LLM — provider: gemini (produção) | groq (dev) | ollama (local/offline)
LLM_PROVIDER=groq

# Embeddings — provider: google (dev/prod) | ollama (offline)
EMBEDDING_PROVIDER=google

# Gemini (produção)
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-2.5-flash

# Groq (desenvolvimento)
GROQ_API_KEY=gsk_...
GROQ_MODEL=openai/gpt-oss-120b

# Ollama (local)
OLLAMA_MODEL=llama3.2
OLLAMA_BASE_URL=http://localhost:11434

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=knowledge_base

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
| 17/06/2026 | 1.4.2 | Registro de divergências da Etapa 2: Adoção do modelo gemini-embedding-001 (devido a erro 404 no text-embedding-004) e refatoração da estratégia de RAG para usar MarkdownHeaderTextSplitter preservando estruturas de troubleshooting completas (com fallback para RecursiveCharacterTextSplitter de 800/100 caracteres). |
| 16/09/2026 | 1.5.0 | Finalização da Etapa 4 (MLOps): Resolução de segfault do Langfuse fixando imagem v2.36.0 (PostgreSQL-only, sem dependência de ClickHouse/Redis). Tratamento defensivo contra Prompt Injection e recusas de LLM no classifier.py com fallback automático para escalonamento humano. Correção no parsing de JSON com blocos de markdown embutidos. Validação end-to-end com n8n, Postman, FastAPI e Qdrant. |
| 18/09/2026 | 1.6.0 | Adição formal de ADRs de Arquitetura: ADR-005 (Ciclo de Vida, Versionamento e Auditoria Temporal de Embeddings no RAG via Soft Invalidation com `is_active`), ADR-006 (Autenticação de Borda e Segurança de APIs via `X-API-Key`) e ADR-007 (Estratégia Híbrida de Deploy Cloud AWS com Custo Zero/Mínimo no Free Tier para Etapa 5). |
| 18/09/2026 | 1.7.0 | Adição do Backlog da Etapa 4.1 (Excelência LLMOps): Endpoint de feedback humano (Active Learning), Evals automatizadas com pacing para respeitar rate limits (Groq TPM) e Model Switching dinâmico via headers/payload sem alteração de .env. |

---

## 11. Registros de Decisões de Arquitetura (ADRs)

### ADR-005: Ciclo de Vida, Versionamento e Auditoria Temporal de Embeddings no RAG

#### Status
Proposto & Aceito

#### Contexto
- **Problema:** A ingestão de runbooks (`POST /ingest` ou scripts de carga) precisa atualizar documentos que sofrem alterações sem gerar fragmentos órfãos ou duplicatas no Qdrant. Além disso, o sistema deve suportar **auditoria temporal**: capacidade de saber exatamente qual versão da base de conhecimento gerou uma resposta no passado e permitir reproduzir ou auditar classificações antigas.
- **Restrições:** Foco em aprendizado de engenharia de IA e MLOps, mantendo os filtros do banco vetorial performáticos e determinísticos.

#### Opções Consideradas

| Opção | Prós | Contras | Complexidade | Quando Válida |
|---|---|---|---|---|
| **Opção A: Substituição Idempotente (Hard Delete por `source`)** | • Banco sempre enxuto<br>• Menor consumo de RAM/Disco no Qdrant<br>• Zero risco de drift de dados obsoletos | • Não guarda histórico de versões anteriores dentro do banco vetorial (inviabiliza auditoria temporal nativa no Qdrant) | Baixa | Bases puramente descartáveis ou quando não há necessidade de reproduzir respostas passadas. |
| **Opção B: Soft Invalidation via Metadados (`is_active: bool` + `version` + `created_at`)** | • **Permite histórico completo e auditoria temporal**<br>• Rollback instantâneo via payload update<br>• Pré-filtro no HNSW garante que apenas versões ativas entrem no Top-K | • Vetores inativos permanecem indexados (exige dimensionar o cluster vetorial adequadamente) | Média | **Padrão Escolhido:** Sistemas com requisitos de auditoria, rastreabilidade de suporte e aprendizado aprofundado de ciclo de vida de dados. |
| **Opção C: Coleções Versionadas (Blue/Green Collection com Alias)** | • Deploy atômico de bases inteiras<br>• Zero downtime e rollback imediato por chave de alias no Qdrant | • Exige reindexação integral a cada documento alterado<br>• Consumo de espaço em dobro durante cutover | Alta | Bases com deploys batch planejados e milhões de documentos. |

#### Decisão
**Escolhida:** **Opção B (Soft Invalidation via Metadados e Auditoria Temporal)**.

1. **Schema de Metadados de cada Ponto (Payload):**
   - `source`: Identificador do documento (ex.: `manual_vpn.md`).
   - `version`: Inteiro incremental para aquele documento (`1, 2, 3...`).
   - `is_active`: Booleano (`true` para a versão corrente, `false` para legadas).
   - `created_at`: Timestamp ISO da indexação.
   - `path`: Categoria associada (ex: `INFRAESTRUTURA/VPN/ERRO_CONEXAO`).
   - `doc_type`: `runbook` | `policy` | `resolved_ticket`.

2. **Mecânica de Ingestão e Atualização:**
   - Ao receber uma nova versão de um documento existente:
     - Localiza a versão anterior vigente (`is_active: true`) para o mesmo `source`.
     - Executa `set_payload(filter={"source": source, "is_active": True}, payload={"is_active": False})` para inativar os chunks antigos sem excluí-los.
     - Insere os novos chunks com `version: version_anterior + 1`, `is_active: True` e `created_at: now()`.

3. **Busca Semântica do Agente (Operação Normal):**
   - Aplica **Pré-filtro obrigatório no Qdrant**:
     ```python
     Filter(must=[
         FieldCondition(key="is_active", match=MatchValue(value=True)),
         FieldCondition(key="path", match=MatchValue(value=categoria_detectada))  # se aplicável
     ])
     ```
   - O Qdrant só avalia nós ativos durante a busca vetorial, garantindo que o Top-K **nunca** seja poluído por versões obsoletas.

4. **Auditoria Temporal (Histórico):**
   - Consultas de auditoria (ex: "Qual runbook estava ativo quando o ticket TKT-123 foi classificado em 10/05?") podem ser executadas filtrando por `version: X` ou por janela de data com `created_at`.

#### Trade-offs Aceitos
- Manutenção de pontos inativos no Qdrant. Como a base de conhecimento do projeto é de runbooks técnicos (dezenas a centenas de documentos), o impacto em RAM/disco é irrelevante, enquanto o ganho em rastreabilidade e aprendizado é imenso.

#### Consequências
- **Positivas:** Rastreabilidade temporal impecável; possibilidade de rollbacks instantâneos; base preparada para auditoria de compliance.
- **Negativas:** Exige lógica de consulta de versão e atualização de payload prévia à inserção.
- **Mitigação:** Encapsular a operação em uma função idempotente `ingest_document_with_versioning()` no módulo `app/rag.py`.

#### Revisit Trigger
- Se o volume de vetores inativos ultrapassar 100.000 pontos, implementar rotina de expurgo (purge) de versões inativas mais antigas que 180 dias.

---

### ADR-006: Autenticação de Borda e Segurança das APIs (`X-API-Key`)

#### Status
Proposto & Aceito

#### Contexto
- **Problema:** Os endpoints do FastAPI (`POST /classify`, `POST /ingest`) executam chamadas pagas de LLM (Groq/Gemini), gravam no PostgreSQL e afetam a base vetorial. Atualmente, os endpoints estão abertos sem autenticação, expondo a aplicação a requisições maliciosas ou disparos acidentais caso a porta seja exposta.
- **Restrições:** O cliente principal da API é o orquestrador n8n e ferramentas de teste/CI (Postman, curl, GitHub Actions). Não há usuários finais interagindo diretamente com o FastAPI.

#### Opções Consideradas

| Opção | Prós | Contras | Complexidade | Quando Válida |
|---|---|---|---|---|
| **Opção A: Header Compartilhado `X-API-Key`** | • Extremamente simples e nativo no FastAPI (`Security(APIKeyHeader)`)<br>• Integração trivial no n8n (Header Auth no HTTP Request node)<br>• Baixíssimo overhead | • Não possui permissões granulares por usuário/role<br>• Rotação exige atualizar `.env` do app e dos clientes | Baixa | Comunicação Service-to-Service interna ou entre componentes de uma mesma infra. |
| **Opção B: OAuth2 com Tokens JWT** | • Expiração automática, revogação, escopos detalhados | • Overhead de servidor auth, complexidade excessiva para 1 único cliente (n8n) | Alta | Múltiplos tenants, usuários humanos ou ecossistema aberto de parceiros. |
| **Opção C: Isolamento Exclusivo por Rede (Security Groups/VPC sem Auth)** | • Sem necessidade de gerenciar tokens no código | • Risco alto de exposição se houver falha de configuração de rede ou porta mapeada | Baixa | Apenas redes privadas puras sem saída ou em clusters totalmente isolados. |

#### Decisão
**Escolhida:** **Opção A (`X-API-Key`)** via injeção de dependência do FastAPI.
- Header padrão: `X-API-Key`.
- O valor é injetado via variável de ambiente `API_AUTH_KEY`.
- Endpoint `GET /health` permanece público para health check do docker-compose e balanceadores de carga.
- Nó HTTP Request do n8n configurado com Header Authentication.

#### Trade-offs Aceitos
- Compartilhamento de uma chave estática entre n8n e FastAPI, aceitável pelo escopo Service-to-Service fechado.

#### Consequências
- **Positivas:** Protege os endpoints contra consumo indevido de cotas de LLM e gravação arbitrária de embeddings; implementação em menos de 20 linhas de código no FastAPI.
- **Negativas:** Necessidade de configurar a mesma chave no n8n.
- **Mitigação:** Armazenar `API_AUTH_KEY` em secrets seguros tanto localmente (`.env`) quanto na AWS (Secrets Manager / Parameter Store).

---

### ADR-007: Estratégia de Deploy Cloud AWS com Custo Mínimo / Free Tier (Etapa 5)

#### Status
Proposto & Aceito

#### Contexto
- **Problema:** A Etapa 5 prevê a implantação na nuvem (AWS) com objetivo pedagógico de aprender arquitetura em nuvem (provisionamento, networking, segurança, CI/CD e integração de microsserviços), **com a restrição estrita de custo zero ou o menor valor financeiro possível** (evitando surpresas na fatura).
- **Restrições:** Orçamento alvo: **$0.00 a < $5.00 USD/mês**, aproveitando ao máximo as cotas gratuitas (Free Tier) da AWS e dos provedores parceiros.

#### Opções Consideradas

| Opção | Prós | Contras | Custo Estimado | Complexidade |
|---|---|---|---|---|
| **Opção A: AWS Free Tier Híbrido (EC2 t2/t3.micro + Qdrant Cloud Free + Langfuse Cloud Free)** | • Custo praticamente **$0.00/mês**<br>• Desonera a RAM da EC2 transferindo Qdrant e Langfuse para SaaS gratuitos oficiais<br>• Proporciona experiência real com EC2, Security Groups, Elastic IP e S3 | • EC2 t2/t3.micro tem 1GB de RAM (exige swap configurado no Linux para n8n/Postgres/FastAPI) | **$0.00 / mês** (1º ano Free Tier) | Baixa |
| **Opção B: AWS Lightsail VM Dedicada (Docker Compose Local)** | • 2 vCPU, 2GB a 4GB RAM<br>• Custo fixo sem surpresas de rede<br>• 3 meses de Free Trial para novas contas | • Passa a custar $5 a $10/mês após período de trial | $0 (trial) a $5-$10/mês | Muito Baixa |
| **Opção C: Multi-Serviço Gerenciado (ECS Fargate + RDS Postgres + ALB + NAT Gateway)** | • Alta disponibilidade corporativa multi-AZ | • NAT Gateway (~$32/mês) + Fargate contínuo + RDS inviabilizam orçamento estudantil/portfolio | $100 – $220/mês | Alta |

#### Decisão
**Escolhida:** **Opção A (Estratégia Cloud Híbrida de Custo Zero / Mínimo)** com foco em aprendizado prático:

1. **Computação na AWS (Camada Gratuita de 12 Meses):**
   - Instância **AWS EC2 `t2.micro` ou `t3.micro`** (750 horas gratuitas/mês no AWS Free Tier).
   - Configuração de **2GB a 4GB de Swap Memory** no Linux para estabilidade operacional de containers.
   - Execução conteinerizada via Docker Compose contendo apenas: `fastapi`, `n8n` e `db` (PostgreSQL).

2. **Desoneração de Memória e Custos via Free Tiers Oficiais:**
   - **Qdrant Cloud (Starter Free Tier):** Cluster perpétuo gerenciado oficial gratuito (1GB RAM / 0.5 vCPU sem limite de tempo), eliminando o container do Qdrant da EC2 e liberando RAM na máquina AWS.
   - **Langfuse Cloud (Free Tier):** Até 50.000 eventos/mês na nuvem oficial do Langfuse, eliminando a necessidade de manter o container do Langfuse rodando na AWS.
   - **AWS S3 Standard (Free Tier de 12 Meses):** 5GB de armazenamento grátis para backup de documentos e dump diário do Postgres.

3. **Segurança e Rede na AWS:**
   - Security Groups restritivos: portas 80/443 públicas, porta 22 (SSH) restrita ao IP do desenvolvedor, banco e serviços internos fechados em `localhost`.
   - Elastic IP associado à instância EC2 (gratuito enquanto a instância estiver em execução).

#### Trade-offs Aceitos
- A divisão entre componentes na EC2 e componentes em Free Tier de SaaS externos exige gerenciar duas conexões adicionais via internet (`QDRANT_HOST` remoto e `LANGFUSE_HOST` remoto), plenamente aceitável pela estabilidade e pelo custo zero obtido.

#### Consequências
- **Positivas:** Experiência completa de nuvem AWS (EC2, S3, IAM, Security Groups, Elastic IP, Docker) com **gasto zero ($0.00)**; performance estável da EC2 sem sobrecarga de memória; aprendizado sólido de arquitetura moderna de microsserviços.
- **Negativas:** Exige criar conta no Qdrant Cloud (gratuita) e Langfuse Cloud (gratuita).
- **Mitigação:** Manter a configuração do `docker-compose.yml` local intacta para que o ambiente local continue funcionando de forma 100% offline se desejado.

#### Revisit Trigger
- Fim do período de 12 meses do AWS Free Tier ou crescimento do volume de chamados além de 50.000 eventos/mês.
