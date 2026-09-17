export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const API_V1 = `${API_BASE_URL}/api/v1`;

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function parseErrorDetail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
  } catch {
    // response wasn't JSON — fall through to statusText
  }
  return res.statusText || `Request failed with status ${res.status}`;
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_V1}${path}`);
  if (!res.ok) throw new ApiError(res.status, await parseErrorDetail(res));
  return (await res.json()) as T;
}

export async function apiPostForm<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`${API_V1}${path}`, { method: "POST", body: form });
  if (!res.ok) throw new ApiError(res.status, await parseErrorDetail(res));
  return (await res.json()) as T;
}

export async function apiPostJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_V1}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new ApiError(res.status, await parseErrorDetail(res));
  return (await res.json()) as T;
}

export async function apiPatchJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_V1}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new ApiError(res.status, await parseErrorDetail(res));
  return (await res.json()) as T;
}

export async function apiDelete<T>(path: string): Promise<T> {
  const res = await fetch(`${API_V1}${path}`, { method: "DELETE" });
  if (!res.ok) throw new ApiError(res.status, await parseErrorDetail(res));
  return (await res.json()) as T;
}
