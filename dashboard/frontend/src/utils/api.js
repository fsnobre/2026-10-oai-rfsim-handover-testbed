const configured = import.meta.env.VITE_API_BASE_URL;

export const API_BASE_URL =
  configured || `${window.location.protocol}//${window.location.hostname}:8000`;

const TOKEN_STORAGE_KEY = "dashboard_api_token";

export function getApiToken() {
  try {
    return window.localStorage.getItem(TOKEN_STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

export function setApiToken(token) {
  try {
    if (token) window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
    else window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    /* ignore storage errors (private mode, etc.) */
  }
}

function authHeaders() {
  const token = getApiToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function wsUrl(path = "/ws") {
  const base = new URL(API_BASE_URL);
  base.protocol = base.protocol === "https:" ? "wss:" : "ws:";
  base.pathname = path;
  base.search = "";
  const token = getApiToken();
  if (token) base.search = `?token=${encodeURIComponent(token)}`;
  return base.toString();
}

export async function apiGet(path) {
  const url = new URL(path, API_BASE_URL);
  const response = await fetch(url, { headers: { ...authHeaders() } });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
}

export async function apiPost(path, payload) {
  const url = new URL(path, API_BASE_URL);
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(payload || {}),
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(data.detail || `${response.status} ${response.statusText}`);
  }
  return data;
}
