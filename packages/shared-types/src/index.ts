export type Intent =
  | "CREATE_NOTE"
  | "CREATE_REMINDER"
  | "CREATE_EVENT"
  | "READ_EVENTS"
  | "WEB_SEARCH"
  | "UNKNOWN";

export type Status = "ready" | "needs_clarification" | "unsupported";

export interface CommandContext {
  intent: Intent;
  slots: Record<string, string>;
  missing: string[];
}

export interface CommandRequest {
  text: string;
  request_id?: string;
  timezone?: string;
  context?: CommandContext;
}

export interface CommandResponse {
  text: string;
  intent: Intent;
  status: Status;
  slots: Record<string, string>;
  missing: string[];
  clarification: string | null;
}
