const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

let accessToken: string | null = null;

export function setAccessToken(token: string | null) { accessToken = token; }
export function getAccessToken() { return accessToken; }

type Method = "GET" | "POST" | "PATCH" | "DELETE" | "PUT";

class ApiError extends Error {
  constructor(public status: number, message: string, public data?: unknown) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  method: Method = "GET",
  body?: unknown,
  retry = true
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    credentials: "include",
    body: body != null ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401 && retry) {
    const refreshed = await silentRefresh();
    if (refreshed) return request<T>(path, method, body, false);
    throw new ApiError(401, "Session expired");
  }

  if (!res.ok) {
    let data: unknown;
    try { data = await res.json(); } catch {}
    const msg = (data as Record<string, string>)?.detail || res.statusText;
    throw new ApiError(res.status, msg, data);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

async function silentRefresh(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
    if (!res.ok) { accessToken = null; return false; }
    const data = await res.json();
    accessToken = data.access_token;
    return true;
  } catch { return false; }
}

export const api = {
  get: <T>(path: string) => request<T>(path, "GET"),
  post: <T>(path: string, body?: unknown) => request<T>(path, "POST", body),
  patch: <T>(path: string, body?: unknown) => request<T>(path, "PATCH", body),
  delete: <T>(path: string) => request<T>(path, "DELETE"),
  refresh: silentRefresh,
};

export { ApiError };
