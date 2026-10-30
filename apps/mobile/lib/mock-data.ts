/* Mock data for the prototype screens. Types live in lib/types.ts so components
   stay data-agnostic and features can import them without the fixtures. */

import type {
  Account,
  AppInfo,
  AssistantStatus,
  DeviceInfo,
  Meeting,
  Note,
  NotificationOption,
  Reminder,
} from "./types";

// ── Home ──────────────────────────────────────────────────────────

export const assistantStatus: AssistantStatus = {
  isOnline: true,
  contextState: "IN_MEETING",
  notificationMode: "SHOW_SILENTLY",
  statusLabel: "In a meeting · Silent notifications",
  explanation: "Your calendar shows a meeting until 4 PM.",
};

export const nextMeeting: Meeting | null = {
  id: "mtg-1",
  title: "Project progress meeting",
  timeLabel: "2:00 – 4:00 PM",
  dateLabel: "Today",
};

// ── Notes ─────────────────────────────────────────────────────────

export const notes: Note[] = [
  {
    id: "note-1",
    title: "Project discussion",
    snippet:
      "Finish Calendar integration before the sprint review on Friday. The parser is already merged, so the remaining work is the PWA screens and the auth callback.",
    tag: "Work",
    updatedLabel: "Updated today",
    pinned: true,
  },
  {
    id: "note-2",
    title: "Shopping checklist",
    snippet: "2 of 4 completed: microphone, USB hub, desk lamp, cable tray.",
    tag: "Personal",
    updatedLabel: "Updated today",
    pinned: true,
  },
  {
    id: "note-3",
    title: "Sprint retro notes",
    snippet:
      "What went well: the command parser shipped with tests. What to improve: smaller pull requests and earlier integration checks.",
    tag: "Work",
    updatedLabel: "Updated yesterday",
    pinned: false,
  },
  {
    id: "note-4",
    title: "Desk setup ideas",
    snippet:
      "Raise the monitor to eye level, add a warm lamp on the left, and keep the cable tray under the desk.",
    tag: "Personal",
    updatedLabel: "Updated 2 days ago",
    pinned: false,
  },
  {
    id: "note-5",
    title: "Meeting with supervisor",
    snippet:
      "Agenda: demo the parser, confirm the Google Calendar scopes, and agree on the notification modes.",
    tag: "Work",
    updatedLabel: "Updated 3 days ago",
    pinned: false,
  },
  {
    id: "note-6",
    title: "Reading list",
    snippet:
      "Designing Data-Intensive Applications, chapter 5. Refactoring UI, sections on spacing and contrast.",
    tag: "Ideas",
    updatedLabel: "Updated 4 days ago",
    pinned: false,
  },
  {
    id: "note-7",
    title: "Monthly budget",
    snippet:
      "Fixed costs, groceries, transport, and a small buffer for hardware. Review on the first Sunday.",
    tag: "Personal",
    updatedLabel: "Updated last week",
    pinned: false,
  },
  {
    id: "note-8",
    title: "API integration checklist",
    snippet:
      "CORS, session cookie, auth callback, error codes, and the contract mirror in shared-types.",
    tag: "Work",
    updatedLabel: "Updated last week",
    pinned: false,
  },
];

// ── Reminders ─────────────────────────────────────────────────────

export const reminders: Reminder[] = [
  {
    id: "rem-1",
    text: "Submit assignment",
    dueLabel: "Today, 6 PM",
    bucket: "today",
    completed: false,
  },
  {
    id: "rem-2",
    text: "Send sprint notes to the team",
    dueLabel: "Today, 9 PM",
    bucket: "today",
    completed: false,
  },
  {
    id: "rem-3",
    text: "Call the courier service",
    dueLabel: "Today, 11 AM",
    bucket: "today",
    completed: false,
    overdue: true,
  },
  {
    id: "rem-4",
    text: "Buy microphone",
    dueLabel: "Tomorrow, 10 AM",
    bucket: "tomorrow",
    completed: false,
  },
  {
    id: "rem-5",
    text: "Review calendar integration PR",
    dueLabel: "Tomorrow, 9 AM",
    bucket: "tomorrow",
    completed: false,
  },
  {
    id: "rem-6",
    text: "Pay internet bill",
    dueLabel: "Friday, 5 PM",
    bucket: "later",
    completed: false,
  },
  {
    id: "rem-7",
    text: "Book dentist appointment",
    dueLabel: "Yesterday, 4 PM",
    bucket: "later",
    completed: true,
  },
];

// ── Settings ──────────────────────────────────────────────────────

export const notificationOptions: NotificationOption[] = [
  {
    mode: "SPEAK_AND_SHOW",
    label: "Speak and show",
    description: "Read the notification out loud and show it on the desk display.",
  },
  {
    mode: "SHOW_SILENTLY",
    label: "Show silently",
    description: "Show it on the display without any sound.",
  },
  {
    mode: "DELAY",
    label: "Delay",
    description: "Hold notifications until the current meeting ends.",
  },
  {
    mode: "MOBILE_ONLY",
    label: "Mobile only",
    description: "Send it to your phone and keep the desk quiet.",
  },
];

export const account: Account = {
  name: "Zain-ul-Abdin",
  email: "zain@example.com",
  provider: "Google",
};

export const deviceInfo: DeviceInfo = {
  isOnline: true,
  lastSyncLabel: "2 minutes ago",
};

export const appInfo: AppInfo = {
  version: "0.1.0",
};
