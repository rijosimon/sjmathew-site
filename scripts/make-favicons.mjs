// Builds the site icons from the portrait: a square crop on the face, in the sizes browsers and phones ask for.
// Run: node scripts/make-favicons.mjs   (needs the `sharp` package that Astro already installs)
import fs from 'node:fs';
import path from 'node:path';
import sharp from 'sharp';

const root = path.resolve(import.meta.dirname, '..');
const source = path.join(root, 'src/assets/portrait.jpg');
const out = path.join(root, 'public');

// Square crop of the 774x1024 portrait: head and a little of the shoulders.
const crop = { left: 105, top: 135, width: 570, height: 570 };
const square = () => sharp(source).extract(crop);

const sizes = { 'favicon-32.png': 32, 'favicon-48.png': 48, 'apple-touch-icon.png': 180, 'icon-192.png': 192 };
for (const [name, size] of Object.entries(sizes)) {
	await square().resize(size, size, { kernel: 'lanczos3' }).png({ compressionLevel: 9 }).toFile(path.join(out, name));
}

// favicon.ico: an ICO container holding 32 px and 48 px PNGs (valid since Windows Vista, read by every browser).
const pngs = [32, 48].map((s) => fs.readFileSync(path.join(out, `favicon-${s}.png`)));
const header = Buffer.alloc(6);
header.writeUInt16LE(0, 0); header.writeUInt16LE(1, 2); header.writeUInt16LE(pngs.length, 4);
let offset = 6 + 16 * pngs.length;
const entries = pngs.map((png, i) => {
	const size = [32, 48][i];
	const e = Buffer.alloc(16);
	e.writeUInt8(size, 0); e.writeUInt8(size, 1); e.writeUInt8(0, 2); e.writeUInt8(0, 3);
	e.writeUInt16LE(1, 4); e.writeUInt16LE(32, 6); e.writeUInt32LE(png.length, 8); e.writeUInt32LE(offset, 12);
	offset += png.length;
	return e;
});
fs.writeFileSync(path.join(out, 'favicon.ico'), Buffer.concat([header, ...entries, ...pngs]));
fs.rmSync(path.join(out, 'favicon-48.png'));

fs.writeFileSync(path.join(out, 'site.webmanifest'), JSON.stringify({
	name: 'Saju John Mathew',
	short_name: 'Saju',
	icons: [{ src: '/icon-192.png', sizes: '192x192', type: 'image/png' }],
	theme_color: '#0e5a63',
	background_color: '#fbf8f3',
	display: 'browser',
}, null, 2) + '\n');
console.log('icons written to public/');
