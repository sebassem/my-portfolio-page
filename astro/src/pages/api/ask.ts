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
    
    // Forward request to backend API with streaming
    const response = await fetch(`${AI_API_URL}/ask`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        // Forward client IP for rate limiting
        'X-Forwarded-For': request.headers.get('x-forwarded-for') || '',
      },
      body: JSON.stringify(body),
    });

    // Check if response is streaming (SSE)
    const contentType = response.headers.get('content-type');
    
    if (contentType?.includes('text/event-stream')) {
      // Pass through the SSE stream directly
      return new Response(response.body, {
        status: response.status,
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
          'X-Accel-Buffering': 'no',  // Disable nginx buffering
        }
      });
    }
    
    // Fallback for non-streaming responses (errors, etc.)
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
