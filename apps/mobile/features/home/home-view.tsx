"use client";

import { useQuery } from "@tanstack/react-query";

import { LoadError, LoadingState } from "@/components/ui/load-state";
import { SectionHeader } from "@/components/ui/section-header";
import { GreetingHeader } from "@/features/home/greeting-header";
import { NextMeetingCard } from "@/features/home/next-meeting-card";
import { RecentNotes } from "@/features/home/recent-notes";
import { listMeetings, listNotes } from "@/lib/api";

export function HomeView() {
  const meetingsQuery = useQuery({ queryKey: ["meetings"], queryFn: listMeetings });
  const notesQuery = useQuery({ queryKey: ["notes"], queryFn: listNotes });

  const meetings = meetingsQuery.data ?? [];
  const notes = notesQuery.data ?? [];
  const loading = meetingsQuery.isPending || notesQuery.isPending;
  const error = meetingsQuery.error ?? notesQuery.error;

  function retry() {
    void meetingsQuery.refetch();
    void notesQuery.refetch();
  }

  return (
    <div className="flex flex-col gap-8 pb-6">
      <GreetingHeader />

      {loading ? (
        <LoadingState label="Loading your desk…" />
      ) : error ? (
        <LoadError message={error.message} onRetry={retry} />
      ) : (
        <>
          <section>
            <SectionHeader title="Next up" />
            <div className="mt-4">
              <NextMeetingCard meeting={meetings[0] ?? null} />
            </div>
          </section>

          <RecentNotes notes={notes.slice(0, 2)} />
        </>
      )}
    </div>
  );
}
