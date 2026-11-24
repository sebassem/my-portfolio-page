export interface BlogPost {
  title: string;
  url: string;
  image: string;
  date: string;
}

const BLOG_FEED_URL = "https://blog.seifbassem.com/posts.json";
const CACHE_TTL_MS = 60 * 60 * 1000; // 1 hour

// Fallback list of featured blog posts from blog.seifbassem.com
export const blogPosts: BlogPost[] = [
  {
    title: "Pub/Sub AI Enrichment with Gemini and Jev",
    url: "https://blog.seifbassem.com/blogs/posts/ai-transformation-pubsub/",
    image: "https://images.seifbassem.com/images/Posts/pubsub-ai-transformation/banner.png",
    date: "2026-09-21"
  },
  {
    title: "Measuring Gemini Enterprise Adoption with BigQuery",
    url: "https://blog.seifbassem.com/blogs/posts/gemini-enterprise-bigquery/",
    image: "https://images.seifbassem.com/images/Posts/gemini-enterprise-bq/banner.png",
    date: "2026-08-02"
  },
  {
    title: "Building a portfolio website with an AI assistant",
    url: "https://blog.seifbassem.com/blogs/posts/ai-portfolio-website/",
    image: "https://images.seifbassem.com/images/Posts/AI-portfolio-website/banner.png",
    date: "2026-01-31"
  },
  {
    title: "Self-Hosting LLMs on Kubernetes: Serving LLMs using vLLM",
    url: "https://blog.seifbassem.com/blogs/posts/hosting-llms-k8s-vllm/",
    image: "https://images.seifbassem.com/images/Posts/Hosting-LLMs-K8s-vLLM/banner.png",
    date: "2025-11-08"
  },
  {
    title: "Self-Hosting LLMs on Kubernetes: Intro",
    url: "https://blog.seifbassem.com/blogs/posts/hosting-llms-k8s-intro/",
    image: "https://images.seifbassem.com/images/Posts/Hosting-LLMs-K8s-Intro/banner.png",
    date: "2025-09-28"
  },
  {
    title: "CI/CD evaluation of Large Language Models using OpenEvals",
    url: "https://blog.seifbassem.com/blogs/posts/llm-evaluation-langchain/",
    image: "https://images.seifbassem.com/images/Posts/llm-evaluation-openeval/banner.png",
    date: "2025-06-29"
  }
];

let cachedPosts: { data: BlogPost[]; fetchedAt: number } | null = null;

/**
 * Dynamically loads the latest blog posts from blog.seifbassem.com/posts.json
 * with a 1-hour in-memory cache and graceful fallback to static blogPosts.
 */
export async function getLatestBlogPosts(limit = 6): Promise<BlogPost[]> {
  const now = Date.now();
  if (cachedPosts && now - cachedPosts.fetchedAt < CACHE_TTL_MS) {
    return cachedPosts.data.slice(0, limit);
  }

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 3000);
    const res = await fetch(BLOG_FEED_URL, {
      signal: controller.signal,
      headers: { Accept: "application/json" }
    });
    clearTimeout(timer);

    if (res.ok) {
      const items = (await res.json()) as Partial<BlogPost>[];
      const valid = items
        .filter(
          (item): item is BlogPost =>
            typeof item?.title === "string" &&
            typeof item?.url === "string" &&
            typeof item?.image === "string" &&
            typeof item?.date === "string"
        );
      if (valid.length > 0) {
        cachedPosts = { data: valid, fetchedAt: now };
        return valid.slice(0, limit);
      }
    }
  } catch {
    // Fall back to static list on network/timeout errors
  }

  return blogPosts.slice(0, limit);
}
