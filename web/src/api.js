// Every call to the API goes through here, so the base address lives in
// exactly one place. VITE_API_BASE comes from web/.env (see .env.example).
const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

async function getJSON(path) {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`${path} failed: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

export function fetchStates() {
  return getJSON("/api/states");
}

export function fetchMetricMap(slug) {
  return getJSON(`/api/metrics/${slug}`);
}

export function fetchStateProfile(code) {
  return getJSON(`/api/states/${code}`);
}
