"""
Simplified AI Assistant API using Azure SDK + LiteLLM

This is an alternative implementation to portfolio_api.py that:
- Uses direct Azure SDK calls (no LangChain/LangGraph abstraction)
- Uses LiteLLM for AI gateway features (caching, retries, fallbacks)
- Has fewer dependencies and faster cold starts

To switch back to LangGraph version, use portfolio_api.py instead.

Caching:
- Default: In-memory local cache (works with scale-to-zero, resets on cold start)
- Optional: Disk cache with Azure Files mount for persistent caching (see code comments)
"""

import os
import random
from pathlib import Path

import yaml
import litellm
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

load_dotenv()


# =============================================================================
# Load Prompts from External Configuration
# =============================================================================

def load_prompts(prompts_path: str = None) -> dict:
    """
    Load prompts from external YAML file.
    Path can be overridden via PROMPTS_FILE_PATH environment variable.
    """
    if prompts_path is None:
        prompts_path = os.getenv("PROMPTS_FILE_PATH", Path(__file__).parent / "prompts.yaml")

    with open(prompts_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# Load prompts at startup
PROMPTS = load_prompts()
ASSISTANT_PROMPT = PROMPTS["assistant_prompt"]


# =============================================================================
# Azure Clients Configuration (Direct SDK)
# =============================================================================

# DefaultAzureCredential tries multiple auth methods in order:
# Environment -> Workload Identity -> Managed Identity -> Azure CLI -> Azure PowerShell -> Azure Developer CLI
credential = DefaultAzureCredential()

# Token provider for Azure OpenAI
openai_token_provider = get_bearer_token_provider(
    credential, "https://cognitiveservices.azure.com/.default"
)

# Azure AI Search - Direct SDK (replaces LangChain AzureAISearchRetriever)
search_client = SearchClient(
    endpoint=f"https://{os.getenv('AZURE_SEARCH_INSTANCE_NAME')}.search.windows.net",
    index_name=os.getenv("AZURE_SEARCH_INDEX_NAME"),
    credential=credential
)

# Azure OpenAI configuration for LiteLLM
AZURE_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME")


# =============================================================================
# LiteLLM Configuration
# =============================================================================

# Cache TTL in seconds (default: 1 hour)
CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", "3600"))

# Default: in-memory local cache
# This works well for single-instance deployments and scale-to-zero scenarios
# Cache resets on cold start, but provides fast responses for repeated questions within a session
#litellm.cache = litellm.Cache(type="local", ttl=CACHE_TTL)

# -----------------------------------------------------------------------------
# OPTIONAL: Persistent Disk Cache with Azure Files Mount
# -----------------------------------------------------------------------------
# Uncomment to enable disk cache:
#CACHE_TYPE = os.getenv("CACHE_TYPE", "local")
litellm.cache = litellm.Cache(
    type="disk",
    disk_cache_dir="/mnt/cache",
    ttl=CACHE_TTL
)

# Enable caching globally
litellm.enable_cache()

# Set callbacks for logging (optional)
# litellm.success_callback = ["langfuse"]  # Uncomment for observability


# =============================================================================
# Core Functions (Direct SDK calls, no LangChain)
# =============================================================================

def retrieve_context(query: str, top_k: int = 3) -> str:
    """
    Retrieve relevant documents from Azure AI Search.
    
    This replaces LangChain's AzureAISearchRetriever with direct SDK calls.
    """
    try:
        results = search_client.search(
            search_text=query,
            top=top_k,
            select=["chunk"]  # Adjust field name based on your index schema
        )
        chunks = [doc["chunk"] for doc in results if "chunk" in doc]
        return "\n\n".join(chunks)
    except Exception as e:
        print(f"Search error: {e}")
        return ""


async def get_ai_response(question: str) -> dict:
    """
    Single function that retrieves context and gets LLM response.
    
    LiteLLM handles:
    - Response caching (identical questions return cached response instantly)
    - Automatic retries with exponential backoff
    - Rate limit handling
    - Token counting and cost tracking
    
    Returns dict with: response, is_job_related, rate_limited
    """
    # Retrieve context from Azure AI Search
    context = retrieve_context(question)
    
    # Build messages (plain dicts instead of LangChain message types)
    system_prompt = ASSISTANT_PROMPT.format(context=context)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]
    
    try:
        # Get fresh token for this request
        token = openai_token_provider()
        
        # LiteLLM async completion with caching
        response = await litellm.acompletion(
            model=f"azure/{DEPLOYMENT_NAME}",
            messages=messages,
            api_base=AZURE_ENDPOINT,
            api_key=token,  # Azure AD token
            api_version="2024-05-01-preview",
            caching=True,           # Enable response caching
            num_retries=3,          # Auto-retry on transient failures
            timeout=30,             # Request timeout in seconds
        )
        
        content = response.choices[0].message.content.strip()
        print(f"LLM response: '{content[:100]}...'")
        
        # Check if off-topic
        is_off_topic = content == "OFF_TOPIC" or content.startswith("OFF_TOPIC")
        
        return {
            "response": content,
            "is_job_related": not is_off_topic,
            "rate_limited": False
        }
        
    except litellm.RateLimitError:
        print("Hit LiteLLM rate limit")
        return {"response": "", "is_job_related": False, "rate_limited": True}
    except Exception as e:
        error_str = str(e).lower()
        if "429" in error_str or "rate limit" in error_str:
            print(f"Rate limit error: {e}")
            return {"response": "", "is_job_related": False, "rate_limited": True}
        print(f"LLM error: {e}")
        raise


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="Seif's AI Assistant API",
    description="An API to ask questions about Seif's expertise and contributions",
    version="2.0.0"  # Bumped version for new implementation
)

