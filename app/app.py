import os
import asyncio
from azure.identity import AzureCliCredential
from agent_framework.azure import AzureOpenAIResponsesClient
from agent_framework import SequentialBuilder
from pydantic import BaseModel
from typing import Literal
from dotenv import load_dotenv

load_dotenv()

class PromptClassification(BaseModel):
    """Classification of a prompt if its job/career related or a general message."""
    classification: Literal["Job Description", "General Prompt"]

async def main():
    classification_agent = AzureOpenAIResponsesClient(credential=AzureCliCredential()).create_agent(
        instructions="""
        You are a prompt classification agent to help understand if a provided prompt is job or career related, specially in Technology. When provided a prompt, you will figure out if its a job description or related to a specific task in a job or career related.
        If it is, classify it as 'Job Description'. If not, classify it as 'General Prompt'. Respond only with the classification label.""",
        name="classification_agent",
        max_tokens=100,
        response_format=PromptClassification,
        id="classification-agent"
    )

    test_agent = AzureOpenAIResponsesClient(credential=AzureCliCredential()).create_agent(
        instructions="""
        You are an agent that writes a poem based on the provided classification.
        """,
        name="test_agent",
        max_tokens=100,
        id="test-agent"
    )

    workflow = SequentialBuilder().participants([classification_agent, test_agent]).build()

    result = await workflow.run("how can he help in managing a kubernetes cluster.")
    
    # Get all output messages
    outputs = result.get_outputs()
    for messages in outputs:
        for message in messages:
            print(f"Role: {message.role}")
            print(f"Text: {message.text}")
            print("---")
    
    # Output just the last message
    print("\n=== Final Output ===")
    print(outputs[0][-1].text)

asyncio.run(main())

