export type Intent =
  | "CREATE_NOTE"
  | "CREATE_CHECKLIST"
  | "CREATE_REMINDER"
  | "CREATE_EVENT"
  | "READ_EVENTS"
  | "UNKNOWN";

export interface CommandRequest {
  text: string;
  request_id?: string;
}

export interface CommandResponse {
  text: string;
  intent: Intent;
  slots: Record<string, string>;
}
