import os
import asyncio
from azure.identity import AzureCliCredential, get_bearer_token_provider
from openai import AzureOpenAI
from langgraph.graph import StateGraph, START, END
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
token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")

client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    azure_ad_token_provider=token_provider,
    api_version="2024-10-21"
)

# Define the classification node
def classification_agent(state: AgentState) -> AgentState:
    response = client.beta.chat.completions.parse(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        messages=[
            {
                "role": "system",
                "content": """You are a prompt classification agent to help understand if a provided prompt is job or career related, specially in Technology. When provided a prompt, you will figure out if its a job description or related to a specific task in a job or career related.
                If it is, classify it as 'Job Description'. If not, classify it as 'General Prompt'. Respond only with the classification label."""
            },
            {
                "role": "user",
                "content": state["input"]
            }
        ],
        max_tokens=100,
        response_format=PromptClassification
    )

    classification = response.choices[0].message.parsed.classification
    return {"classification": classification}

# Define the poem writing node
def poem_agent(state: AgentState) -> AgentState:
    response = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        messages=[
            {
                "role": "system",
                "content": "You are an agent that writes a poem based on the provided classification."
            },
            {
                "role": "user",
                "content": f"The input was: {state['input']}\nClassification: {state['classification']}\n\nWrite a short poem based on this."
            }
        ],
        max_tokens=100
    )

    poem = response.choices[0].message.content
    return {"poem": poem}

# Build the graph
def build_graph():
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("classification_agent", classification_agent)
    workflow.add_node("poem_agent", poem_agent)

    # Define edges (sequential flow)
    workflow.add_edge(START, "classification_agent")
    workflow.add_edge("classification_agent", "poem_agent")
    workflow.add_edge("poem_agent", END)

    return workflow.compile()

async def main():
    graph = build_graph()

    # Run the graph
    result = await graph.ainvoke({
        "input": "how can he help in managing a kubernetes cluster.",
        "classification": "",
        "poem": ""
    })

    # Print results
    print(f"Classification: {result['classification']}")
    print("---")
    print(f"Poem:\n{result['poem']}")
    print("\n=== Final Output ===")
    print(result['poem'])

asyncio.run(main())