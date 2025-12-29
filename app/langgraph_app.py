"""
LangGraph Agent API for Job Classification and Expertise Retrieval

This module implements a FastAPI service with a two-stage agent workflow:
1. Classification Agent - Determines if input is job/career related
2. Contributions Agent - Uses RAG to retrieve relevant expertise (only for job-related inputs)
"""

import os
import random
from typing import Literal, TypedDict
from azure.identity import AzureCliCredential, get_bearer_token_provider
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_community.retrievers import AzureAISearchRetriever
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph, START, END

load_dotenv()


# =============================================================================
# State Schema
# =============================================================================

class AgentState(TypedDict):
    """State that flows through the graph."""
    input: str           # User's input query
    classification: str  # "Job Description" or "General Prompt"
    expertise: str       # Retrieved expertise from RAG


# =============================================================================
# Azure Clients Configuration
# =============================================================================

credential = AzureCliCredential()

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
# Prompt Templates
# =============================================================================

CLASSIFICATION_SYSTEM_PROMPT = """You are a prompt classification agent to help understand if a provided prompt is job or career related, specially in Technology.
When provided a prompt, you will figure out if its a job description or related to a specific task in a job or career related.
If it is, classify it as 'Job Description'.
## Example 1:
The CSA role is a customer-facing, hands-on technical position responsible for:

- Leading technical engagements across design, build, and operations.
- Driving application innovation and AI transformation on Microsoft Azure and GitHub.
- Removing technical blockers and accelerating adoption.
- Engaging with senior executives, architects, engineers, and developers.
- Collaborating internally and externally to deliver pilots and oversee implementations.

### Responsibilities

- Understand customer business and IT priorities for cloud, AI, and low-code solutions.
- Act as the voice of the customer, providing feedback to engineering and accelerating solution delivery through reviews, PoCs, and environment setup.
- Support customer skilling via workshops and readiness activities.
- Drive cloud consumption growth and resolve adoption challenges.
- Build strong customer/partner relationships and identify growth opportunities.
- Stay current with Azure, AI, GitHub, and enterprise development languages (.NET, Python, Java, JavaScript/Node.js).
- Share insights internally and externally through technical communities and events.


### Qualifications

- Bachelors degree in Computer Science, IT, Engineering, Business, or equivalent experience.
- Strong background in cloud/infrastructure technologies, IT consulting, architecture, or software development.
- Experience in customer-facing technical roles and projects.
- Cloud certifications (Azure, AWS, Google) and security certifications.
- Proficiency in enterprise-scale cloud/hybrid architectures and migrations.
- Development experience in .NET, Java, JavaScript/Node.js, or Python.
English required; Arabic is a plus.

## Example 2:
We are looking for a DevOps Engineer to join our dynamic team. The ideal candidate will have experience with CI/CD pipelines, cloud infrastructure, and automation tools. Responsibilities include managing cloud resources, implementing security best practices, and collaborating with development teams to streamline deployment processes. Proficiency in AWS, Docker, Kubernetes, and scripting languages is required.

## Example 3:
How can you help me with managing a large kubernetes environment?

If not, classify it as 'General Prompt'.
Respond only with the classification label."""

RAG_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a helpful assistant that retrieves relevant contributions and expertise based on the provided context.
You will help the user understand why and how Seif can have a huge impact in their job or career.
Use only the information from the context to answer the question.
If the context doesn't contain relevant information, say "I don't have enough information to answer that question, better to reach out to Seif directly"

Context:
{context}"""),
    ("human", "{question}")
])


# =============================================================================
# Agent Nodes
# =============================================================================

def classification_agent(state: AgentState) -> dict:
    """
    Classifies the input as job-related or general.
    Returns 'Job Description' or 'General Prompt'.
    """
    response = llm.invoke([
        SystemMessage(content=CLASSIFICATION_SYSTEM_PROMPT),
        HumanMessage(content=state["input"])
    ])

    content = response.content.strip()
    classification = "Job Description" if "Job Description" in content else "General Prompt"

    return {"classification": classification}


def contributions_agent(state: AgentState) -> dict:
    """
    Uses RAG to retrieve relevant expertise from Azure AI Search.
    Only runs when classification is 'Job Description'.
    """
    # Retrieve relevant documents
    docs = retriever.invoke(state["input"])
    context = "\n\n".join(doc.page_content for doc in docs)

    # Build and execute RAG chain
    chain = RAG_PROMPT | llm | StrOutputParser()
    expertise = chain.invoke({
        "context": context,
        "question": f"Based on the job description: {state['input']}\n\nWhat relevant contributions and expertise can you find?"
    })

    return {"expertise": expertise}


# =============================================================================
# Graph Routing
# =============================================================================

def route_by_classification(state: AgentState) -> Literal["contributions_agent", "__end__"]:
    """Routes to contributions_agent only for job-related prompts."""
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

app = FastAPI(
    title="Seif's AI Assistant API",
    description="An API to ask questions about Seif's expertise and contributions",
    version="1.0.0"
)

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
async def ask_question(request: QuestionRequest):
    """
    Process a question through the LangGraph agent.

    Returns the LLM response if the question is job-related,
    otherwise returns a fun message.
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        result = await graph.ainvoke({
            "input": request.question,
            "classification": "",
            "expertise": ""
        })

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