// Run with: node --test oauth-helper/
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { auth, callback, handle } from './handler.mjs';

const env = { GITHUB_CLIENT_ID: 'abc123', GITHUB_CLIENT_SECRET: 'shh' };

test('auth redirects to GitHub with the client id, scope and a state cookie', () => {
	const res = auth(new Request('https://example.test/api/auth'), env);
	assert.equal(res.status, 302);
	const location = new URL(res.headers.get('location'));
	assert.equal(location.origin + location.pathname, 'https://github.com/login/oauth/authorize');
	assert.equal(location.searchParams.get('client_id'), 'abc123');
	assert.equal(location.searchParams.get('scope'), 'public_repo');
	const state = location.searchParams.get('state');
	assert.match(res.headers.get('set-cookie'), new RegExp(`oauth_state=${state}`));
});

test('callback exchanges the code and hands the token to the editor', async () => {
	let sent;
	const fake = async (url, init) => {
		sent = { url, body: JSON.parse(init.body) };
		return new Response(JSON.stringify({ access_token: 'gho_token' }));
	};
	const req = new Request('https://example.test/api/callback?code=CODE&state=S1', { headers: { cookie: 'oauth_state=S1' } });
	const res = await callback(req, env, fake);
	const text = await res.text();
	assert.equal(sent.url, 'https://github.com/login/oauth/access_token');
	assert.deepEqual(sent.body, { client_id: 'abc123', client_secret: 'shh', code: 'CODE' });
	assert.match(text, /authorization:github:success:/);
	assert.match(text, /gho_token/);
	assert.match(res.headers.get('set-cookie'), /Max-Age=0/);
});

test('callback refuses a mismatched state and never calls GitHub', async () => {
	const fake = async () => assert.fail('must not call GitHub');
	const req = new Request('https://example.test/api/callback?code=CODE&state=EVIL', { headers: { cookie: 'oauth_state=S1' } });
	const text = await (await callback(req, env, fake)).text();
	assert.match(text, /authorization:github:error:/);
	assert.doesNotMatch(text, /success/);
});

test('callback reports GitHub errors instead of a token', async () => {
	const fake = async () => new Response(JSON.stringify({ error: 'bad_verification_code', error_description: 'The code has expired' }));
	const req = new Request('https://example.test/api/callback?code=OLD&state=S1', { headers: { cookie: 'oauth_state=S1' } });
	const text = await (await callback(req, env, fake)).text();
	assert.match(text, /authorization:github:error:/);
	assert.match(text, /The code has expired/);
});

test('handle routes by path', async () => {
	assert.equal((await handle(new Request('https://x.test/api/auth'), env)).status, 302);
	assert.equal((await handle(new Request('https://x.test/other'), env)).status, 404);
});
