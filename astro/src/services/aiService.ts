export interface AskAIResponse {
  answer?: string;
  message?: string;
}

// Callback type for streaming updates
export type StreamCallback = (chunk: string, done: boolean, error?: string) => void;

// Use local API route that proxies to the backend
// This allows the server to reach internal container app URLs
export async function askAI(question: string, onChunk?: StreamCallback): Promise<AskAIResponse> {
  const response = await fetch('/api/ask', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ question }),
  });

  // Check if streaming response (SSE)
  const contentType = response.headers.get('content-type');
  
  if (contentType?.includes('text/event-stream') && onChunk) {
    // Handle streaming response
    const reader = response.body?.getReader();
    const decoder = new TextDecoder();
    let fullResponse = '';
    
    if (!reader) {
      throw new Error('No response body');
    }
    
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split('\n');
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            
            if (data.content) {
              fullResponse += data.content;
              onChunk(data.content, false);
            }
            
            if (data.done) {
              onChunk('', true);
            }
            
            if (data.error === 'rate_limited') {
              return { 
                answer: '🔥 The AI is a bit overloaded right now. Please try again in a moment!' 
              };
            }
            
            if (data.error && data.error !== 'rate_limited') {
              throw new Error(data.error);
            }
          } catch (e) {
            // Skip invalid JSON lines (empty lines, etc.)
            if (line.trim() && line !== 'data: ') {
              console.warn('Failed to parse SSE data:', line);
            }
          }
        }
      }
    }
    
    return { answer: fullResponse };
  }

  // Fallback for JSON responses (errors, etc.)
  return response.json();
}

export function warmupBackend(): void {
  // Send a warm-up request to wake up the container app (fire and forget)
  fetch('/api/warmup').catch(() => {});
}
