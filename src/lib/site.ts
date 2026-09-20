import type { CollectionEntry } from 'astro:content';

/** When true, a banner is shown and search engines are told not to list the site. Off now that the site is live. */
export const PREVIEW = false;

const NAME = 'Saju John Mathew';

export const SITE = {
	name: NAME,
	/** The home page headline. */
	tagline: 'Biblical Messages to draw you closer to Jesus.',
	/** The line under the headline. */
	intro: `From the ministry of ${NAME}: listen, watch and read, in Malayalam, English, Hindi, Kiswahili and more. Everything is free.`,
	/** For search results and link previews. */
	description: `Biblical messages from the ministry of ${NAME} to draw you closer to Jesus, in Malayalam, English, Hindi and more. Everything is free.`,
	url: 'https://www.sjmathew.com',
} as const;

export type LanguageCode = 'ml' | 'en' | 'hi' | 'sw' | 'pt' | 'ta' | 'si';

/** `native` is what the language calls itself; it is set in its own script. */
export const LANGUAGES: Record<LanguageCode, { name: string; native: string; lang: string }> = {
	ml: { name: 'Malayalam', native: 'മലയാളം', lang: 'ml' },
	en: { name: 'English', native: 'English', lang: 'en' },
	hi: { name: 'Hindi', native: 'हिन्दी', lang: 'hi' },
	sw: { name: 'Swahili', native: 'Kiswahili', lang: 'sw' },
	pt: { name: 'Portuguese', native: 'Português', lang: 'pt' },
	ta: { name: 'Tamil', native: 'தமிழ்', lang: 'ta' },
	si: { name: 'Sinhala', native: 'සිංහල', lang: 'si' },
};
export const LANGUAGE_ORDER: LanguageCode[] = ['ml', 'en', 'hi', 'sw', 'ta', 'pt', 'si'];

export const KINDS = {
	audio: { label: 'Audio', verb: 'Listen' },
	video: { label: 'Video', verb: 'Watch' },
	article: { label: 'Reading', verb: 'Read' },
} as const;
export type Kind = keyof typeof KINDS;

/** Pick the BCP-47 language for a string from the script it is written in. */
export function scriptLang(text: string, fallback = 'en'): string {
	if (/[ഀ-ൿ]/.test(text)) return 'ml';
	if (/[ऀ-ॿ]/.test(text)) return 'hi';
	if (/[\u0B80-\u0BFF]/.test(text)) return 'ta';
	if (/[\u0D80-\u0DFF]/.test(text)) return 'si';
	return fallback;
}

/**
 * Where the media library is served from. Set PUBLIC_MEDIA_BASE_URL at build time (for example
 * the Spaces CDN address). In development `npm run dev:media` serves the local library at /media.
 */
const MEDIA_BASE = (import.meta.env.PUBLIC_MEDIA_BASE_URL ?? '/media').replace(/\/+$/, '');

/** Turn a media key (`audio/ykt/class-08.mp3`) into a URL. Full URLs and root paths pass through. */
export function mediaUrl(ref: string): string {
	if (/^(https?:)?\/\//.test(ref) || ref.startsWith('/')) return ref;
	return `${MEDIA_BASE}/${ref.split('/').map(encodeURIComponent).join('/')}`;
}

export function formatDate(date: Date): string {
	return new Intl.DateTimeFormat('en', {
		year: 'numeric',
		month: 'short',
		day: 'numeric',
		timeZone: 'UTC',
	}).format(date);
}

export function slugify(text: string): string {
	return text
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/^-+|-+$/g, '');
}

export type Message = CollectionEntry<'messages'>;
export type LibraryItem = CollectionEntry<'library'>;

export const byNewest = (a: { data: { date: Date } }, b: { data: { date: Date } }) =>
	b.data.date.valueOf() - a.data.date.valueOf();

/** "10 parts", "Video", "Reading" ... the short descriptor under a card title. */
export function describe(m: Message): string {
	if (m.data.kind === 'audio') {
		const n = m.data.tracks?.length ?? 0;
		return n > 1 ? `${n} parts` : 'Audio';
	}
	return KINDS[m.data.kind].label;
}

/** First readable paragraph of a Markdown body, as plain text, for cards and previews. */
export function makeExcerpt(markdown: string, max = 170): string {
	const paragraphs = markdown.split(/\n{2,}/).map((p) => p.trim());
	for (const raw of paragraphs) {
		if (!raw || raw.startsWith('>') || /^reading passage/i.test(raw)) continue;
		const text = raw
			.replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
			.replace(/[*_`#]/g, '')
			.replace(/\s+/g, ' ')
			.trim();
		if (text.length < 60) continue;
		if (text.length <= max) return text;
		return text.slice(0, max).replace(/\s+\S*$/, '') + '…';
	}
	return '';
}