# Note: CORS not needed - this API is internal-only (ingressExternal: false)
# Only accessible by other containers in the same environment

# Fun messages for non-job-related queries
FUN_MESSAGES = [
    "🤖 Beep boop! That's not quite what I'm trained for. Try asking about Seif's professional expertise instead!",
    "🎮 Nice try! But I'm here to talk about jobs and careers, not to play games. Ask me about Seif's skills!",
    "🌟 Interesting question! But let's keep it professional. What would you like to know about Seif's experience?",
    "🚀 I'm an expert on Seif's career, not a general chatbot. Fire away with a job-related question!",
    "💼 My specialty is matching Seif's skills to your needs. Got a job description or career question?",
    "🎯 Off-topic alert! I'm laser-focused on helping you understand how Seif can contribute to your team.",
    "☕ That's a fun question, but I'm caffeinated only for career conversations. What role are you hiring for?",
    "🔮 My crystal ball only shows career paths! Ask me about Seif's professional background instead.",
]

# Fun messages for when Azure OpenAI rate limits us (429 errors)
GPU_OVERLOAD_MESSAGES = [
    "🔥 Whoa there! The GPUs are literally on fire right now. Those things are expensive! Give it a couple of minutes or reach out to Seif directly at seif@yourlink.com",
    "💸 Plot twist: GPUs cost more than my coffee addiction! Azure OpenAI needs a breather. Try again in a few minutes or just email Seif!",
    "🦾 The AI hamsters powering this thing need a water break. GPUs are pricey, you know! Wait a bit or contact Seif the old-fashioned way.",
    "⚡ Too many brain cells activated at once! The Azure OpenAI servers are sweating. Try again shortly or slide into Seif's inbox directly.",
    "🎰 You hit the jackpot... of rate limits! GPUs don't grow on trees. Give it 2 minutes or reach out to Seif - he's friendlier than this error anyway!",
    "🐢 Slow down, speed racer! The AI needs to catch its breath (and Azure needs to cool those expensive GPUs). Try again soon or contact Seif directly!",
    "💰 Fun fact: Every GPU cycle costs money, and we just ran out of cycles! Please try again in a couple minutes, or just reach out to Seif directly.",
    "🤯 The AI brain is overheating! Those GPUs are working overtime. Take a breather and try again, or skip the middleman and contact Seif!",
]


class QuestionRequest(BaseModel):
    """Request model for the ask endpoint."""
    question: str


class AnswerResponse(BaseModel):
    """Response model for the ask endpoint."""
    answer: str
    is_job_related: bool


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "healthy", "message": "Seif's AI Assistant is running (LiteLLM)!"}


@app.post("/ask", response_model=AnswerResponse)
async def ask_question(question_request: QuestionRequest):
    """
    Process a question using direct Azure SDK + LiteLLM.

    Returns the LLM response if the question is job-related,
    otherwise returns a fun message.

    Features:
    - Response caching via LiteLLM (instant responses for repeated questions)
    - Automatic retries with exponential backoff
    - LiteLLM handles Azure OpenAI rate limits gracefully
    """
    # Strip whitespace from input
    question = question_request.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # Server-side validation (defense-in-depth, matches client maxlength)
    if len(question) > 1200:
        raise HTTPException(status_code=400, detail="Question too long (max 1200 characters)")

    try:
        result = await get_ai_response(question)

        # Check if we hit Azure OpenAI rate limits
        if result.get("rate_limited"):
            return AnswerResponse(
                answer=random.choice(GPU_OVERLOAD_MESSAGES),
                is_job_related=False
            )

        # Return LLM response or fun message for off-topic
        if result["is_job_related"]:
            return AnswerResponse(
                answer=result["response"],
                is_job_related=True
            )
        else:
            return AnswerResponse(
                answer=random.choice(FUN_MESSAGES),
                is_job_related=False
            )

    except Exception as e:
        import traceback
        print(f"Error processing question: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error processing question: {str(e)}")


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
