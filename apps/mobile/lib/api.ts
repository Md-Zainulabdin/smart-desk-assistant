import type { CommandRequest, CommandResponse } from "@desk/shared-types";

import { API_URL } from "./env";

/**
 * A failed backend call. `code` carries the backend error code, for example
 * `invalid_timezone` or `invalid_command`, and `network_error` when the server
 * could not be reached at all.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(message: string, status: number, code: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

function detailFrom(body: unknown, fallback: string): string {
  if (typeof body === "object" && body !== null && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

function codeFrom(body: unknown): string {
  if (typeof body === "object" && body !== null && "code" in body) {
    const code = (body as { code: unknown }).code;
    if (typeof code === "string") return code;
  }
  return "http_error";
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...init, headers, credentials: "include" });
  } catch {
    throw new ApiError("Could not reach the server.", 0, "network_error");
  }

  const body: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    throw new ApiError(detailFrom(body, response.statusText), response.status, codeFrom(body));
  }

  return body as T;
}

export function getHealth(): Promise<{ status: string }> {
  return request<{ status: string }>("/health");
}

/** Parse one command. Send the previous response back as `context` to complete it. */
export function sendCommand(command: CommandRequest): Promise<CommandResponse> {
  return request<CommandResponse>("/api/v1/command", {
    method: "POST",
    body: JSON.stringify(command),
  });
}
