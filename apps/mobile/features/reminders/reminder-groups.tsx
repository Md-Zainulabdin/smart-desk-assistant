"use client";

import { useMemo, useState } from "react";

import { CardList } from "@/components/ui/card-list";
import { EmptyState } from "@/components/ui/empty-state";
import { FilterChips } from "@/components/ui/filter-chips";
import { SectionHeader } from "@/components/ui/section-header";
import { ReminderRow } from "@/features/reminders/reminder-row";
import { useReminders } from "@/features/reminders/use-reminders";
import type { Reminder } from "@/lib/types";

type Filter = "all" | "today" | "upcoming" | "completed";

const FILTERS = [
  { value: "all", label: "All" },
  { value: "today", label: "Today" },
  { value: "upcoming", label: "Upcoming" },
  { value: "completed", label: "Completed" },
] as const;

interface ReminderGroupsProps {
  reminders: Reminder[];
}

export function ReminderGroups({ reminders: initial }: ReminderGroupsProps) {
  const { reminders, toggle } = useReminders(initial);
  const [filter, setFilter] = useState<Filter>("all");

  const sections = useMemo(() => {
    const open = reminders.filter((reminder) => !reminder.completed);
    const completed = reminders.filter((reminder) => reminder.completed);
    const bucket = (name: Reminder["bucket"]) =>
      open.filter((reminder) => reminder.bucket === name);

    if (filter === "today") return [{ title: "Today", items: bucket("today") }];
    if (filter === "upcoming") {
      return [
        { title: "Tomorrow", items: bucket("tomorrow") },
        { title: "Later", items: bucket("later") },
      ];
    }
    if (filter === "completed") {
      return [{ title: "Completed", items: completed }];
    }
    return [
      { title: "Today", items: bucket("today") },
      { title: "Tomorrow", items: bucket("tomorrow") },
      { title: "Later", items: bucket("later") },
      { title: "Completed", items: completed },
    ];
  }, [reminders, filter]);

  const visible = sections.filter((section) => section.items.length > 0);

  return (
    <div className="flex flex-col gap-6">
      <FilterChips label="Filter reminders" options={FILTERS} value={filter} onChange={setFilter} />

      {visible.length === 0 ? (
        <EmptyState
          message={filter === "completed" ? "Nothing completed yet." : "No reminders here."}
        />
      ) : (
        <div className="flex flex-col gap-8">
          {visible.map((section) => (
            <section key={section.title}>
              <SectionHeader title={section.title} />
              <div className="mt-4">
                <CardList>
                  {section.items.map((reminder) => (
                    <ReminderRow key={reminder.id} reminder={reminder} onToggle={toggle} />
                  ))}
                </CardList>
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
