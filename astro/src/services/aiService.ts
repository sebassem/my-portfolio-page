export interface AskAIResponse {
  answer?: string;
  message?: string;
}

// Use local API route that proxies to the backend
// This allows the server to reach internal container app URLs
export async function askAI(question: string): Promise<AskAIResponse> {
  const response = await fetch('/api/ask', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ question }),
  });

  return response.json();
}

export async function onTextboxFocus(): Promise<void> {
  // No-op or implement if needed
}
