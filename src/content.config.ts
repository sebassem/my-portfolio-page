import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const portfolio = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "./src/content/portfolio" }),
  schema: z.object({
    name: z.string(),
    category: z.array(z.enum(['AI', 'Architecture', 'Contributions', 'Speaking', 'Content'])),
    cover: z.string(),
    link: z.string().url(),
    order: z.number().optional(),
    featured: z.boolean().optional(),
  }),
});

export const collections = { portfolio };
