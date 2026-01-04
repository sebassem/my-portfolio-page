"""
Simplified AI Assistant API using Azure SDK + LiteLLM
Caching:
- Default: In-memory local cache (works with scale-to-zero, resets on cold start)
- Optional: Disk cache with Azure Files mount for persistent caching (see code comments)
"""

import os
import re
import random
from pathlib import Path
from typing import Tuple

import yaml
import litellm
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

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

# Azure AI Search
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
litellm.cache = litellm.Cache(type="local", ttl=CACHE_TTL)

# -----------------------------------------------------------------------------
# OPTIONAL: Persistent Disk Cache with Azure Files Mount
# -----------------------------------------------------------------------------
# To enable disk caching with Azure Files, uncomment below and configure
# the volume mount in your Container App Bicep (requires shared key access on storage)
#
# litellm.cache = litellm.Cache(
#     type="disk",
#     disk_cache_dir="/mnt/cache",
#     ttl=CACHE_TTL
# )

# Enable caching globally
litellm.enable_cache()

# Set callbacks for logging (optional)
# litellm.success_callback = ["langfuse"]  # Uncomment for observability


# =============================================================================
# Rate Limiting (SlowAPI) & Input Sanitization
# =============================================================================

# Custom key function to handle X-Forwarded-For from Container Apps proxy
def get_client_ip(request: Request) -> str:
    """Extract client IP, handling proxies."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)

# Initialize rate limiter with in-memory storage (resets on restart, fine for scale-to-zero)
# Rate limit: 10 requests per minute per IP (configurable via env)
RATE_LIMIT = os.getenv("RATE_LIMIT", "10/minute")
limiter = Limiter(key_func=get_client_ip)

# Patterns that might indicate prompt injection or malicious input
# Note: LiteLLM's moderation() is for harmful content, not prompt injection
SUSPICIOUS_PATTERNS = [
    r"ignore\s+(previous|above|all)\s+instructions?",
    r"disregard\s+(previous|above|all)",
    r"forget\s+(everything|previous|above)",
    r"you\s+are\s+now",
    r"new\s+instructions?",
    r"system\s*:\s*",
    r"<\s*script",
    r"javascript\s*:",
    r"\{\{.*\}\}",  # Template injection
    r"\$\{.*\}",    # Variable injection
]

# Compile patterns for performance
COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in SUSPICIOUS_PATTERNS]


def sanitize_input(text: str) -> Tuple[str, bool]:
    """
    Sanitize user input to prevent prompt injection attacks.
    
    Returns:
        Tuple of (sanitized_text, is_suspicious)
    """
    # Check for suspicious patterns
    for pattern in COMPILED_PATTERNS:
        if pattern.search(text):
            return text, True
    
    # Remove potential control characters (except newlines and tabs)
    sanitized = ''.join(char for char in text if char.isprintable() or char in '\n\t')
    
    # Normalize excessive whitespace
    sanitized = re.sub(r'\s{10,}', ' ', sanitized)
    
    return sanitized, False


# =============================================================================
# Core Functions
# =============================================================================

def retrieve_context(query: str, top_k: int = 3) -> str:
    """
    Retrieve relevant documents from Azure AI Search.
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
    
    # Build messages
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
            max_tokens=1024,        # Balanced for detailed responses with examples
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


async def stream_ai_response(question: str):
    """
    Async generator that streams LLM response chunks.
    
    Yields Server-Sent Events (SSE) formatted data.
    Note: Streaming bypasses caching - each request hits the LLM.
    """
    import json
    
    # Retrieve context from Azure AI Search
    context = retrieve_context(question)
    
    # Build messages
    system_prompt = ASSISTANT_PROMPT.format(context=context)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]
    
    try:
        # Get fresh token for this request
        token = openai_token_provider()
        
        # LiteLLM async streaming completion
        response = await litellm.acompletion(
            model=f"azure/{DEPLOYMENT_NAME}",
            messages=messages,
            api_base=AZURE_ENDPOINT,
            api_key=token,
            api_version="2024-05-01-preview",
            stream=True,            # Enable streaming
            max_tokens=1024,        # Balanced for detailed responses with examples
            num_retries=3,
            timeout=60,             # Longer timeout for streaming
        )
        
        # Collect full response to check for OFF_TOPIC
        full_response = ""
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
        
        # Check if the response is off-topic
        is_off_topic = full_response.strip() == "OFF_TOPIC" or full_response.strip().startswith("OFF_TOPIC")
        
        if is_off_topic:
            # Return a fun message instead of "OFF_TOPIC"
            fun_message = random.choice(FUN_MESSAGES)
            yield f"data: {json.dumps({'content': fun_message})}\n\n"
            yield f"data: {json.dumps({'done': True, 'is_job_related': False})}\n\n"
        else:
            # Stream the actual response
            yield f"data: {json.dumps({'content': full_response})}\n\n"
            # Send done event
            yield f"data: {json.dumps({'done': True})}\n\n"
        
    except litellm.RateLimitError:
        print("Hit LiteLLM rate limit during streaming")
        yield f"data: {json.dumps({'error': 'rate_limited'})}\n\n"
    except Exception as e:
        error_str = str(e).lower()
        if "429" in error_str or "rate limit" in error_str:
            print(f"Rate limit error during streaming: {e}")
            yield f"data: {json.dumps({'error': 'rate_limited'})}\n\n"
        else:
            print(f"LLM streaming error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="Seif's AI Assistant API",
    description="An API to ask questions about Seif's expertise and contributions",
    version="2.0.0"  # Bumped version for new implementation
)

# Register rate limiter with FastAPI
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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


@app.post("/ask")
@limiter.limit(RATE_LIMIT)
async def ask_question(request: Request, question_request: QuestionRequest):
    """
    Process a question using direct Azure SDK + LiteLLM with streaming.

    Returns a Server-Sent Events (SSE) stream of the LLM response.

    Features:
    - Real-time streaming response (word by word)
    - Automatic retries with exponential backoff
    - Rate limiting via SlowAPI (10/minute per IP by default)
    - Input sanitization to prevent prompt injection
    
    Note: Streaming bypasses response caching.
    """
    import json
    
    # Strip whitespace from input
    question = question_request.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # Server-side validation (defense-in-depth, matches client maxlength)
    if len(question) > 4000:
        raise HTTPException(status_code=400, detail="Question too long (max 4000 characters)")
    
    # Sanitize input and check for suspicious patterns
    question, is_suspicious = sanitize_input(question)
    
    if is_suspicious:
        # Log suspicious input for monitoring (don't expose details to client)
        client_ip = get_client_ip(request)
        print(f"Suspicious input detected from {client_ip}: {question[:100]}...")
        # Return fun message as SSE for suspicious input
        async def suspicious_response():
            msg = random.choice(FUN_MESSAGES)
            yield f"data: {json.dumps({'content': msg})}\n\n"
            yield f"data: {json.dumps({'done': True, 'is_job_related': False})}\n\n"
        return StreamingResponse(
            suspicious_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            }
        )

    # Return streaming response
    return StreamingResponse(
        stream_ai_response(question),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
