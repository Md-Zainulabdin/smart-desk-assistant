"use client";

import { CardList } from "@/components/ui/card-list";
import { SectionHeader } from "@/components/ui/section-header";
import { ReminderRow } from "@/features/reminders/reminder-row";
import { useReminders } from "@/features/reminders/use-reminders";
import type { Reminder } from "@/lib/types";

interface ReminderListProps {
  reminders: Reminder[];
}

export function ReminderList({ reminders: initial }: ReminderListProps) {
  const { reminders, toggle } = useReminders(initial);

  return (
    <section>
      <SectionHeader title="Reminders" href="/reminders" />

      {reminders.length === 0 ? (
        <p className="mt-4 text-[14px] text-zinc-500">You&apos;re all caught up.</p>
      ) : (
        <div className="mt-4">
          <CardList>
            {reminders.map((reminder) => (
              <ReminderRow key={reminder.id} reminder={reminder} onToggle={toggle} />
            ))}
          </CardList>
        </div>
      )}
    </section>
  );
}
