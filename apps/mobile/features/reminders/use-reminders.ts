import { useState } from "react";

import type { Reminder } from "@/lib/types";

/* Home shows a slice, the reminders page shows groups; both toggle the same way. */
export function useReminders(initial: Reminder[]) {
  const [reminders, setReminders] = useState(initial);

  function toggle(id: string) {
    setReminders((prev) =>
      prev.map((reminder) =>
        reminder.id === id ? { ...reminder, completed: !reminder.completed } : reminder,
      ),
    );
  }

  return { reminders, toggle };
}
