"""
Seif's AI Assistant API
=======================
A FastAPI-based AI assistant that answers questions about Seif's professional expertise.

Architecture:
- Azure AI Search for RAG (Retrieval Augmented Generation)
- Azure OpenAI via LiteLLM for LLM inference
- Server-Sent Events (SSE) for real-time streaming responses

Caching:
- Default: In-memory local cache (works with scale-to-zero, resets on cold start)
- Optional: Disk cache with Azure Files mount for persistent caching

Rate Limiting:
- Default: In-memory (resets on container restart)
- Optional: Azure Table Storage for persistent rate limiting across restarts
  Set AZURE_STORAGE_ACCOUNT_NAME env var to enable persistent storage
"""

import os
import random
from pathlib import Path
from typing import AsyncGenerator, Dict, List

import limits.storage as limits_storage
import litellm
import yaml
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from limits.strategies import FixedWindowRateLimiter
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

# Local imports
from services.sanitization import sanitize_input
from services.streaming import (
    sse_message,
    create_fun_message_stream,
    get_sse_headers,
    FUN_MESSAGES,
)
from storage.azure_table_storage import AzureTableStorage

# Load environment variables from .env file (for local development)
load_dotenv()


# =============================================================================
# Configuration Constants
# =============================================================================

# Cache time-to-live in seconds (default: 1 hour)
CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", "3600"))

# Rate limit for API requests (default: 3 requests per week per IP)
# Note: limits library supports second/minute/hour/day/month/year
# For weekly, use "3/day" format
RATE_LIMIT = os.getenv("RATE_LIMIT", "3/day")

# Maximum question length (matches client-side validation)
MAX_QUESTION_LENGTH = 4000

# Number of documents to retrieve from search
SEARCH_TOP_K = 5

# Buffer size for detecting OFF_TOPIC responses before streaming
OFF_TOPIC_BUFFER_SIZE = 20


# =============================================================================
# Response Messages
# =============================================================================

# Fun messages for rate limit exceeded (application-level rate limiting)
RATE_LIMIT_MESSAGES: List[str] = [
    "🎫 Whoa, you've used all your questions for today! Seif's AI assistant needs a breather. Come back tomorrow or just reach out to Seif directly!",
    "🏆 Achievement unlocked: Power User! You've hit your daily limit. The AI needs to recharge - try again tomorrow or contact Seif!",
    "📊 Plot twist: You're so curious that you've maxed out your daily quota! Come back tomorrow, or skip the queue and email Seif directly.",
    "⏰ Time flies when you're having fun! You've asked enough questions for today. The counter resets tomorrow - or just reach out to Seif now!",
    "🎯 Hat trick! You've hit your daily limit. Either you really like this AI, or you really want to hire Seif. Why not contact him directly?",
    "🔋 Battery low! This AI runs on limited daily juice. Recharge tomorrow or go straight to the source - Seif himself!",
    "🎪 The show's over for today! Come back tomorrow for more, or get a private show by contacting Seif directly!",
    "🚦 Red light! You've crossed the finish line for today. Pit stop until tomorrow, or take the direct route to Seif's inbox!",
]


# =============================================================================
# Prompt Configuration
# =============================================================================

