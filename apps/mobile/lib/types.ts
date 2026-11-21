/* View models for the mock screens. Keep types here so features share them
   without importing fixtures from mock-data. */

export type ContextState = "AVAILABLE" | "IN_MEETING" | "AWAY" | "PRESENT_UNKNOWN";

export type NotificationMode = "SPEAK_AND_SHOW" | "SHOW_SILENTLY" | "DELAY" | "MOBILE_ONLY";

export interface AssistantStatus {
  isOnline: boolean;
  contextState: ContextState;
  notificationMode: NotificationMode;
  statusLabel: string;
  explanation: string;
}

export interface Meeting {
  id: string;
  title: string;
  timeLabel: string;
  dateLabel: string;
}

export type ReminderBucket = "today" | "tomorrow" | "later";

export interface Reminder {
  id: string;
  text: string;
  dueLabel: string;
  bucket: ReminderBucket;
  completed: boolean;
  overdue?: boolean;
}

export interface Note {
  id: string;
  title: string;
  snippet: string;
  tag: string;
  updatedLabel: string;
  pinned: boolean;
}

export interface NotificationOption {
  mode: NotificationMode;
  label: string;
  description: string;
}

export interface Account {
  name: string;
  email: string;
  provider: string;
}

export interface DeviceInfo {
  isOnline: boolean;
  lastSyncLabel: string;
}

export interface AppInfo {
  version: string;
}
