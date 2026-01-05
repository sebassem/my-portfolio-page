"""
Server-Sent Events (SSE) Streaming Utilities
============================================
Helper functions for formatting and streaming SSE responses.
"""

import json
import random
from typing import AsyncGenerator, Dict, List

# Fun messages for non-job-related (off-topic) queries
FUN_MESSAGES: List[str] = [
    "🤖 Beep boop! That's not quite what I'm trained for. Try asking about Seif's professional expertise instead!",
    "🎮 Nice try! But I'm here to talk about jobs and careers, not to play games. Ask me about Seif's skills!",
    "🌟 Interesting question! But let's keep it professional. What would you like to know about Seif's experience?",
    "🚀 I'm an expert on Seif's career, not a general chatbot. Fire away with a job-related question!",
    "💼 My specialty is matching Seif's skills to your needs. Got a job description or career question?",
    "🎯 Off-topic alert! I'm laser-focused on helping you understand how Seif can contribute to your team.",
    "☕ That's a fun question, but I'm caffeinated only for career conversations. What role are you hiring for?",
    "🔮 My crystal ball only shows career paths! Ask me about Seif's professional background instead.",
]


def sse_message(
    content: str = None,
    done: bool = False,
    is_job_related: bool = True,
    error: str = None
) -> str:
    """
    Format a Server-Sent Event message.
    
    Args:
        content: Text content to stream
        done: Whether this is the final message
        is_job_related: Whether the response was job-related (for analytics)
        error: Error type if an error occurred
        
    Returns:
        SSE-formatted string (data: {...}\n\n)
    """
    data = {}
    if content is not None:
        data["content"] = content
    if done:
        data["done"] = True
        data["is_job_related"] = is_job_related
    if error:
        data["error"] = error
    return f"data: {json.dumps(data)}\n\n"


async def create_fun_message_stream(is_job_related: bool = False) -> AsyncGenerator[str, None]:
    """
    Create an SSE stream that returns a random fun message.
    
    Used for off-topic questions and suspicious input.
    
    Args:
        is_job_related: Flag indicating if response is job-related
        
    Yields:
        SSE-formatted messages
    """
    message = random.choice(FUN_MESSAGES)
    yield sse_message(content=message)
    yield sse_message(done=True, is_job_related=is_job_related)


def get_sse_headers() -> Dict[str, str]:
    """
    Get standard headers for SSE streaming responses.
    
    Returns:
        Dictionary of HTTP headers optimized for SSE
    """
    return {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # Disable nginx/proxy buffering
    }
