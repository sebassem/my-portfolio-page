import type { APIRoute } from 'astro';

export const POST: APIRoute = async ({ request }) => {
  // Use process.env for runtime environment variables in Node.js
  const AI_API_URL = process.env.AI_API_URL;
  
  if (!AI_API_URL) {
    return new Response(JSON.stringify({ message: 'AI API URL not configured' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  try {
    const body = await request.json();
    
    // Server-side validation (defense-in-depth, matches client maxlength="1200")
    if (!body.question || typeof body.question !== 'string') {
      return new Response(JSON.stringify({ message: 'Question is required' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    if (body.question.length > 1200) {
      return new Response(JSON.stringify({ message: 'Question too long (max 1200 characters)' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    const response = await fetch(`${AI_API_URL}/ask`, {
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
