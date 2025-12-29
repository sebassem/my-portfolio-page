import os
import asyncio
from azure.identity import AzureCliCredential, get_bearer_token_provider
from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph, START, END
from langchain_community.retrievers import AzureAISearchRetriever
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel
from typing import Literal, TypedDict, Annotated
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
    poem: str

# Initialize Azure OpenAI client
credential = AzureCliCredential()
open_ai_token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
search_token_provider = get_bearer_token_provider(credential, "https://search.azure.com/.default")

client = AzureChatOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    azure_deployment=os.getenv("AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME"),
    azure_ad_token_provider=open_ai_token_provider,
    api_version="2024-08-01-preview",
)

# Initialize the retriever for Azure AI Search
retriever = AzureAISearchRetriever(
    api_key=None,
    azure_ad_token=search_token_provider,
    service_name=os.getenv("AZURE_SEARCH_INSTANCE_NAME"),
    index_name=os.getenv("AZURE_SEARCH_INDEX_NAME"),
    top_k=3,
    content_key="chunk",  # Adjust this to match your index field containing the text content
)

# RAG prompt template
rag_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a helpful assistant that retrieves relevant contributions and expertise based on the provided context.
Use only the information from the context to answer the question.
If the context doesn't contain relevant information, say "I don't have enough information to answer that question, better to reach out to Seif directly"

Context:
{context}"""),
    ("human", "{question}")
])

# Define the classification node
def classification_agent(state: AgentState) -> AgentState:
    from langchain_core.messages import SystemMessage, HumanMessage

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

# Define an agent to get the relevant contributions based on classification
def contributions_agent(state: AgentState) -> AgentState:
    from langchain_core.messages import SystemMessage, HumanMessage

    messages = [
        SystemMessage(content="You are an agent that retrieves relevant contributions and expertise based on the classification and the job description provided."),
        HumanMessage(content=f"The input was: {state['input']}\nClassification: {state['classification']}\n\nGet the relevant contributions and expertise.")
    ]

    response = client.invoke(messages)

    expertise = response.content
    return {"Expertise": expertise}

# Build the graph
def build_graph():
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("classification_agent", classification_agent)
    workflow.add_node("contributions_agent", contributions_agent)

    # Define edges (sequential flow)
    workflow.add_edge(START, "classification_agent")
    workflow.add_edge("classification_agent", "contributions_agent")
    workflow.add_edge("contributions_agent", END)

    return workflow.compile()

async def main():
    graph = build_graph()

    # Run the graph
    result = await graph.ainvoke({
        "input": "how can he help in managing a kubernetes cluster.",
        "classification": "",
        "expertise": ""
    })

    # Print results
    print(f"Classification: {result['classification']}")
    #print(f"expertise:\n{result['expertise']}")
    print("\n=== Final Output ===")
    print(result['expertise'])

asyncio.run(main())