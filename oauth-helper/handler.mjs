// Login helper for the Decap CMS editor.
//
// Decap runs in the browser and needs a GitHub access token. GitHub will only hand one out after a
// server has swapped a one-time code for it using a secret, so this is the small server piece.
// It has two routes and no state:
//   GET /auth      sends the editor to GitHub's sign-in page
//   GET /callback  GitHub sends the visitor back here; the code is exchanged for a token, and the
//                  token is passed to the editor window (the format Decap expects)
//
// Runtime-neutral: each function takes a standard `Request` and returns a standard `Response`, so
// it works as a DigitalOcean/Cloudflare/Deno/Node 18+ function. Configure with environment variables
//   GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, and optionally
//   OAUTH_SCOPE (default "public_repo": enough for a public repository)

const GITHUB = 'https://github.com/login/oauth';

const html = (body, headers = {}) =>
	new Response(body, { status: 200, headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store', ...headers } });

function cookie(request, name) {
	const match = (request.headers.get('cookie') ?? '').match(new RegExp(`(?:^|; )${name}=([^;]+)`));
	return match ? match[1] : null;
}

/** Tell the opener window how the sign-in went, then close. Message format is fixed by Decap. */
function finish(status, content) {
	const message = `authorization:github:${status}:${JSON.stringify(content)}`;
	return html(`<!doctype html><meta charset="utf-8"><title>Signing in</title><script>
(() => {
	const message = ${JSON.stringify(message)};
	window.addEventListener('message', (event) => {
		window.opener.postMessage(message, event.origin);
		window.close();
	});
	window.opener.postMessage('authorizing:github', '*');
})();
</script><p>Signing in…</p>`, { 'set-cookie': 'oauth_state=; Path=/; Max-Age=0; Secure; HttpOnly; SameSite=Lax' });
}

export function auth(request, env) {
	if (!env.GITHUB_CLIENT_ID) return new Response('GITHUB_CLIENT_ID is not set', { status: 500 });
	const state = crypto.randomUUID();
	const url = new URL(`${GITHUB}/authorize`);
	url.searchParams.set('client_id', env.GITHUB_CLIENT_ID);
	url.searchParams.set('scope', env.OAUTH_SCOPE ?? 'public_repo');
	url.searchParams.set('state', state);
	return new Response(null, {
		status: 302,
		headers: {
			location: url.toString(),
			// Remember the state so the callback can check that the visitor is the one who started.
			'set-cookie': `oauth_state=${state}; Path=/; Max-Age=600; Secure; HttpOnly; SameSite=Lax`,
		},
	});
}

export async function callback(request, env, fetchImpl = fetch) {
	const params = new URL(request.url).searchParams;
	const code = params.get('code');
	if (params.get('error')) return finish('error', { message: params.get('error_description') ?? params.get('error') });
	if (!code || !params.get('state') || params.get('state') !== cookie(request, 'oauth_state')) {
		return finish('error', { message: 'The sign-in could not be verified. Please try again.' });
	}
	const response = await fetchImpl(`${GITHUB}/access_token`, {
		method: 'POST',
		headers: { 'content-type': 'application/json', accept: 'application/json' },
		body: JSON.stringify({ client_id: env.GITHUB_CLIENT_ID, client_secret: env.GITHUB_CLIENT_SECRET, code }),
	});
	const data = await response.json().catch(() => ({}));
	if (!data.access_token) return finish('error', { message: data.error_description ?? 'GitHub did not return a token.' });
	return finish('success', { token: data.access_token, provider: 'github' });
}

/** One entry point for hosts that route by path. */
export async function handle(request, env, fetchImpl = fetch) {
	const { pathname } = new URL(request.url);
	if (pathname.endsWith('/auth')) return auth(request, env);
	if (pathname.endsWith('/callback')) return callback(request, env, fetchImpl);
	return new Response('Not found', { status: 404 });
}
