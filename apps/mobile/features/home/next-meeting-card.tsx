import Link from "next/link";
import type { Meeting } from "@desk/shared-types";

import { formatDate, formatTime } from "@/lib/format";

interface NextMeetingCardProps {
  meeting: Meeting | null;
}

export function NextMeetingCard({ meeting }: NextMeetingCardProps) {
  if (!meeting) {
    return (
      <div className="surface-card">
        <p className="text-[14px] text-zinc-500">No upcoming meetings</p>
      </div>
    );
  }

  return (
    <Link
      href="/calendar"
      className="surface-card block transition-colors hover:border-black/15 dark:hover:border-white/20"
    >
      <p className="text-[15px] font-medium tracking-tight">{meeting.title}</p>
      <p className="mt-2 text-[13px] text-zinc-500">
        {formatDate(meeting.start)}
        {meeting.all_day
          ? " · All day"
          : `, ${formatTime(meeting.start)} - ${formatTime(meeting.end)}`}
      </p>
    </Link>
  );
}
