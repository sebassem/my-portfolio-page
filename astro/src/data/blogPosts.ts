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
  },
  {
    title: "Simplifying private deployment of Azure AI services using AVM",
    url: "https://seifbassem.com/blogs/posts/azure-ai-services-private-deployment/",
    image: "https://images.seifbassem.com/images/Posts/Azure-AI-Services-Private-Deployment/banner.png",
    date: "2025-05-06"
  },
  {
    title: "Testing the latest Bicep Toys - Fail, Deployer and Graph",
    url: "https://seifbassem.com/blogs/posts/bicep-fail-deployer-graph/",
    image: "https://images.seifbassem.com/images/Posts/bicep-fail-deployer-graph/banner.png",
    date: "2025-03-16"
  }
];
