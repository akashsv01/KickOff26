const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("kickoff_token");
}

export function setToken(token: string) {
  localStorage.setItem("kickoff_token", token);
}

export function clearToken() {
  localStorage.removeItem("kickoff_token");
}

export function formatApiError(detail: unknown, fallback = "Request failed"): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item) {
          const loc = "loc" in item && Array.isArray(item.loc) ? item.loc.slice(-1)[0] : "";
          return loc ? `${loc}: ${item.msg}` : String(item.msg);
        }
        return "Invalid input";
      })
      .join("; ");
  }
  return fallback;
}

const DEFAULT_TIMEOUT_MS = 30_000;

export async function api<T>(
  path: string,
  options: RequestInit = {},
  timeoutMs = DEFAULT_TIMEOUT_MS
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(`${API_URL}/api${path}`, {
      ...options,
      headers,
      signal: options.signal ?? controller.signal,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(formatApiError(err.detail, res.statusText));
    }
    // No-content responses (e.g. 204 from DELETE) have an empty body - don't
    // try to parse them as JSON.
    if (res.status === 204 || res.status === 205) {
      return undefined as T;
    }
    const text = await res.text();
    return (text ? JSON.parse(text) : undefined) as T;
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      throw new Error(
        `Request timed out - is the backend running at ${API_URL}?`
      );
    }
    if (err instanceof TypeError) {
      throw new Error(`Cannot reach API at ${API_URL}. Start the backend server.`);
    }
    throw err;
  } finally {
    clearTimeout(timeout);
  }
}

export { API_URL };
