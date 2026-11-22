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
  request_id?: string | null;
  timezone?: string | null;
  context?: CommandContext | null;
}

export interface CommandResponse {
  text: string;
  intent: Intent;
  status: Status;
  slots: Record<string, string>;
  missing: string[];
  clarification: string | null;
}

export interface User {
  id: string;
  email: string;
  name: string | null;
  picture_url: string | null;
}

export interface Note {
  id: string;
  content: string;
  created_at: string;
}

export interface Meeting {
  id: string;
  title: string;
  start: string;
  end: string;
  all_day: boolean;
  link: string;
  meet_link: string | null;
}

export interface MeetingInput {
  title: string;
  start: string;
  end: string;
  timezone?: string | null;
  attendees?: string[];
  description?: string;
  request_id?: string | null;
}

export interface MeetingCreated {
  id: string;
  link: string;
  meet_link: string | null;
}

export interface SearchResult {
  title: string;
  url: string;
  snippet: string;
}

export interface SearchData {
  query: string;
  results: SearchResult[];
}

export interface SearchEnvelope {
  success: boolean;
  data: SearchData | null;
  error: { code: string; message: string } | null;
}
