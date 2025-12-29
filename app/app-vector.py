import os
from langchain_community.retrievers import AzureAISearchRetriever
from azure.identity import AzureCliCredential, get_bearer_token_provider
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv

load_dotenv()

# Initialize Azure credentials
credential = AzureCliCredential()

# Token provider for Azure OpenAI (Cognitive Services scope)
openai_token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")

# Token for Azure AI Search (requires Search Index Data Reader role)
search_token_provider = get_bearer_token_provider(credential, "https://search.azure.com/.default")
azure_search_token = search_token_provider()

# Initialize the retriever for Azure AI Search
retriever = AzureAISearchRetriever(
    api_key=None,
    azure_ad_token=azure_search_token,
    service_name=os.getenv("AZURE_SEARCH_INSTANCE_NAME"),
    index_name=os.getenv("AZURE_SEARCH_INDEX_NAME"),
    top_k=3,
    content_key="chunk",  # Adjust this to match your index field containing the text content
)

# Initialize Azure OpenAI Chat client
llm = AzureChatOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    azure_deployment=os.getenv("AZURE_DEPLOYMENT_NAME"),
    azure_ad_token_provider=openai_token_provider,
    api_version="2024-08-01-preview",
)

# RAG prompt template
rag_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a helpful assistant that answers questions based on the provided context. 
Use only the information from the context to answer the question. 
If the context doesn't contain relevant information, say "I don't have enough information to answer that question."

Context:
{context}"""),
    ("human", "{question}")
])

# Helper function to format retrieved documents
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

# Build the RAG chain
rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | rag_prompt
    | llm
    | StrOutputParser()
)

# Main function to run RAG queries
def ask(question: str) -> str:
    """Ask a question and get an answer using RAG."""
    return rag_chain.invoke(question)

if __name__ == "__main__":
    # Example usage
    question = "What information do you have in the documents related to Kubernetes?"
    print(f"Question: {question}")
    print("-" * 50)
    answer = ask(question)
    print(f"Answer: {answer}")
