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
    title: "Cloud Solution Architect - Tech strategy",
    company: "Microsoft",
    description: "Leading cloud architecture, transformation and optimization initiatives for enterprise customers and building top-notch tools and solutions for better cloud adoption.",
    highlights: [
      "Cloud and AI solutions architecture",
      "Global Technical Lead for Azure Arc and hybrid cloud adoption",
      "Core maintainer for Azure Landing Zones (ALZ)",
      "Core maintainer for the ALZ subscription vending Bicep module",
      "Developed multiple Bicep modules for the Azure Verified Modules library",
      "Co-author if the Azure Advisor cost optimization workbook",
      "Author of multiple Cloud Adoption Framework (CAF) guidance",
      "Speaker at multiple events, like Microsoft Ignite and PowerShell Conference Europe."
    ]
  },
  {
    year: "2020 - 2023",
    title: "Sr. Cloud Solution Architect Engineering - Tech Strategy Team",
    company: " Microsoft",
    description: "Leading content and tool development for cloud adoption, governance and hybrid cloud",
    highlights: [
      "Led the authoring of the Cloud adoption framework landing zone accelerator for Azure Arc Data Services",
      "Authored a reference architecture on the Azure Architecture center around Disaster recovery for Azure Arc SQL Managed Instance ",
      "Led the development of field content to support customer engagements around security, governance and management of hybrid and multi-cloud solutions",
      "lead engineer for `ArcBox for DataOps` developing the reference architecture for the Azure Arc-enabled SQL Managed Instance landing zone accelerator",
      "Authored a Microsoft Learn Module on Azure Monitor Workbooks",
      "Lead Core maintainer for the Azure Arc Jumpstart project",
    ]
  },
  {
    year: "2021 - 2022",
    title: "Sr. Customer Engineer, Apps & Infra, Global Technical Team",
    company: "Microsoft",
    description: "Leading content development for the Well-architected and Cloud adoption frameworks",
    highlights: [
      "Reduced the time and cost of the Azure Well-Architected assessments deliveries by ~40% by building the cost optimization workbook",
      "Led the authoring of the Azure Arc-enabled servers Enterprise scale landing zone accelerator focusing on two design areas (Cost governance and Management)",
      "Contributed to authoring the Arc-enabled Kubernetes Enterprise scale landing zone accelerator by leading the Cost governance design area"
    ]
  },
  {
    year: "2018 - 2021",
    title: "Subject Matter Expert - FastTrack center for M365",
    company: "Microsoft",
    description: "Lead for Windows and Microsoft 365 deployment and design engagements for enterprise customers in EMEA",
    highlights: [
      "Engaged with customers across EMEA region to act as a trusted advisor to customers , helping them modernize their management of Windows 10 , Office 365 and Edge using Microsoft Endpoint Manager",
      "Built a Windows virtual desktop sandbox to provide self-service training environments for my team modern workplace",
      "Contribute to provide business and technical insights to our Engineering teams through deep analysis documents"
    ]
  },
  {
    year: "2013 - 2018",
    title: "Domain Infrastructure & Messaging System Team Leader",
    company: "QNB Group",
    description: "Lead for Microsoft solutions",
    highlights: [
      "Led the PCI DSS certification journey by securing and hardening our Windows environment (Desktops and servers)",
      "Developed a cross-platform mobile application to direct customers to the nearest branches or ATMs with ATM systems integration",
      "Deployed an azure test environment for Exchange and CRM",
      "Developed automation runbooks using orchestrator to automate different tasks in the data center",
      "Introduced Configuration manager to the environment to automate patching, application and operating system deployment and hardware inventory"
    ]
  },
  {
    year: "2013 - 2018",
    title: "Senior System Administrator",
    company: "Société Générale",
    description: "System administrator for Microsoft solutions",
    highlights: [
      "Reduced number of help desk requests by developing a bot-like application which empowers the end users to troubleshoot and solve their the most common problems they face day-to-day",
      "Automated the migration of Exchange 2003 to Exchange 2007 using PowerShell and custom developed applications",
      "Developed an internal portal to allow self-service password reset"
    ]
  }
];