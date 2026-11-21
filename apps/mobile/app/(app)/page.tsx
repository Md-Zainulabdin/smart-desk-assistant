import { AssistantStatusCard } from "@/components/ui/assistant-status-card";
import { SectionHeader } from "@/components/ui/section-header";
import { GreetingHeader } from "@/features/home/greeting-header";
import { NextMeetingCard } from "@/features/home/next-meeting-card";
import { RecentNotes } from "@/features/home/recent-notes";
import { ReminderList } from "@/features/home/reminder-list";
import { assistantStatus, nextMeeting, notes, reminders } from "@/lib/mock-data";

export default function Home() {
  const openReminders = reminders.filter((reminder) => !reminder.completed).slice(0, 2);

  return (
    <div className="flex flex-col gap-8 pb-6">
      <GreetingHeader />

      <AssistantStatusCard status={assistantStatus} />

      <section>
        <SectionHeader title="Next up" />
        <div className="mt-4">
          <NextMeetingCard meeting={nextMeeting} />
        </div>
      </section>

      <ReminderList reminders={openReminders} />

      <RecentNotes notes={notes.slice(0, 2)} />
    </div>
  );
}
