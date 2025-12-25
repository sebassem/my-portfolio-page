// AI API Configuration
// Replace with your actual API key
export const OPENAI_API_KEY = "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";

// OpenAI API settings
export const AI_CONFIG = {
  apiUrl: "https://api.openai.com/v1/chat/completions",
  model: "gpt-4.1-mini",
  maxTokens: 500,
  temperature: 0.7,
};

// System prompt template for portfolio questions
export const getSystemPrompt = (projectName: string, projectDesc: string, projectCategory: string) => {
  return `You are a helpful assistant that answers questions about portfolio projects. 
The current project is: "${projectName}"
Description: ${projectDesc}
Category: ${projectCategory}

Answer questions about this project helpfully and concisely.`;
};

export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface ProjectContext {
  name: string;
  desc: string;
  category: string;
}

// Helper function to call OpenAI API
export async function callOpenAI(messages: ChatMessage[]): Promise<string> {
  const response = await fetch(AI_CONFIG.apiUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${OPENAI_API_KEY}`
    },
    body: JSON.stringify({
      model: AI_CONFIG.model,
      messages,
      max_tokens: AI_CONFIG.maxTokens,
      temperature: AI_CONFIG.temperature
    })
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error?.message || "Failed to get response from OpenAI");
  }

  const data = await response.json();
  return data.choices[0].message.content;
}