def load_prompts(prompts_path: str = None) -> Dict:
    """
    Load system prompts from external YAML configuration file.
    
    Args:
        prompts_path: Path to YAML file. Defaults to PROMPTS_FILE_PATH env var
                      or prompts.yaml in the same directory.
    
    Returns:
        Dictionary containing prompt configurations.
    """
    if prompts_path is None:
        prompts_path = os.getenv("PROMPTS_FILE_PATH", Path(__file__).parent / "prompts.yaml")

    with open(prompts_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# Load prompts at module startup
PROMPTS = load_prompts()
ASSISTANT_PROMPT = PROMPTS["assistant_prompt"]


# =============================================================================
# Azure Services Configuration
# =============================================================================

# DefaultAzureCredential authentication chain:
# Environment -> Workload Identity -> Managed Identity -> Azure CLI -> PowerShell -> Azure Developer CLI
credential = DefaultAzureCredential()

# Token provider for Azure OpenAI (returns fresh tokens automatically)
openai_token_provider = get_bearer_token_provider(
    credential, "https://cognitiveservices.azure.com/.default"
)

# Azure AI Search client for RAG context retrieval
search_client = SearchClient(
    endpoint=f"https://{os.getenv('AZURE_SEARCH_INSTANCE_NAME')}.search.windows.net",
    index_name=os.getenv("AZURE_SEARCH_INDEX_NAME"),
    credential=credential
)

# Azure OpenAI configuration
AZURE_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME")


# =============================================================================
# LiteLLM Configuration
# =============================================================================

# Configure in-memory cache for response caching
# Note: Cache resets on cold start but provides fast responses for repeated questions
litellm.cache = litellm.Cache(type="local", ttl=CACHE_TTL)

# Optional: Persistent disk cache with Azure Files mount
# Uncomment and configure volume mount in Container App Bicep for persistence:
# litellm.cache = litellm.Cache(type="disk", disk_cache_dir="/mnt/cache", ttl=CACHE_TTL)

# Enable caching globally
litellm.enable_cache()


# =============================================================================
# Rate Limiting Configuration
# =============================================================================

def get_client_ip(request: Request) -> str:
    """
    Extract the real client IP address, handling reverse proxy headers.
    
    Container Apps and other proxies add X-Forwarded-For header with the
    original client IP as the first value in the comma-separated list.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Client IP address string
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # First IP in the list is the original client
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


# Register custom storage backend with limits library
limits_storage.SCHEMES["azuretable"] = AzureTableStorage


def create_limiter() -> Limiter:
    """
    Create rate limiter with appropriate storage backend.
    
    Uses Azure Table Storage if AZURE_STORAGE_ACCOUNT_NAME is set,
    otherwise falls back to in-memory storage.
    
    Returns:
        Configured Limiter instance
    """
    storage_account = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
    
    if storage_account:
        try:
            # Test if we can connect to Azure Table Storage
            print(f"🔄 Attempting to connect to Azure Table Storage (account: {storage_account})...")
            azure_storage = AzureTableStorage(uri="azuretable://", credential=credential)
            if azure_storage.check():
                print(f"✅ Using Azure Table Storage for rate limiting (account: {storage_account})")
                # Create limiter with memory storage first (it will be overridden)
                new_limiter = Limiter(
                    key_func=get_client_ip,
                    storage_uri="memory://",
                )
                # Manually inject our Azure Table Storage into both _storage and _limiter
                new_limiter._storage = azure_storage
                new_limiter._limiter = FixedWindowRateLimiter(azure_storage)
                print("✅ Azure Table Storage injected into rate limiter")
                return new_limiter
            else:
                print("⚠️ Azure Table Storage check failed, falling back to in-memory")
        except Exception as e:
            print(f"⚠️ Failed to initialize Azure Table Storage: {e}")
            print("⚠️ Falling back to in-memory rate limiting")
    
    print("⚠️ Using in-memory rate limiting (will reset on restart)")
    return Limiter(key_func=get_client_ip)


# Initialize rate limiter (persistent with Azure Table Storage, or in-memory fallback)
limiter = create_limiter()


# =============================================================================
# Core AI Functions
# =============================================================================

def retrieve_context(query: str, top_k: int = SEARCH_TOP_K) -> str:
    """
    Retrieve relevant document chunks from Azure AI Search.
    
    Performs a semantic/hybrid search to find the most relevant
    portfolio content for the user's question.
    
    Args:
        query: User's question
        top_k: Number of documents to retrieve
        
    Returns:
        Concatenated document chunks as context string
    """
    try:
        results = search_client.search(
            search_text=query,
            top=top_k,
            select=["chunk"]  # Field name from search index schema
        )
        chunks = [doc["chunk"] for doc in results if "chunk" in doc]
        return "\n\n".join(chunks)
    except Exception as e:
        print(f"Search error: {e}")
        return ""


def is_rate_limit_error(exception: Exception) -> bool:
    """
    Check if an exception indicates a rate limit error.
    
    Azure OpenAI returns 429 status codes when rate limited.
    
    Args:
        exception: The caught exception
        
    Returns:
        True if this is a rate limit error
    """
    if isinstance(exception, litellm.RateLimitError):
        return True
    error_str = str(exception).lower()
    return "429" in error_str or "rate limit" in error_str


async def stream_ai_response(question: str) -> AsyncGenerator[str, None]:
    """
    Stream LLM response chunks as Server-Sent Events.
    
    This function:
    1. Retrieves relevant context from Azure AI Search
    2. Calls Azure OpenAI with streaming enabled
    3. Buffers initial response to detect OFF_TOPIC before streaming
    4. Yields SSE-formatted chunks for real-time display
    
    Note: Streaming bypasses LiteLLM's response cache.
    
    Args:
        question: User's sanitized question
        
    Yields:
        SSE-formatted message strings
    """
    # Step 1: Retrieve relevant context from portfolio documents
    context = retrieve_context(question)
    
    # Step 2: Build the conversation messages
    system_prompt = ASSISTANT_PROMPT.format(context=context)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]
    
    try:
        # Get fresh Azure AD token for this request
        token = openai_token_provider()
        
        # Step 3: Call Azure OpenAI with streaming
        response = await litellm.acompletion(
            model=f"azure/{DEPLOYMENT_NAME}",
            messages=messages,
            api_base=AZURE_ENDPOINT,
            api_key=token,
            api_version="2024-05-01-preview",
            stream=True,
            max_tokens=1024,
            num_retries=3,
            temperature=0.3,
            timeout=60,  # Longer timeout for streaming
        )
        
        # Step 4: Buffer initial chunks to detect OFF_TOPIC
        # We need to check if the response starts with "OFF_TOPIC" before streaming
        buffer = ""
        streaming_started = False
        
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                
                if not streaming_started:
                    # Still buffering to detect OFF_TOPIC
                    buffer += content
                    
                    # Check if we have enough content to determine if it's off-topic
                    if len(buffer) >= OFF_TOPIC_BUFFER_SIZE or "OFF_TOPIC" in buffer:
                        if buffer.strip().startswith("OFF_TOPIC"):
                            # Off-topic detected: return fun message instead
                            async for msg in create_fun_message_stream():
                                yield msg
                            return
                        else:
                            # Not off-topic: flush buffer and start streaming
                            streaming_started = True
                            yield sse_message(content=buffer)
                else:
                    # Normal streaming mode
                    yield sse_message(content=content)
        
        # Handle case where response was shorter than buffer limit
        if not streaming_started and buffer:
            if buffer.strip().startswith("OFF_TOPIC"):
                async for msg in create_fun_message_stream():
                    yield msg
                return
            else:
                yield sse_message(content=buffer)
        
        # Send completion event
        yield sse_message(done=True)
        
    except Exception as e:
        if is_rate_limit_error(e):
            print(f"Rate limit error during streaming: {e}")
            yield sse_message(error="rate_limited")
        else:
            print(f"LLM streaming error: {e}")
            yield sse_message(error=str(e))


# =============================================================================
# FastAPI Application Setup
# =============================================================================

app = FastAPI(
    title="Seif's AI Assistant API",
    description="An API to ask questions about Seif's expertise and contributions",
    version="2.0.0",
)


async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Custom handler for rate limit exceeded errors."""
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": random.choice(RATE_LIMIT_MESSAGES)
        }
    )


