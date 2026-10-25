import type { Metadata } from "next";

import { PagePlaceholder } from "@/components/shell/page-placeholder";

export const metadata: Metadata = {
  title: "Reminders",
};

export default function RemindersPage() {
  return (
    <PagePlaceholder
      title="Reminders"
      description="Reminders with snooze and dismiss are added in stage 5."
    />
  );
}
