export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch("/api" + path, options);
  const body = await response.json();
  if (!response.ok) {
    const detail = body.detail;
    throw new Error(
      typeof detail === "string" ? detail : JSON.stringify(detail ?? body),
    );
  }
  return body as T;
}
export function post<T>(path: string, body: unknown) {
  return api<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
