"""
LangGraph Agent API for Job Classification and Expertise Retrieval

This module implements a FastAPI service with a single-call RAG agent:
- Retrieves context from Azure AI Search
- Single LLM call classifies AND responds (or returns OFF_TOPIC)
"""

import os
import random
from pathlib import Path
from typing import TypedDict

import yaml
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from langchain_community.retrievers import AzureAISearchRetriever
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph, START, END
from openai import RateLimitError

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


# =============================================================================
# State Schema
# =============================================================================

class AgentState(TypedDict):
    """State that flows through the graph."""
    input: str           # User's input query
    response: str        # LLM response (or "OFF_TOPIC")
    is_job_related: bool # Whether the query was job-related
    rate_limited: bool   # Flag to indicate if we hit Azure OpenAI rate limit


# =============================================================================
# Azure Clients Configuration
# =============================================================================

# DefaultAzureCredential tries multiple auth methods in order:
# Environment -> Workload Identity -> Managed Identity -> Azure CLI -> Azure PowerShell -> Azure Developer CLI
credential = DefaultAzureCredential()

# Token providers for Azure services
openai_token_provider = get_bearer_token_provider(
    credential, "https://cognitiveservices.azure.com/.default"
)
search_token = get_bearer_token_provider(
    credential, "https://search.azure.com/.default"
)()

# Azure OpenAI LLM client
llm = AzureChatOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    azure_deployment=os.getenv("AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME"),
    azure_ad_token_provider=openai_token_provider,
    api_version="2024-05-01-preview",
)

# Azure AI Search retriever for RAG
retriever = AzureAISearchRetriever(
    api_key=None,
    azure_ad_token=search_token,
    service_name=os.getenv("AZURE_SEARCH_INSTANCE_NAME"),
    index_name=os.getenv("AZURE_SEARCH_INDEX_NAME"),
    top_k=3,
    content_key="chunk",
)


# =============================================================================
# Prompt Templates (loaded from external configuration)
# =============================================================================

ASSISTANT_PROMPT = PROMPTS["assistant_prompt"]


# =============================================================================
# Agent Node (Single LLM Call)
# =============================================================================

def assistant_agent(state: AgentState) -> dict:
    """
    Single agent that:
    1. Retrieves RAG context
    2. Makes ONE LLM call that classifies AND responds
    
    Returns OFF_TOPIC for non-job-related queries.
    Handles Azure OpenAI rate limit (429) errors gracefully.
    """
    try:
        # Retrieve relevant documents
        docs = retriever.invoke(state["input"])
        context = "\n\n".join(doc.page_content for doc in docs) if docs else ""
        
        # Build prompt with context
        system_prompt = ASSISTANT_PROMPT.format(context=context)
        
        # Single LLM call - classifies and responds
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=state["input"])
        ])
        
        content = response.content.strip()
        print(f"LLM response: '{content[:100]}...'")
        
        # Check if off-topic
        is_off_topic = content == "OFF_TOPIC" or content.startswith("OFF_TOPIC")
        
        return {
            "response": content,
            "is_job_related": not is_off_topic,
            "rate_limited": False
        }
    except RateLimitError:
        return {"response": "", "is_job_related": False, "rate_limited": True}
    except Exception as e:
        if "429" in str(e) or "rate limit" in str(e).lower():
            return {"response": "", "is_job_related": False, "rate_limited": True}
        raise


# =============================================================================
# Graph Builder
# =============================================================================

def build_graph():
    """
    Builds a simple LangGraph workflow:
    START -> assistant_agent -> END
    """
    workflow = StateGraph(AgentState)
    workflow.add_node("assistant_agent", assistant_agent)
    workflow.add_edge(START, "assistant_agent")
    workflow.add_edge("assistant_agent", END)
    return workflow.compile()


# =============================================================================
# FastAPI Application
# =============================================================================

# Initialize rate limiter
# Uses IP address for rate limiting
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Seif's AI Assistant API",
    description="An API to ask questions about Seif's expertise and contributions",
    version="1.0.0"
)

# Custom rate limit exceeded handler with fun messages
RATE_LIMIT_MESSAGES = [
    "🚦 We've hit our AI request limit! Please try again in about a minute, or reach out to Seif directly.",
    "⏰ Too many AI requests at once! The limit resets in about a minute - try again shortly or contact Seif directly.",
    "🤖 Our AI is taking a quick breather (request limit reached). Please wait about a minute and try again!",
    "⚡ AI request limit reached! Give it a minute to reset, or skip the AI and reach out to Seif directly.",
    "☕ Hit the AI request cap! Try again in about a minute, or feel free to contact Seif the old-fashioned way.",
]

def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Custom handler for rate limit exceeded - returns fun message."""
    return JSONResponse(
        status_code=429,
        content={
            "answer": random.choice(RATE_LIMIT_MESSAGES),
            "is_job_related": False
        }
    )

# Add rate limiter to app state and register custom exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)

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


# Build the graph once at startup
graph = build_graph()


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "healthy", "message": "Seif's AI Assistant is running!"}


@app.post("/ask", response_model=AnswerResponse)
@limiter.limit("3/minute")  # Rate limit: 3 requests per minute per IP
async def ask_question(request: Request, question_request: QuestionRequest):
    """
    Process a question through the LangGraph agent.

    Returns the LLM response if the question is job-related,
    otherwise returns a fun message.

    Rate limited to 10 requests per minute per IP address.
    """
    # Strip whitespace from input
    question = question_request.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # Server-side validation (defense-in-depth, matches client maxlength)
    if len(question) > 4000:
        raise HTTPException(status_code=400, detail="Question too long (max 4000 characters)")

    try:
        result = await graph.ainvoke({
            "input": question,
            "response": "",
            "is_job_related": False,
            "rate_limited": False
        })

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