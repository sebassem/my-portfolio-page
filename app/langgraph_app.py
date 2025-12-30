"""
LangGraph Agent API for Job Classification and Expertise Retrieval

This module implements a FastAPI service with a two-stage agent workflow:
1. Classification Agent - Determines if input is job/career related
2. Contributions Agent - Uses RAG to retrieve relevant expertise (only for job-related inputs)
"""

import os
import random
from pathlib import Path
from typing import Literal, TypedDict

import yaml
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from langchain_community.retrievers import AzureAISearchRetriever
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
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
    classification: str  # "Job Description" or "General Prompt"
    expertise: str       # Retrieved expertise from RAG
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
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
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

CLASSIFICATION_SYSTEM_PROMPT = PROMPTS["classification_prompt"]

RAG_PROMPT = ChatPromptTemplate.from_messages([
    ("system", PROMPTS["rag_system_prompt"]),
    ("human", PROMPTS["rag_human_prompt"])
])


# =============================================================================
# Agent Nodes
# =============================================================================

def classification_agent(state: AgentState) -> dict:
    """
    Classifies the input as job-related or general.
    Returns 'Job Description' or 'General Prompt'.
    Handles Azure OpenAI rate limit (429) errors gracefully.
    """
    try:
        response = llm.invoke([
            SystemMessage(content=CLASSIFICATION_SYSTEM_PROMPT),
            HumanMessage(content=state["input"])
        ])

        content = response.content.strip()
        classification = "Job Description" if "Job Description" in content else "General Prompt"

        return {"classification": classification, "rate_limited": False}
    except RateLimitError:
        return {"classification": "Rate Limited", "rate_limited": True}
    except Exception as e:
        # Check if the underlying cause is a rate limit error
        if "429" in str(e) or "rate limit" in str(e).lower():
            return {"classification": "Rate Limited", "rate_limited": True}
        raise


def contributions_agent(state: AgentState) -> dict:
    """
    Uses RAG to retrieve relevant expertise from Azure AI Search.
    Only runs when classification is 'Job Description'.
    Handles Azure OpenAI rate limit (429) errors gracefully.
    """
    try:
        # Retrieve relevant documents
        docs = retriever.invoke(state["input"])
        context = "\n\n".join(doc.page_content for doc in docs)

        # Build and execute RAG chain
        chain = RAG_PROMPT | llm | StrOutputParser()
        expertise = chain.invoke({
            "context": context,
            "question": f"Based on the job description: {state['input']}\n\nWhat relevant contributions and expertise can you find?"
        })

        return {"expertise": expertise, "rate_limited": False}
    except RateLimitError:
        return {"expertise": "", "rate_limited": True}
    except Exception as e:
        # Check if the underlying cause is a rate limit error
        if "429" in str(e) or "rate limit" in str(e).lower():
            return {"expertise": "", "rate_limited": True}
        raise


# =============================================================================
# Graph Routing
# =============================================================================

def route_by_classification(state: AgentState) -> Literal["contributions_agent", "__end__"]:
    """Routes to contributions_agent only for job-related prompts, ends early if rate limited."""
    if state.get("rate_limited"):
        return "__end__"
    if state["classification"] == "Job Description":
        return "contributions_agent"
    return "__end__"


# =============================================================================
# Graph Builder
# =============================================================================

def build_graph():
    """
    Builds the LangGraph workflow:

    START -> classification_agent -> [Job Description?] -> contributions_agent -> END
                                  -> [General Prompt?]  -> END
    """
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("classification_agent", classification_agent)
    workflow.add_node("contributions_agent", contributions_agent)

    # Define edges
    workflow.add_edge(START, "classification_agent")
    workflow.add_conditional_edges("classification_agent", route_by_classification)
    workflow.add_edge("contributions_agent", END)

    return workflow.compile()


# =============================================================================
# FastAPI Application
# =============================================================================

# Initialize rate limiter
# Uses IP address for rate limiting, 10 requests per minute
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Seif's AI Assistant API",
    description="An API to ask questions about Seif's expertise and contributions",
    version="1.0.0"
)

# Add rate limiter to app state and register exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    if not question_request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        result = await graph.ainvoke({
            "input": question_request.question,
            "classification": "",
            "expertise": "",
            "rate_limited": False
        })

        # Check if we hit Azure OpenAI rate limits
        if result.get("rate_limited"):
            return AnswerResponse(
                answer=random.choice(GPU_OVERLOAD_MESSAGES),
                is_job_related=False
            )

        is_job_related = result["classification"] == "Job Description"

        if is_job_related and result.get("expertise"):
            return AnswerResponse(
                answer=result["expertise"],
                is_job_related=True
            )
        else:
            return AnswerResponse(
                answer=random.choice(FUN_MESSAGES),
                is_job_related=False
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing question: {str(e)}")


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)