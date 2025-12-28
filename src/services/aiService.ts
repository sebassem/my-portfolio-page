export interface AskAIResponse {
  answer?: string;
  message?: string;
}

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
