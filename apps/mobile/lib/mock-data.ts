/* Reminders are outside the evaluation-day MVP. The screen keeps local fixtures
   so the planned feature stays visible without pretending it is connected. */

import type { Reminder } from "./types";

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
