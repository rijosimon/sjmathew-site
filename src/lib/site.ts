import type { CollectionEntry } from 'astro:content';

/** Shown as a banner and used to add noindex while this is only a design preview. */
export const PREVIEW = true;

export const SITE = {
	name: 'Saju John Mathew',
	tagline: 'Recorded messages and e-books, free to listen to, read and share.',
	url: 'https://www.sjmathew.com',
} as const;

export type LanguageCode = 'ml' | 'en' | 'hi' | 'sw';

/** `native` is what the language calls itself; it is set in its own script. */
export const LANGUAGES: Record<LanguageCode, { name: string; native: string; lang: string }> = {
	ml: { name: 'Malayalam', native: 'മലയാളം', lang: 'ml' },
	en: { name: 'English', native: 'English', lang: 'en' },
	hi: { name: 'Hindi', native: 'हिन्दी', lang: 'hi' },
	sw: { name: 'Swahili', native: 'Kiswahili', lang: 'sw' },
};
export const LANGUAGE_ORDER: LanguageCode[] = ['ml', 'en', 'hi', 'sw'];

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
	return fallback;
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
