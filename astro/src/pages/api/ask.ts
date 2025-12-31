import type { APIRoute } from 'astro';

export const POST: APIRoute = async ({ request }) => {
  const AI_API_URL = import.meta.env.AI_API_URL;
  
  if (!AI_API_URL) {
    return new Response(JSON.stringify({ message: 'AI API URL not configured' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  try {
    const body = await request.json();
    
    const response = await fetch(`https://${AI_API_URL}/ask`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    const data = await response.json();
    
    return new Response(JSON.stringify(data), {
      status: response.status,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (error) {
    console.error('Error calling AI API:', error);
    return new Response(JSON.stringify({ message: 'Failed to reach AI service' }), {
      status: 502,
      headers: { 'Content-Type': 'application/json' }
    });
  }
};
