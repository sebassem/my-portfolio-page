"""
Seif's AI Assistant API
=======================
A FastAPI-based AI assistant that answers questions about Seif's professional expertise.

Architecture:
- Azure AI Search for RAG (Retrieval Augmented Generation)
- Azure OpenAI SDK for LLM inference
- Server-Sent Events (SSE) for real-time streaming responses

Caching:
- Default: In-memory TTL cache (works with scale-to-zero, resets on cold start)

Rate Limiting:
- Default: In-memory (resets on container restart)
- Optional: Azure Table Storage for persistent rate limiting across restarts
Set AZURE_STORAGE_ACCOUNT_NAME env var to enable persistent storage
"""

import os
import random
from pathlib import Path
from typing import AsyncGenerator, Dict, List

import hashlib
import json
import time

import limits.storage as limits_storage
import yaml
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from cachetools import TTLCache
from openai import AsyncAzureOpenAI, AzureOpenAI, RateLimitError
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
CLASSIFICATION_PROMPT = PROMPTS["classification_prompt"]


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
EMBEDDING_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME")

# Azure OpenAI client for embeddings (sync)
openai_client = AzureOpenAI(
    azure_endpoint=AZURE_ENDPOINT,
    azure_ad_token_provider=openai_token_provider,
    api_version="2024-05-01-preview"
)

# Azure OpenAI client for chat completions (async)
async_openai_client = AsyncAzureOpenAI(
    azure_endpoint=AZURE_ENDPOINT,
    azure_ad_token_provider=openai_token_provider,
    api_version="2024-05-01-preview"
)

# Search index vector field name
SEARCH_VECTOR_FIELD = os.getenv("AZURE_SEARCH_VECTOR_FIELD", "text_vector")


# =============================================================================
# Response Cache Configuration
# =============================================================================

# In-memory TTL cache for LLM responses (resets on cold start)
_response_cache: TTLCache = TTLCache(maxsize=256, ttl=CACHE_TTL)


def _cache_key(model: str, messages: list, **kwargs) -> str:
    """Generate a deterministic cache key from the request parameters."""
    key_data = json.dumps({"model": model, "messages": messages, **kwargs}, sort_keys=True)
    return hashlib.sha256(key_data.encode()).hexdigest()


# =============================================================================
# Rate Limiting Configuration
# =============================================================================

def get_client_ip(request: Request) -> str:
    """
    Extract the real client IP address from trusted proxy headers.
    
    Priority order (most trusted first):
    1. CF-Connecting-IP: Set by Cloudflare, cannot be spoofed by clients
    2. X-Real-IP: Set by trusted reverse proxies (nginx, etc.)
    3. X-Forwarded-For: Can be spoofed, used as last resort
    4. Direct connection IP: Fallback when no proxy headers present
    
    Args:
        request: FastAPI request object
        
    Returns:
        Client IP address string
    """
    # Cloudflare's verified client IP (most trusted - Cloudflare overwrites this)
    cf_connecting_ip = request.headers.get("cf-connecting-ip")
    if cf_connecting_ip:
        return cf_connecting_ip.strip()
    
    # X-Real-IP from trusted reverse proxy
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    
    # X-Forwarded-For as fallback (take rightmost non-private IP if possible)
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # First IP in the list is the original client (added by first proxy)
        # Note: In production with Cloudflare, CF-Connecting-IP should be used instead
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

def get_embedding(text: str) -> list[float]:
    """
    Generate embedding vector for text using Azure OpenAI.
    
    Args:
        text: Text to embed
        
    Returns:
        Embedding vector as list of floats
    """
    response = openai_client.embeddings.create(
        input=text,
        model=EMBEDDING_DEPLOYMENT_NAME
    )
    return response.data[0].embedding


