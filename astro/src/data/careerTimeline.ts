export interface TimelineItem {
  year: string;
  title: string;
  company: string;
  description: string;
  highlights?: string[];
}

export const careerTimeline: TimelineItem[] = [
  {
    year: "2023 - Present",
    title: "Cloud Solution Architect",
    company: "Microsoft",
    description: "Leading cloud architecture and AI transformation initiatives for enterprise customers.",
    highlights: [
      "Azure Arc & Hybrid Cloud",
      "AI/ML Solutions",
      "Infrastructure as Code"
    ]
  },
  {
    year: "2020 - 2023",
    title: "Senior Cloud Engineer",
    company: "Previous Company",
    description: "Designed and implemented cloud-native solutions on Azure.",
    highlights: [
      "Kubernetes & Containers",
      "DevOps & CI/CD",
      "Cloud Migrations"
    ]
  },
  {
    year: "2017 - 2020",
    title: "Systems Engineer",
    company: "Another Company",
    description: "Managed enterprise infrastructure and began cloud journey.",
    highlights: [
      "Windows Server & Active Directory",
      "Virtualization",
      "Automation"
    ]
  }
];
