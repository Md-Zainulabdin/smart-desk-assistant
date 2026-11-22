import type {
  CommandRequest,
  CommandResponse,
  Meeting,
  MeetingCreated,
  MeetingInput,
  Note,
  SearchData,
  SearchEnvelope,
  User,
} from "@desk/shared-types";

import { API_URL } from "./env";

/** Give up after this long so the UI can show an error instead of loading forever. */
const TIMEOUT_MS = 10_000;

/**
 * A failed backend call. `code` carries the backend error code, for example
 * `invalid_timezone` or `invalid_command`. The client adds `network_error` when
 * the server could not be reached and `timeout` when it did not answer in time.
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

function errorFrom(body: unknown, fallback: string): { message: string; code: string } {
  if (typeof body === "object" && body !== null) {
    if ("error" in body) {
      const error = (body as { error: unknown }).error;
      if (typeof error === "object" && error !== null) {
        const message = (error as { message: unknown }).message;
        const code = (error as { code: unknown }).code;
        return {
          message: typeof message === "string" ? message : fallback,
          code: typeof code === "string" ? code : "http_error",
        };
      }
    }
    if ("detail" in body) {
      const detail = (body as { detail: unknown }).detail;
      const code = (body as { code?: unknown }).code;
      if (typeof detail === "string") {
        return {
          message: detail,
          code: typeof code === "string" ? code : "http_error",
        };
      }
    }
  }
  return { message: fallback, code: "http_error" };
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers,
      credentials: "include",
      signal: init.signal ?? AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "TimeoutError") {
      throw new ApiError("The server took too long to answer.", 0, "timeout");
    }
    throw new ApiError("Could not reach the server.", 0, "network_error");
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const body: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    const { message, code } = errorFrom(body, response.statusText || "Request failed.");
    throw new ApiError(message, response.status, code);
  }

  return body as T;
}

/** Parse one command. Send the previous response back as `context` to complete it. */
export function sendCommand(command: CommandRequest): Promise<CommandResponse> {
  return request<CommandResponse>("/api/v1/command", {
    method: "POST",
    body: JSON.stringify(command),
  });
}

export function getCurrentUser(): Promise<User> {
  return request<User>("/auth/me");
}

export function logout(): Promise<void> {
  return request<void>("/auth/logout", { method: "POST" });
}

export function listNotes(): Promise<Note[]> {
  return request<Note[]>("/api/v1/notes");
}

export function createNote(content: string): Promise<Note> {
  return request<Note>("/api/v1/notes", {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}

export function listMeetings(): Promise<Meeting[]> {
  return request<Meeting[]>("/api/v1/calendar/meetings");
}

export function createMeeting(input: MeetingInput): Promise<MeetingCreated> {
  return request<MeetingCreated>("/api/v1/calendar/meetings", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function searchWeb(query: string): Promise<SearchData> {
  const envelope = await request<SearchEnvelope>("/api/v1/search", {
    method: "POST",
    body: JSON.stringify({ query }),
  });
  if (!envelope.success || envelope.data === null) {
    const error = envelope.error;
    throw new ApiError(error?.message ?? "Search failed.", 0, error?.code ?? "search_error");
  }
  return envelope.data;
}
