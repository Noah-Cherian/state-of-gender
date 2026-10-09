// Every data request goes through here, so where the data comes from is
// decided in exactly one place.
//
// By default the site reads static JSON files from /data/ (made by
// api/export_static.py and served by Vercel along with the rest of the
// site). That avoids waiting on the free-tier API, which sleeps when idle
// and can take up to a minute to wake.
//
// Setting VITE_USE_LIVE_API=true (in web/.env) switches back to calling the
// FastAPI server directly -- handy when changing the API locally and
// wanting to see the result without re-exporting.
const USE_LIVE_API = import.meta.env.VITE_USE_LIVE_API === "true";

// A trailing slash is trimmed so "https://x.onrender.com/" and
// "https://x.onrender.com" both work.
const API_BASE = (import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000").replace(/\/+$/, "");

async function getJSON(apiPath, staticPath) {
  const url = USE_LIVE_API ? `${API_BASE}${apiPath}` : `/data/${staticPath}`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${url} failed: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

export function fetchStates() {
  return getJSON("/api/states", "states.json");
}

export function fetchMetrics() {
  return getJSON("/api/metrics", "metrics.json");
}

export function fetchMetricMap(slug) {
  return getJSON(`/api/metrics/${slug}`, `metrics/${slug}.json`);
}

export function fetchStateProfile(code) {
  return getJSON(`/api/states/${code}`, `states/${code.toUpperCase()}.json`);
}
