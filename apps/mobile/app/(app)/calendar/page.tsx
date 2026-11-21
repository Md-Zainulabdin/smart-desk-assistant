import type { Metadata } from "next";

import { PagePlaceholder } from "@/components/shell/page-placeholder";

export const metadata: Metadata = {
  title: "Calendar",
};

export default function CalendarPage() {
  return (
    <PagePlaceholder
      title="Calendar"
      description="Upcoming events and event creation are added in stage 6."
    />
  );
}
