import { CardRow } from "@/components/ui/card-list";
import { IconButton } from "@/components/ui/icon-button";
import { CheckIcon, ClockIcon } from "@/components/ui/icons";
import type { Reminder } from "@/lib/types";

interface ReminderRowProps {
  reminder: Reminder;
  onToggle?: (id: string) => void;
}

export function ReminderRow({ reminder, onToggle }: ReminderRowProps) {
  return (
    <CardRow>
      <div
        className={`flex items-start justify-between gap-4 ${
          reminder.completed ? "opacity-40" : ""
        }`}
      >
        <div className="min-w-0 flex-1">
          <p
            className={`text-[14px] leading-snug ${
              reminder.completed ? "line-through text-zinc-500" : ""
            }`}
          >
            {reminder.text}
          </p>
          <p className="mt-1 flex items-center gap-1.5 text-[13px] text-zinc-500">
            {reminder.overdue && (
              <span
                className="inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500"
                aria-hidden="true"
              />
            )}
            {reminder.dueLabel}
            {reminder.overdue && <span className="sr-only">Overdue</span>}
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-1">
          <IconButton
            label={reminder.completed ? "Undo complete" : "Complete"}
            pressed={reminder.completed}
            onClick={onToggle ? () => onToggle(reminder.id) : undefined}
          >
            <CheckIcon />
          </IconButton>
          <IconButton label="Snooze" disabled>
            <ClockIcon />
          </IconButton>
        </div>
      </div>
    </CardRow>
  );
}
