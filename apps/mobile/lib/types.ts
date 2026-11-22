export type ReminderBucket = "today" | "tomorrow" | "later";

export interface Reminder {
  id: string;
  text: string;
  dueLabel: string;
  bucket: ReminderBucket;
  completed: boolean;
  overdue?: boolean;
}