# Register rate limiter middleware
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)

# Note: CORS not configured - this API is internal-only (ingressExternal: false)
# Only accessible by other containers in the same Container Apps environment


# =============================================================================
# Request/Response Models
# =============================================================================

class QuestionRequest(BaseModel):
    """Request body for the /ask endpoint."""
    question: str


class AnswerResponse(BaseModel):
    """Response body for non-streaming responses."""
    answer: str
    is_job_related: bool


# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/")
async def root() -> Dict[str, str]:
    """
    Health check endpoint.
    
    Returns:
        Status message indicating the service is running
    """
    return {
        "status": "healthy",
        "message": "Seif's AI Assistant is running!"
    }


@app.post("/ask")
@limiter.limit(RATE_LIMIT)
async def ask_question(request: Request, question_request: QuestionRequest) -> StreamingResponse:
    """
    Process a question and stream the AI response.
    
    This endpoint:
    1. Validates and sanitizes the input
    2. Checks for prompt injection attempts
    3. Streams the LLM response as Server-Sent Events
    
    Features:
    - Real-time streaming response (word by word)
    - Automatic retries with exponential backoff
    - Rate limiting (10/minute per IP by default)
    - Input sanitization for security
    
    Args:
        request: FastAPI request object (used for rate limiting)
        question_request: Request body containing the question
        
    Returns:
        StreamingResponse with SSE-formatted chunks
        
    Raises:
        HTTPException: If question is empty or too long
    """
    # Validate input
    question = question_request.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    if len(question) > MAX_QUESTION_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Question too long (max {MAX_QUESTION_LENGTH} characters)"
        )
    
    # Sanitize input and check for prompt injection
    question, is_suspicious = sanitize_input(question)
    
    if is_suspicious:
        # Log for security monitoring (don't expose details to client)
        client_ip = get_client_ip(request)
        print(f"⚠️ Suspicious input detected from {client_ip}: {question[:100]}...")
        
        # Return a fun deflection message
        return StreamingResponse(
            create_fun_message_stream(),
            media_type="text/event-stream",
            headers=get_sse_headers(),
        )

    # Stream the AI response
    return StreamingResponse(
        stream_ai_response(question),
        media_type="text/event-stream",
        headers=get_sse_headers(),
    )


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