def retrieve_context(query: str, top_k: int = SEARCH_TOP_K) -> str:
    """
    Retrieve relevant document chunks from Azure AI Search using hybrid + semantic search.
    
    Performs hybrid search (keyword + vector) with semantic ranking to find the most
    relevant portfolio content. The semantic ranker uses a cross-encoder model to
    re-rank results for better relevance.
    
    Args:
        query: User's question
        top_k: Number of documents to retrieve
        
    Returns:
        Concatenated document chunks as context string
    """
    try:
        # Generate embedding for the query
        query_embedding = get_embedding(query)

        # Get semantic configuration name - use explicit env var or construct from index name
        index_name = os.getenv('AZURE_SEARCH_INDEX_NAME')
        default_semantic_config = f"{index_name}-semantic-configuration" if index_name else "portfolio-rag-index-semantic-configuration"
        semantic_config = os.getenv("AZURE_SEARCH_SEMANTIC_CONFIG", default_semantic_config)
        print(f"🔍 Searching with semantic config: {semantic_config}")

        # Hybrid search with semantic ranking
        results = search_client.search(
            search_text=query,  # Keyword search component
            vector_queries=[
                VectorizedQuery(
                    vector=query_embedding,
                    k_nearest_neighbors=top_k,
                    fields=SEARCH_VECTOR_FIELD
                )
            ],
            query_type="semantic",  # Enable semantic ranking
            semantic_configuration_name=semantic_config,
            top=top_k,
            select=["chunk"]  # Field name from search index schema
        )
        
        # Convert to list to actually execute the search
        results_list = list(results)
        chunks = [doc["chunk"] for doc in results_list if "chunk" in doc]
        total_chars = sum(len(c) for c in chunks)
        print(f"🔍 Search: {len(results_list)} results, {len(chunks)} chunks, {total_chars} chars")
        return "\n\n".join(chunks)
    except Exception as e:
        print(f"❌ Search error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
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
    if isinstance(exception, RateLimitError):
        return True
    error_str = str(exception).lower()
    return "429" in error_str or "rate limit" in error_str


async def classify_question(question: str) -> bool:
    """
    Lightweight classification to determine if a question is job/career relevant.
    
    This is Stage 1 of the two-stage approach - uses minimal tokens (~150 input, ~10 output)
    to filter off-topic questions BEFORE expensive RAG retrieval.
    
    Args:
        question: User's sanitized question
        
    Returns:
        True if the question is relevant (should proceed to RAG), False if off-topic
    """
    try:
        # Build lightweight classification prompt (no RAG context needed)
        classification_message = CLASSIFICATION_PROMPT.format(question=question)
        
        response = await async_openai_client.chat.completions.create(
            model=DEPLOYMENT_NAME,
            messages=[
                {"role": "user", "content": classification_message}
            ],
            max_tokens=10,
            temperature=0,  # Deterministic classification
            timeout=10,
        )
        
        # Parse response - look for TRUE or FALSE in the response
        content = response.choices[0].message.content.strip().upper()
        print(f"🏷️ Raw classification response: {content}")
        
        # Check for false indicators first (more specific)
        is_relevant = not ("FALSE" in content or "OFF_TOPIC" in content or "OFF-TOPIC" in content)
        
        print(f"🏷️ Classification: '{question[:50]}...' -> is_relevant={is_relevant}")
        return is_relevant
        
    except Exception as e:
        print(f"⚠️ Classification error: {e}. Defaulting to relevant (will use RAG).")
        # On error, default to relevant to avoid blocking legitimate questions
        return True


async def stream_ai_response(question: str) -> AsyncGenerator[str, None]:
    """
    Stream LLM response chunks as Server-Sent Events.

    This function uses a two-stage approach for token efficiency:
    1. Lightweight classification (~150 tokens) to filter off-topic questions
    2. Full RAG retrieval + response only for relevant questions

    Args:
        question: User's sanitized question

    Yields:
        SSE-formatted message strings
    """
    # Stage 1: Lightweight classification (no RAG, minimal tokens)
    is_relevant = await classify_question(question)
    
    if not is_relevant:
        # Off-topic: return fun message without expensive RAG retrieval
        print(f"⏭️ Skipping RAG for off-topic question: '{question[:50]}...'")
        async for msg in create_fun_message_stream():
            yield msg
        return
    
    # Stage 2: Question is relevant - proceed with full RAG pipeline
    # Retrieve relevant context from portfolio documents
    context = retrieve_context(question)
    
    if not context:
        print("⚠️ WARNING: No context retrieved from RAG")

    # Build the conversation messages
    system_prompt = ASSISTANT_PROMPT.format(context=context)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]

    try:
        # Call Azure OpenAI with streaming
        response = await async_openai_client.chat.completions.create(
            model=DEPLOYMENT_NAME,
            messages=messages,
            stream=True,
            max_tokens=1024,
            temperature=0.3,
            timeout=60,  # Longer timeout for streaming
        )

        # Stream response chunks directly (no buffering needed)
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                yield sse_message(content=content)

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
