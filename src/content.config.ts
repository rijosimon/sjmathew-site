import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

const language = z.enum(['ml', 'en', 'hi', 'sw']);

/** Audio series, video talks and written messages. */
const messages = defineCollection({
	loader: glob({ base: './src/content/messages', pattern: '**/*.md' }),
	schema: ({ image }) =>
		z.object({
			title: z.string(),
			date: z.coerce.date(),
			languages: z.array(language).min(1),
			kind: z.enum(['audio', 'video', 'article']),
			series: z.string().optional(),
			featured: z.boolean().default(false),
			cover: image().optional(),
			/** Audio: one entry per part. `src` is a path or full URL. */
			tracks: z.array(z.object({ title: z.string(), src: z.string() })).optional(),
			/** Video: a YouTube video/playlist, or a self-hosted file. */
			video: z
				.discriminatedUnion('provider', [
					z.object({
						provider: z.literal('youtube'),
						id: z.string().optional(),
						playlist: z.string().optional(),
					}),
					z.object({ provider: z.literal('file'), src: z.string(), poster: z.string().optional() }),
				])
				.optional(),
			downloads: z
				.array(z.object({ label: z.string(), note: z.string().optional(), href: z.string() }))
				.default([]),
			/** Where this came from on the old WordPress site (for the migration only). */
			source: z.object({ wpId: z.number(), wpSlug: z.string() }).optional(),
		}),
});

/** E-books and tracts (PDF). */
const library = defineCollection({
	loader: glob({ base: './src/content/library', pattern: '**/*.md' }),
	schema: z.object({
		title: z.string(),
		date: z.coerce.date(),
		languages: z.array(language).min(1),
		type: z.enum(['book', 'tract']),
		file: z.string(),
		source: z.object({ wpId: z.number(), wpSlug: z.string() }).optional(),
	}),
});

/** Plain pages such as About. */
const pages = defineCollection({
	loader: glob({ base: './src/content/pages', pattern: '**/*.md' }),
	schema: z.object({ title: z.string() }),
});

export const collections = { messages, library, pages };
