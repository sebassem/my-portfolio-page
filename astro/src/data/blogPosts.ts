export interface BlogPost {
  title: string;
  url: string;
  image: string;
  date: string;
}

// Latest blog posts from seifbassem.com
// This file can be populated dynamically via a build script or API
export const blogPosts: BlogPost[] = [
  {
    title: "Pub/Sub AI Enrichment with Gemini",
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
    title: "Self-Hosting LLMs on Kubernetes: Serving LLMs using vLLM",
    url: "https://seifbassem.com/blogs/posts/hosting-llms-k8s-vllm/",
    image: "https://images.seifbassem.com/images/Posts/Hosting-LLMs-K8s-vLLM/banner.png",
    date: "2025-11-08"
  },
  {
    title: "Self-Hosting LLMs on Kubernetes: Intro",
    url: "https://seifbassem.com/blogs/posts/hosting-llms-k8s-intro/",
    image: "https://images.seifbassem.com/images/Posts/Hosting-LLMs-K8s-Intro/banner.png",
    date: "2025-09-28"
  },
  {
    title: "Level Up your workflows with GitHub Copilot's custom chat modes",
    url: "https://www.seifbassem.com/blogs/posts/github-copilot-custom-chat-modes/",
    image: "https://images.seifbassem.com/images/Posts/Github-Copilot-Custom-Chat-Modes/banner.png",
    date: "2025-08-09"
  },
  {
    title: "CI/CD evaluation of Large Language Models using OpenEvals",
    url: "https://seifbassem.com/blogs/posts/llm-evaluation-langchain/",
    image: "https://images.seifbassem.com/images/Posts/llm-evaluation-openeval/banner.png",
    date: "2025-06-29"
  }
];
