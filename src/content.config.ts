import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

const language = z.enum(['ml', 'en', 'hi', 'sw', 'pt', 'ta', 'si']);

/** A YouTube video/playlist, or a file in the media library (`src` is a media key). */
const video = z.discriminatedUnion('provider', [
	z.object({
		provider: z.literal('youtube'),
		id: z.string().optional(),
		playlist: z.string().optional(),
	}),
	z.object({ provider: z.literal('file'), src: z.string(), poster: z.string().optional() }),
]);

/**
 * File references (`src`, `href`, `cover`, `file`) are media keys such as
 * `audio/ykt/class-08.mp3`. They resolve against PUBLIC_MEDIA_BASE_URL (see `mediaUrl`).
 * A value starting with `/` or `http` is used as is.
 */

/** Audio series, video talks and written messages. */
const messages = defineCollection({
	loader: glob({ base: './src/content/messages', pattern: '**/*.md' }),
	schema: z.object({
		title: z.string(),
		date: z.coerce.date(),
		languages: z.array(language).min(1),
		kind: z.enum(['audio', 'video', 'article']),
		series: z.string().optional(),
		featured: z.boolean().default(false),
		cover: z.string().optional(),
		/** Audio: one entry per part. */
		tracks: z.array(z.object({ title: z.string(), src: z.string() })).optional(),
		video: video.optional(),
		/** Further videos on the same page (a few messages have several). */
		moreVideos: z.array(video).optional(),
		downloads: z
			.array(z.object({ label: z.string(), note: z.string().optional(), href: z.string() }))
			.default([]),
		/** Where this came from on the old WordPress site (for the migration only). */
		source: z.object({ wpId: z.number(), wpSlug: z.string(), wpType: z.string().optional() }).optional(),
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
		source: z.object({ wpId: z.number(), wpSlug: z.string(), wpType: z.string().optional() }).optional(),
	}),
});

/** Plain pages such as About and FAQ. */
const pages = defineCollection({
	loader: glob({ base: './src/content/pages', pattern: '**/*.md' }),
	schema: z.object({ title: z.string() }),
});

export const collections = { messages, library, pages };
