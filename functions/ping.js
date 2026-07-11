// Temporary deploy-path probe (issue #43 Phase 2a).
// Proves a top-level functions/ dir auto-deploys via the git-connected
// Cloudflare Pages build. Removed once the auto-deploy is confirmed.
export function onRequest() {
  return new Response("pong", {
    status: 200,
    headers: { "content-type": "text/plain; charset=utf-8" },
  });
}
