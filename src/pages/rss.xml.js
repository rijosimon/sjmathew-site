import rss from '@astrojs/rss';
import { getCollection } from 'astro:content';
import { KINDS, makeExcerpt } from '../lib/site';

export async function GET(context) {
	const messages = (await getCollection('messages')).sort((a, b) => b.data.date.valueOf() - a.data.date.valueOf());
	return rss({
		title: 'Saju John Mathew: messages',
		description: 'Biblical messages and readings from the ministry of Saju John Mathew, to draw you closer to Jesus.',
		site: context.site,
		items: messages.map((message) => ({
			title: message.data.title,
			pubDate: message.data.date,
			description: makeExcerpt(message.body ?? '', 240) || KINDS[message.data.kind].label,
			link: `/messages/${message.id}/`,
			categories: [KINDS[message.data.kind].label, ...message.data.languages],
		})),
	});
}
