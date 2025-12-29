import os
import asyncio
from azure.identity import AzureCliCredential, get_bearer_token_provider
from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph, START, END
from langchain_community.retrievers import AzureAISearchRetriever
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel
from typing import Literal, TypedDict
from dotenv import load_dotenv

load_dotenv()

# Define the classification schema
class PromptClassification(BaseModel):
    """Classification of a prompt if its job/career related or a general message."""
    classification: Literal["Job Description", "General Prompt"]

# Define the state schema for the graph
class AgentState(TypedDict):
    input: str
    classification: str
    expertise: str

# Initialize Azure OpenAI client
credential = AzureCliCredential()
open_ai_token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
search_token_provider = get_bearer_token_provider(credential, "https://search.azure.com/.default")
azure_search_token = search_token_provider()

client = AzureChatOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    azure_deployment=os.getenv("AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME"),
    azure_ad_token_provider=open_ai_token_provider,
    api_version="2024-08-01-preview",
)

retriever = AzureAISearchRetriever(
    api_key=None,
    azure_ad_token=azure_search_token,
    service_name=os.getenv("AZURE_SEARCH_INSTANCE_NAME"),
    index_name=os.getenv("AZURE_SEARCH_INDEX_NAME"),
    top_k=3,
    content_key="chunk",  # Adjust this to match your index field containing the text content
)

# RAG prompt template
rag_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a helpful assistant that retrieves relevant contributions and expertise based on the provided context. You will help the user understands why and how based on the provided context Seif can have huge impact in their job or career.
Use only the information from the context to answer the question.
If the context doesn't contain relevant information, say "I don't have enough information to answer that question, better to reach out to Seif directly"

Context:
{context}"""),
    ("human", "{question}")
])

# Define the classification node
def classification_agent(state: AgentState) -> AgentState:
    messages = [
        SystemMessage(content="""You are a prompt classification agent to help understand if a provided prompt is job or career related, specially in Technology. When provided a prompt, you will figure out if its a job description or related to a specific task in a job or career related.
If it is, classify it as 'Job Description'. If not, classify it as 'General Prompt'. Respond only with the classification label."""),
        HumanMessage(content=state["input"])
    ]

    response = client.invoke(messages)

    # Parse the classification from the response content
    content = response.content.strip()
    if "Job Description" in content:
        classification = "Job Description"
    else:
        classification = "General Prompt"

    return {"classification": classification}

# Helper function to format retrieved documents
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

# Define an agent to get the relevant contributions based on classification using RAG
def contributions_agent(state: AgentState) -> AgentState:
    # Retrieve relevant documents from Azure AI Search
    docs = retriever.invoke(state["input"])
    context = format_docs(docs)

    # Format the RAG prompt with context and question
    messages = rag_prompt.format_messages(
        context=context,
        question=f"Based on the job description: {state['input']}\n\nWhat relevant contributions and expertise can you find?"
    )

    response = client.invoke(messages)
    expertise = StrOutputParser().invoke(response)

    return {"expertise": expertise}

# Routing function to decide next step based on classification
def route_by_classification(state: AgentState) -> str:
    if state["classification"] == "Job Description":
        return "contributions_agent"
    else:
        return "end"

# Build the graph
def build_graph():
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("classification_agent", classification_agent)
    workflow.add_node("contributions_agent", contributions_agent)

    # Define edges with conditional routing
    workflow.add_edge(START, "classification_agent")
    workflow.add_conditional_edges(
        "classification_agent",
        route_by_classification,
        {
            "contributions_agent": "contributions_agent",
            "end": END
        }
    )
    workflow.add_edge("contributions_agent", END)

    return workflow.compile()

async def main():
    graph = build_graph()

    # Run the graph
    result = await graph.ainvoke({
        "input": "how can he help in managing a large cloud environment.",
        "classification": "",
        "expertise": ""
    })

    # Print results
    print(f"Classification: {result['classification']}")
    print("\n=== Final Output ===")
    print(result['expertise'])

asyncio.run(main())