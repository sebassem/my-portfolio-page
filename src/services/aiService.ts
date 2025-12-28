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

export async function onTextboxFocus(): Promise<void> {
  await fetch('/api/textbox-focus', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ event: 'focus', timestamp: new Date().toISOString() }),
  });
}
