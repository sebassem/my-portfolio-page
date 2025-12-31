import type { APIRoute } from 'astro';

export const GET: APIRoute = async () => {
  const AI_API_URL = process.env.AI_API_URL;
  
  if (!AI_API_URL) {
    return new Response(JSON.stringify({ status: 'error', message: 'AI API URL not configured' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  try {
    // Call the backend root endpoint to warm it up
    const response = await fetch(`${AI_API_URL}/`);
    const data = await response.json();
    
    return new Response(JSON.stringify(data), {
      status: response.status,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (error) {
    return new Response(JSON.stringify({ status: 'error', message: 'Warmup failed' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
};
