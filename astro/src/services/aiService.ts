export interface AskAIResponse {
  answer?: string;
  message?: string;
}

// Get the AI API base URL from environment variable
// Falls back to relative path for local development
const AI_API_BASE_URL = import.meta.env.PUBLIC_AI_API_URL || '';

export async function askAI(question: string): Promise<AskAIResponse> {
  const response = await fetch(`${AI_API_BASE_URL}/api/ask`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ question }),
  });

  return response.json();
}

export async function onTextboxFocus(): Promise<void> {
  await fetch(`${AI_API_BASE_URL}/api/textbox-focus`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ event: 'focus', timestamp: new Date().toISOString() }),
  });
}
