/** Typed API client for the Next Gent Sofia Trade v1 backend (OpenAPI contract, FR §5.1). */

const BASE = "";

/** Error envelope, PRD §12.6. `request_id` correlates with the server log. */
export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    request_id: string;
    details?: unknown;
    status: number;
  };
}

export class ApiError extends Error {
  code: string;
  status: number;
  requestId: string;
  details?: unknown;
  constructor(body: ApiErrorBody) {
    super(body.error.message);
    this.name = "ApiError";
    this.code = body.error.code;
    this.status = body.error.status;
    this.requestId = body.error.request_id;
    this.details = body.error.details;
  }
}

export function authHeaders(): Record<string, string> {
  const token = sessionStorage.getItem("sofia_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** True when the request was not authenticated (session missing or expired). */
export function isUnauthorized(err: unknown): boolean {
  return err instanceof ApiError && err.status === 401;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...authHeaders(), ...(init?.headers ?? {}) },
  });
  const data = (await res.json().catch(() => ({}))) as unknown;
  if (!res.ok) {
    if (typeof data === "object" && data !== null && "error" in data) {
      throw new ApiError(data as ApiErrorBody);
    }
    throw new Error(`HTTP ${res.status} on ${path}`);
  }
  return data as T;
}

export const get = <T>(path: string) => api<T>(path);
export const post = <T>(path: string, body?: unknown) => api<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) });
export const put = <T>(path: string, body?: unknown) => api<T>(path, { method: "PUT", body: JSON.stringify(body ?? {}) });
export const del = <T>(path: string) => api<T>(path, { method: "DELETE" });
