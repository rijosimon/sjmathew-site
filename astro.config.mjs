// @ts-check
import { defineConfig, fontProviders } from 'astro/config';
import sitemap from '@astrojs/sitemap';

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

// https://astro.build/config
export default defineConfig({
	site: 'https://www.sjmathew.com',
	trailingSlash: 'always',
	integrations: [sitemap()],
	fonts: [
		noto('Noto Serif', '--font-serif-latin', 'latin', 'serif', [400, 700], true),
		noto('Noto Serif Malayalam', '--font-serif-ml', 'malayalam', 'serif', [400, 700]),
		noto('Noto Serif Devanagari', '--font-serif-hi', 'devanagari', 'serif', [400, 700]),
		noto('Noto Sans', '--font-sans-latin', 'latin', 'sans-serif', [400, 600, 700]),
		noto('Noto Sans Malayalam', '--font-sans-ml', 'malayalam', 'sans-serif', [400, 600, 700]),
		noto('Noto Sans Devanagari', '--font-sans-hi', 'devanagari', 'sans-serif', [400, 600, 700]),
	],
});
