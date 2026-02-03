# Seif's AI-Powered Portfolio

A personal portfolio website with an AI assistant that answers questions about Seif's professional expertise. Built with Astro, FastAPI, and deployed on Azure Container Apps.

![Azure](https://img.shields.io/badge/Azure-0089D6?style=flat&logo=microsoft-azure&logoColor=white)
![Astro](https://img.shields.io/badge/Astro-FF5D01?style=flat&logo=astro&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat&logo=typescript&logoColor=white)

## 🏗️ Architecture

This project consists of three main components:

### Frontend (`/astro`)
- **Framework**: [Astro](https://astro.build/) with server-side rendering
- **Styling**: Tailwind CSS v4
- **Animations**: GSAP + Lottie
- **Features**: 
  - Portfolio showcase with project timeline
  - Blog integration
  - Real-time AI chat with streaming responses (SSE)

### Backend API (`/app`)
- **Framework**: FastAPI with Python 3.12
- **AI/ML Stack**:
  - **LLM**: DeepSeek V3.2 via Azure AI Foundry
  - **Embeddings**: Azure OpenAI (text-embedding-ada-002)
  - **RAG**: Azure AI Search for context retrieval
  - **Inference**: LiteLLM for unified LLM interface
- **Features**:
  - Two-stage classification (filters irrelevant questions)
  - Server-Sent Events (SSE) for streaming responses
  - Rate limiting with Azure Table Storage persistence
  - Response caching with configurable TTL

### Infrastructure (`/infra`)
- **IaC**: Bicep with Azure Verified Modules
- **Deployment Target**: Azure Container Apps
- **Services**:
  - Azure Container Registry
  - Azure AI Foundry (LLM + Embeddings)
  - Azure AI Search
  - Azure Key Vault
  - Azure Storage Account

## 📁 Project Structure

```
├── app/                          # Python FastAPI backend
│   ├── litellm_app.py            # Main API application
│   ├── prompts.yaml              # AI system prompts configuration
│   ├── requirements.txt          # Python dependencies
│   ├── Dockerfile                # Multi-stage Python container
│   ├── services/                 # Business logic modules
│   │   ├── sanitization.py       # Input sanitization
│   │   └── streaming.py          # SSE streaming utilities
│   └── storage/                  # Storage backends
│       └── azure_table_storage.py # Rate limiting persistence
│
├── astro/                        # Astro frontend
│   ├── src/
│   │   ├── components/           # UI components
│   │   ├── content/portfolio/    # Markdown portfolio items
│   │   ├── pages/                # Route pages
│   │   │   └── api/              # API routes (proxy to backend)
│   │   └── services/             # Frontend services
│   │       └── aiService.ts      # AI chat client
│   ├── package.json
│   ├── Dockerfile                # Multi-stage Node.js container
│   └── astro.config.mjs
│
├── infra/                        # Azure infrastructure
│   ├── main.bicep                # Main deployment template
│   ├── main.bicepparam           # Parameters file
│   └── modules/                  # Bicep modules
│       ├── appEnvironment.bicep  # Container Apps Environment
│       ├── certKeyvault.bicep    # SSL certificate management
│       └── foundry.bicep         # Azure AI Foundry setup
│
└── cloudflare/                   # Cloudflare configuration (DNS/CDN)
```

## 🤖 AI Assistant Features

The AI assistant uses a two-stage approach:

1. **Classification Stage**: A lightweight prompt determines if the question is about Seif's professional work
2. **RAG Stage**: For relevant questions, retrieves context from Azure AI Search and generates a response

### Rate Limiting

- Default: 3 requests per day per IP
- Persistent across container restarts using Azure Table Storage
- Fun, randomized messages when limits are exceeded

### Caching

- In-memory cache (resets on cold start)
- Optional: Disk cache with Azure Files for persistence

## 📝 License

See [LICENSE](LICENSE) for details.

## 👤 Author

**Seif Bassem** - Cloud Solution Architect

- Website: [seifbassem.com](https://seifbassem.com)
- GitHub: [@yourhandle](https://github.com/sebassem)