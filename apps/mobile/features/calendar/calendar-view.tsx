"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { CardList, CardRow } from "@/components/ui/card-list";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadError, LoadingState } from "@/components/ui/load-state";
import { PageHeader } from "@/components/ui/page-header";
import { createMeeting, listMeetings } from "@/lib/api";
import { formatDate, formatTime } from "@/lib/format";

export function CalendarView() {
  const queryClient = useQueryClient();
  const meetingsQuery = useQuery({ queryKey: ["meetings"], queryFn: listMeetings });
  const createMeetingMutation = useMutation({
    mutationFn: createMeeting,
    onSuccess: async () => {
      setTitle("");
      setStart("");
      setEnd("");
      await queryClient.invalidateQueries({ queryKey: ["meetings"] });
    },
  });
  const [title, setTitle] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!title.trim() || !start || !end || createMeetingMutation.isPending) return;

    createMeetingMutation.mutate({
      title: title.trim(),
      start: new Date(start).toISOString(),
      end: new Date(end).toISOString(),
      request_id: crypto.randomUUID(),
    });
  }

  const meetings = meetingsQuery.data ?? [];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Calendar" subtitle="Upcoming meetings from Google Calendar" />

      <form onSubmit={handleSubmit} className="surface-card flex flex-col gap-3">
        <h2 className="text-[13px] font-medium">New meeting</h2>
        <label className="flex flex-col gap-1 text-[13px] text-zinc-500">
          Title
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            maxLength={200}
            placeholder="Design review"
            className="rounded-lg border border-hairline bg-transparent px-3 py-2 text-[14px] text-foreground outline-none"
          />
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="flex flex-col gap-1 text-[13px] text-zinc-500">
            Starts
            <input
              type="datetime-local"
              value={start}
              onChange={(event) => setStart(event.target.value)}
              className="rounded-lg border border-hairline bg-transparent px-3 py-2 text-[14px] text-foreground outline-none"
            />
          </label>
          <label className="flex flex-col gap-1 text-[13px] text-zinc-500">
            Ends
            <input
              type="datetime-local"
              value={end}
              onChange={(event) => setEnd(event.target.value)}
              className="rounded-lg border border-hairline bg-transparent px-3 py-2 text-[14px] text-foreground outline-none"
            />
          </label>
        </div>
        {createMeetingMutation.error && (
          <p className="text-[13px] text-red-500">{createMeetingMutation.error.message}</p>
        )}
        <button
          type="submit"
          disabled={createMeetingMutation.isPending || !title.trim() || !start || !end}
          className="self-start rounded-full bg-foreground px-5 py-2 text-sm font-medium text-background disabled:opacity-50"
        >
          {createMeetingMutation.isPending ? "Creating…" : "Create meeting"}
        </button>
      </form>

      {meetingsQuery.isPending ? (
        <LoadingState label="Loading meetings…" />
      ) : meetingsQuery.error ? (
        <LoadError
          message={meetingsQuery.error.message}
          onRetry={() => void meetingsQuery.refetch()}
        />
      ) : meetings.length === 0 ? (
        <EmptyState message="No upcoming meetings in the next 7 days." />
      ) : (
        <CardList>
          {meetings.map((meeting) => (
            <CardRow key={meeting.id}>
              <a
                href={meeting.link}
                target="_blank"
                rel="noreferrer"
                className="block transition-colors hover:text-foreground"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <p className="text-[14px] font-medium tracking-tight">{meeting.title}</p>
                  <p className="shrink-0 text-[13px] text-zinc-500">{formatDate(meeting.start)}</p>
                </div>
                <p className="mt-1 text-[13px] text-zinc-500">
                  {meeting.all_day
                    ? "All day"
                    : `${formatTime(meeting.start)} - ${formatTime(meeting.end)}`}
                  {meeting.meet_link ? " · Google Meet" : ""}
                </p>
              </a>
            </CardRow>
          ))}
        </CardList>
      )}
    </div>
  );
}
