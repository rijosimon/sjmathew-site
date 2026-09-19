// @ts-check
import { defineConfig, fontProviders } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import os from 'node:os';
import path from 'node:path';
import sirv from 'sirv';

// One serif (reading) and one sans (interface) family per script. Fontsource
// subsets are split by unicode range, so a visitor only downloads the scripts
// actually present on the page they open.
const fontsource = fontProviders.fontsource();

/** @typedef {[400 | 600 | 700, ...(400 | 600 | 700)[]]} Weights */

/**
 * @param {string} name
 * @param {string} cssVariable
 * @param {string} subset
 * @param {'serif' | 'sans-serif'} generic
 * @param {Weights} weights
 * @param {boolean} [italic]
 */
const noto = (name, cssVariable, subset, generic, weights, italic = false) => ({
	provider: fontsource,
	name,
	cssVariable,
	weights,
	styles: /** @type {['normal'] | ['normal', 'italic']} */ (italic ? ['normal', 'italic'] : ['normal']),
	subsets: /** @type {[string]} */ ([subset]),
	fallbacks: [generic],
});

// Development only: serve the locally processed media library at /media with byte-range
// support (needed for seeking in audio and video). Uses LOCAL_MEDIA_DIR if set, otherwise
// ~/Workspace/sjmathew-media/out. Requests for files that are not there fall through as 404s.
const devMedia = () => ({
	name: 'dev-media',
	configureServer(/** @type {import('vite').ViteDevServer} */ server) {
		const dir = process.env.LOCAL_MEDIA_DIR ?? path.join(os.homedir(), 'Workspace', 'sjmathew-media', 'out');
		server.middlewares.use('/media', sirv(dir, { dev: true, etag: true }));
	},
});

// https://astro.build/config
export default defineConfig({
	site: 'https://www.sjmathew.com',
	trailingSlash: 'always',
	integrations: [sitemap()],
	vite: { plugins: [devMedia()] },
	fonts: [
		noto('Noto Serif', '--font-serif-latin', 'latin', 'serif', [400, 700], true),
		noto('Noto Serif Malayalam', '--font-serif-ml', 'malayalam', 'serif', [400, 700]),
		noto('Noto Serif Devanagari', '--font-serif-hi', 'devanagari', 'serif', [400, 700]),
		noto('Noto Sans', '--font-sans-latin', 'latin', 'sans-serif', [400, 600, 700]),
		noto('Noto Sans Malayalam', '--font-sans-ml', 'malayalam', 'sans-serif', [400, 600, 700]),
		noto('Noto Sans Devanagari', '--font-sans-hi', 'devanagari', 'sans-serif', [400, 600, 700]),
		noto('Noto Serif Tamil', '--font-serif-ta', 'tamil', 'serif', [400, 700]),
		noto('Noto Sans Tamil', '--font-sans-ta', 'tamil', 'sans-serif', [400, 600, 700]),
	],
});
