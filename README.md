# 🤖 Help Desk IA

MVP de um agente de IA para triagem automática de chamados de suporte (help desk), com classificação de urgência e categoria, base de conhecimento consultável via RAG e resolução automática de casos simples.

> Status: em desenvolvimento — veja [Onde o projeto está](#-onde-o-projeto-está) abaixo.

## O que é

O agente recebe um chamado de suporte (texto), classifica a **urgência** e a **categoria** (em uma taxonomia hierárquica configurável), consulta uma base de conhecimento interna (runbooks e histórico de chamados resolvidos) via **RAG**, e decide entre:

- resolver o caso automaticamente e registrar o log, ou
- escalar para um humano, com sugestão de ação.

Tudo isso com observabilidade de custo, latência e taxa de acerto por requisição.

### Problema que resolve

Chamados repetitivos consomem tempo do time de infraestrutura. Muitas soluções já existem em runbooks e no histórico de chamados, mas ficam espalhadas em arquivos e não são reaproveitadas. O agente centraliza esse conhecimento e o aplica automaticamente.

### O que não é

- Não é um chatbot de atendimento ao cliente.
- Não substitui analistas humanos em chamados complexos.
- Não treina modelos proprietários — usa LLMs via API (Gemini, Groq ou Ollama).

## Arquitetura

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

| Serviço | Responsabilidade | Onde roda |
|---|---|---|
| FastAPI | API do agente | Docker |
| Qdrant | Banco vetorial para RAG | Docker |
| n8n | Orquestração de fluxos | Docker |
| PostgreSQL | Metadados e logs de chamados | Docker |
| LangFuse | Observabilidade de custo/latência do LLM | Docker |

Principais decisões técnicas: LLM e provider de embeddings configuráveis por variável de ambiente (Gemini em produção, Groq em dev, Ollama offline), taxonomia de categorias hierárquica (`AREA/SUBAREA/ACAO`) definida em YAML, e RAG com particionamento de documentos preservando a estrutura de seções (Markdown) com fallback para split por caracteres.

## Como rodar

### Pré-requisitos

- Docker e Docker Compose
- Uma chave de API de LLM (Gemini ou Groq) — ou Ollama rodando localmente para uso 100% offline

### Passo a passo

1. Clone o repositório:
   ```bash
   git clone https://github.com/Brunoobert/helpdesk-ia.git
   cd helpdesk-ia
   ```

2. Copie o arquivo de variáveis de ambiente e preencha suas chaves:
   ```bash
   cp .env.example .env
   ```
   Principais variáveis a configurar:
   - `LLM_PROVIDER` — `gemini`, `groq` ou `ollama`
   - `GEMINI_API_KEY` / `GROQ_API_KEY` — conforme o provider escolhido
   - `EMBEDDING_PROVIDER` — provider usado para gerar embeddings do RAG

3. Suba os serviços:
   ```bash
   docker compose up -d
   ```
   Isso inicializa a API do agente, o Qdrant (banco vetorial), o n8n (orquestração), o PostgreSQL (logs) e o LangFuse (observabilidade).

4. Verifique se está tudo no ar:
   ```bash
   curl http://localhost:8000/health
   ```

### Portas dos serviços

| Serviço | Porta |
|---|---|
| API (FastAPI) | `8000` |
| Qdrant | `6333` |
| n8n | `5678` |
| PostgreSQL | `5432` |
| LangFuse | `3000` |

### Rodando os testes

```bash
pytest
```

## Endpoints principais

- `POST /classify` — recebe o texto de um chamado e retorna categoria, urgência, ação sugerida e se pode ser auto-resolvido.
- `POST /ingest` — indexa um documento (PDF/TXT) na base de conhecimento vetorial.
- `GET /health` — verifica a saúde dos serviços dependentes (Qdrant, LLM, LangFuse, banco).

Contratos completos de request/response estão documentados em [`spec_helpdesk_ia.md`](./spec_helpdesk_ia.md).

## Onde o projeto está

O desenvolvimento é guiado por etapas, detalhadas na spec técnica ([`spec_helpdesk_ia.md`](./spec_helpdesk_ia.md)):

- ✅ **Etapa 2 — RAG e taxonomia:** concluída. RAG com Qdrant funcionando; taxonomia de categorias hierárquica e configurável via YAML.
- ✅ **Etapa 3 — Orquestração com n8n:** concluída. Fluxo webhook → `/classify` → decisão automática (mock) ou alerta para humano.
- ⏳ **Etapa 4 — Observabilidade e persistência:** em andamento. Falta persistir o histórico de chamados (`TicketLog`) no PostgreSQL e ligar os traces no LangFuse.

Fora do escopo por enquanto: integração real com Active Directory, interface web para o usuário final, autenticação de usuários e suporte multi-idioma.

## Estrutura do repositório

```
app/            # Código da API (FastAPI) — classificação, RAG, prompts
config/         # Configuração da taxonomia de categorias (categorias.yml)
docs/           # Base de conhecimento (runbooks, documentos sintéticos)
n8n/flows/      # Fluxos de orquestração do n8n
scripts/        # Scripts auxiliares
tests/          # Testes automatizados (pytest)
```

## Variáveis de ambiente

Veja o arquivo [`.env.example`](./.env.example) para a lista completa. As principais são:

```env
LLM_PROVIDER=groq              # gemini | groq | ollama
EMBEDDING_PROVIDER=google      # google | ollama

GEMINI_API_KEY=
GROQ_API_KEY=
OLLAMA_BASE_URL=http://localhost:11434

QDRANT_HOST=localhost
QDRANT_PORT=6333

DATABASE_URL=postgresql://user:pass@localhost:5432/helpdesk
```

## Segurança

- Chaves de API ficam apenas em `.env`, nunca versionadas (arquivo no `.gitignore`).
- Em produção (AWS), os segredos vão para o AWS Secrets Manager e os serviços internos ficam em subnet privada.
