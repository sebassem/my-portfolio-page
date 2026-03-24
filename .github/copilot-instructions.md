# Copilot Instructions

AI-powered portfolio website for Seif Bassem with a RAG-based assistant that answers questions about his professional expertise.

## Project Structure

Three main components communicate in this order:

```
Browser → Astro (frontend, port 4321) → FastAPI (backend, port 8000) → Azure AI Services
```

- **`/astro`** - Astro SSR frontend with Tailwind CSS v4
- **`/app`** - FastAPI backend with LiteLLM and Azure AI integration
- **`/infra`** - Bicep IaC using Azure Verified Modules (AVM)
- **`/cloudflare`** - DNS/CDN configuration

## Development Commands

### Frontend (`/astro`)

```bash
cd astro
npm install
npm run dev      # Start dev server at http://localhost:4321
npm run build    # Production build
npm run preview  # Preview production build
```

### Backend (`/app`)

```bash
cd app
pip install -r requirements.txt
uvicorn litellm_app:app --reload --port 8000  # Start dev server
```

Required environment variables (create `.env` file or set in shell):
- `AZURE_OPENAI_ENDPOINT` - Azure AI Foundry endpoint
- `AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME` - LLM deployment name (e.g., `llm-deployment`)
- `AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME` - Embedding deployment name
- `AZURE_SEARCH_INSTANCE_NAME` - Azure AI Search instance name
- `AZURE_SEARCH_INDEX_NAME` - Search index name
- `AZURE_STORAGE_ACCOUNT_NAME` - (Optional) For persistent rate limiting

### Infrastructure (`/infra`)

```bash
# Validate Bicep
az bicep build --file infra/main.bicep --stdout > /dev/null

# What-if deployment
az deployment sub what-if --location swedencentral --parameters infra/main.bicepparam

# Deploy
az deployment sub create --location swedencentral --parameters infra/main.bicepparam
```

## Architecture Patterns

### Two-Stage AI Classification

The backend uses a two-stage approach to save tokens:
1. **Classification Stage** (`classify_question`) - Lightweight prompt (~150 tokens) determines if the question is about Seif's professional work
2. **RAG Stage** - Only relevant questions trigger Azure AI Search retrieval and full LLM response

This pattern is defined in `app/prompts.yaml` and implemented in `app/litellm_app.py`.

### SSE Streaming

AI responses stream via Server-Sent Events:
- Backend: `app/services/streaming.py` formats SSE messages
- Frontend proxy: `astro/src/pages/api/ask.ts` passes through SSE streams
- Client: `astro/src/services/aiService.ts` consumes the stream

### Rate Limiting

Rate limiting uses two backends:
- **In-memory** (default) - Resets on container restart
- **Azure Table Storage** (persistent) - Custom storage backend in `app/storage/azure_table_storage.py`

The storage backend is auto-detected based on `AZURE_STORAGE_ACCOUNT_NAME` env var.

### Authentication

All Azure services use `DefaultAzureCredential` (no API keys):
- Local dev: Uses Azure CLI login
- Container Apps: Uses user-assigned managed identity

## Conventions

### Bicep/Infrastructure

- Uses Azure Verified Modules (AVM) from `br/public:avm/...` registry
- Resource naming: `{type}-{prefix}-infra-{suffix}` (e.g., `ca-sbm-infra-001`)
- All secrets stored in Key Vault and referenced via managed identity

### Python Backend

- Type hints required
- Docstrings use Google style
- Prompts externalized in `prompts.yaml`, not hardcoded
- Input sanitization in `app/services/sanitization.py` with prompt injection detection

### Frontend

- Astro SSR mode with Node.js adapter
- API routes in `/astro/src/pages/api/` proxy to backend
- Never call backend URLs directly from browser - always use API routes

## CI/CD Workflows

| Workflow | Trigger Path | Action |
|----------|--------------|--------|
| `build-api.yml` | `app/**` | Build Python Docker image, deploy to Container Apps |
| `build-astro.yml` | `astro/**` | Build Node.js Docker image, deploy to Container Apps |
| `deploy-infra.yml` | `infra/**` | Validate and deploy Bicep templates |
| `upload-portfolio.yml` | Manual | Upload portfolio content to RAG index |

All workflows use OIDC authentication with Azure (no stored secrets for Azure access).
