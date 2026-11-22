"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { LoadError, LoadingState } from "@/components/ui/load-state";
import { PageHeader } from "@/components/ui/page-header";
import { NoteList } from "@/features/notes/note-list";
import { createNote, listNotes } from "@/lib/api";

export function NotesView() {
  const queryClient = useQueryClient();
  const notesQuery = useQuery({ queryKey: ["notes"], queryFn: listNotes });
  const createNoteMutation = useMutation({
    mutationFn: createNote,
    onSuccess: async () => {
      setContent("");
      await queryClient.invalidateQueries({ queryKey: ["notes"] });
    },
  });
  const [content, setContent] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = content.trim();
    if (!text || createNoteMutation.isPending) return;
    createNoteMutation.mutate(text);
  }

  const notes = notesQuery.data ?? [];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Notes" subtitle={notesQuery.data ? `${notes.length} notes` : undefined} />

      <form onSubmit={handleSubmit} className="surface-card flex flex-col gap-3">
        <label htmlFor="note-content" className="text-[13px] font-medium">
          New note
        </label>
        <textarea
          id="note-content"
          value={content}
          onChange={(event) => setContent(event.target.value)}
          rows={3}
          placeholder="Write a note…"
          className="w-full resize-y bg-transparent text-[14px] outline-none placeholder:text-zinc-500"
        />
        {createNoteMutation.error && (
          <p className="text-[13px] text-red-500">{createNoteMutation.error.message}</p>
        )}
        <button
          type="submit"
          disabled={createNoteMutation.isPending || content.trim().length === 0}
          className="self-start rounded-full bg-foreground px-5 py-2 text-sm font-medium text-background disabled:opacity-50"
        >
          {createNoteMutation.isPending ? "Saving…" : "Save note"}
        </button>
      </form>

      {notesQuery.isPending ? (
        <LoadingState label="Loading notes…" />
      ) : notesQuery.error ? (
        <LoadError message={notesQuery.error.message} onRetry={() => void notesQuery.refetch()} />
      ) : (
        <NoteList notes={notes} />
      )}
    </div>
  );
}
