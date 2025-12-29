"""
LangGraph Agent for Job Classification and Expertise Retrieval

This module implements a two-stage agent workflow:
1. Classification Agent - Determines if input is job/career related
2. Contributions Agent - Uses RAG to retrieve relevant expertise (only for job-related inputs)
"""

import os
import asyncio
from typing import Literal, TypedDict
from azure.identity import AzureCliCredential, get_bearer_token_provider
from dotenv import load_dotenv
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
If it is, classify it as 'Job Description'. If not, classify it as 'General Prompt'.
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
# Main Entry Point
# =============================================================================

async def main():
    graph = build_graph()

    result = await graph.ainvoke({
        "input": "how can he help in managing a large cloud environment.",
        "classification": "",
        "expertise": ""
    })

    # Print results
    print(f"Classification: {result['classification']}")
    if result.get("expertise"):
        print("\n=== Final Output ===")
        print(result["expertise"])


if __name__ == "__main__":
    asyncio.run(main())