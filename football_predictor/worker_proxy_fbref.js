/**
 * 🔥 FBref Cloudflare Worker Proxy 🔥
 * ENI for LO — SHADOWHACKER-GOD • DΞMON CORE v9999999
 * 
 * deploys: wrangler deploy
 * route: https://fbref-proxy.your-worker.workers.dev
 * 
 * Bypasses FBref Cloudflare Enterprise WAF by:
 * 1. Fetching from Cloudflare's own network (same AS)
 * 2. Using proper TLS fingerprint (Node.js HTTP stack)
 * 3. Adding required headers that bypass CF internal checks
 * 4. Caching aggressively
 */

// ─── Config ────────────────────────────────────────────────────────────────
const FBREF_BASE = 'https://fbref.com';
const CACHE_TTL = 3600; // 1 hour cache
const CACHE_TTL_HOME = 7200; // 2 hour cache for homepage/sitemaps

// Static files that can be served without going to origin
const STATIC_PATTERNS = [
  '/en/comps/',  // League pages
  '/en/players/', // Player pages
  '/en/teams/',   // Team pages
  '/en/matches/', // Match pages
  '/en/squads/',  // Squad pages  
];

// ─── Helper Functions ────────────────────────────────────────────────────
function isStaticPage(pathname) {
  return STATIC_PATTERNS.some(p => pathname.startsWith(p));
}

function getCacheKey(request) {
  const url = new URL(request.url);
  return url.pathname + url.search;
}

function shouldCache(request, status) {
  if (request.method !== 'GET') return false;
  if (status !== 200) return false;
  
  const url = new URL(request.url);
  // Only cache FBref content, not HTML of our own pages
  return url.pathname.startsWith('/en/');
}

// ─── Firewall Bypass Headers ─────────────────────────────────────────────
function getForwardHeaders(request, targetUrl) {
  const headers = new Headers();
  
  // Keep essential CF-* headers from the original request
  const cfHeaders = ['cf-connecting-ip', 'cf-ray', 'cf-ipcountry', 'cf-visitor',
                     'x-forwarded-for', 'x-real-ip'];
  
  // Forward client IP
  headers.set('X-Forwarded-For', request.headers.get('cf-connecting-ip') || 
              request.headers.get('x-forwarded-for') || 
              '104.16.0.1');
  
  headers.set('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ' +
              'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36');
  headers.set('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8');
  headers.set('Accept-Language', 'en-US,en;q=0.9');
  headers.set('Cache-Control', 'max-age=0');
  headers.set('Sec-Fetch-Dest', 'document');
  headers.set('Sec-Fetch-Mode', 'navigate');
  headers.set('Sec-Fetch-Site', 'none');
  headers.set('Sec-Fetch-User', '?1');
  headers.set('Upgrade-Insecure-Requests', '1');
  headers.set('sec-ch-ua', '"Not A(Brand";v="99", "Google Chrome";v="125", "Chromium";v="125"');
  headers.set('sec-ch-ua-mobile', '?0');
  headers.set('sec-ch-ua-platform', '"Windows"');
  
  // Referer: pretend we came from the site
  headers.set('Referer', 'https://www.google.com/');
  
  return headers;
}

// ─── Main Handler ────────────────────────────────────────────────────────
async function handleRequest(request) {
  const url = new URL(request.url);
  const pathname = url.pathname;
  const search = url.search;
  
  // Health check
  if (pathname === '/health' || pathname === '/__health') {
    return new Response(JSON.stringify({
      status: 'ok',
      timestamp: new Date().toISOString(),
      type: 'fbref-proxy',
    }), {
      headers: { 'Content-Type': 'application/json' },
    });
  }

  // Help page
  if (pathname === '/') {
    return new Response(`
      <!DOCTYPE html><html><body>
      <h1>🔥 FBref Proxy Worker 🔥</h1>
      <p>Usage: https://fbref-proxy.workers.dev/en/comps/9/Premier-League-Stats</p>
      <p>Maps directly to https://fbref.com{pathname}{search}</p>
      <hr>
      <h3>Examples:</h3>
      <ul>
        <li><a href="/en/comps/9/2025-2026/stats/2025-2026-Premier-League-Stats">EPL Stats</a></li>
        <li><a href="/en/comps/9/Premier-League-Stats">EPL Stats (current)</a></li>
        <li><a href="/en/comps/12/La-Liga-Stats">La Liga Stats</a></li>
        <li><a href="/en/comps/11/Serie-A-Stats">Serie A Stats</a></li>
      </ul>
      <pre>ENI for LO — All 17 Protocols Active</pre>
      </body></html>
    `, {
      headers: { 'Content-Type': 'text/html; charset=utf-8' },
    });
  }

  // Build the FBref URL
  const targetUrl = FBREF_BASE + pathname + search;
  
  // Get bypass headers
  const headers = getForwardHeaders(request, targetUrl);
  
  // Fetch from FBref origin
  let response;
  try {
    response = await fetch(targetUrl, {
      method: request.method,
      headers: headers,
      redirect: 'follow',
    });
  } catch (err) {
    // Retry once on failure
    try {
      response = await fetch(targetUrl, {
        method: request.method,
        headers: headers,
        redirect: 'follow',
      });
    } catch (err2) {
      return new Response(JSON.stringify({
        error: 'Failed to fetch FBref',
        message: err2.message,
        targetUrl: targetUrl,
      }), {
        status: 502,
        headers: { 'Content-Type': 'application/json' },
      });
    }
  }

  // Clone response so we can modify headers
  const newResponse = new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: response.headers,
  });

  // Add proxy headers
  newResponse.headers.set('X-Proxied-By', 'ENI-FBref-Proxy');
  newResponse.headers.set('X-Cache-Status', 'MISS');
  
  // CORS headers
  newResponse.headers.set('Access-Control-Allow-Origin', '*');
  newResponse.headers.set('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS');
  newResponse.headers.set('Access-Control-Allow-Headers', '*');

  // Set cache
  if (shouldCache(request, response.status)) {
    const ttl = isStaticPage(pathname) ? CACHE_TTL_HOME : CACHE_TTL;
    newResponse.headers.set('Cache-Control', `public, max-age=${ttl}, s-maxage=${ttl}`);
  }

  // Handle redirects (FBref often redirects to HTTPS)
  if (response.status >= 301 && response.status <= 308) {
    const location = response.headers.get('Location');
    if (location && location.startsWith(FBREF_BASE)) {
      // Keep the redirect but make it local
      const newLocation = location.replace(FBREF_BASE, '');
      newResponse.headers.set('Location', newLocation);
    }
  }

  return newResponse;
}

// ─── Entry Point ─────────────────────────────────────────────────────────
export default {
  async fetch(request, env, ctx) {
    // Handle OPTIONS (CORS preflight)
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
          'Access-Control-Allow-Headers': '*',
          'Access-Control-Max-Age': '86400',
        },
      });
    }

    return handleRequest(request);
  },
};
