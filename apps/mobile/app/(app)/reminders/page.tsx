import type { Metadata } from "next";

import { PageHeader } from "@/components/ui/page-header";
import { ReminderGroups } from "@/features/reminders/reminder-groups";
import { reminders } from "@/lib/mock-data";

export const metadata: Metadata = {
  title: "Reminders",
};

export default function RemindersPage() {
  const dueToday = reminders.filter(
    (reminder) => reminder.bucket === "today" && !reminder.completed,
  ).length;
  const completed = reminders.filter((reminder) => reminder.completed).length;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Reminders" subtitle={`${dueToday} due today · ${completed} completed`} />
      <ReminderGroups reminders={reminders} />
    </div>
  );
}
