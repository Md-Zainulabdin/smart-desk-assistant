"use client";

import { useMemo, useState } from "react";
import type { Note } from "@desk/shared-types";

import { CardList } from "@/components/ui/card-list";
import { EmptyState } from "@/components/ui/empty-state";
import { SearchIcon } from "@/components/ui/icons";

import { NoteRow } from "./note-row";

interface NoteListProps {
  notes: Note[];
}

export function NoteList({ notes }: NoteListProps) {
  const [query, setQuery] = useState("");

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return notes;
    return notes.filter((note) => note.content.toLowerCase().includes(needle));
  }, [notes, query]);

  if (notes.length === 0) {
    return <EmptyState message="No notes yet. Add one above." />;
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="surface-field flex items-center gap-2.5">
        <SearchIcon className="shrink-0 text-zinc-500" />
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search notes"
          aria-label="Search notes"
          className="w-full bg-transparent text-[14px] outline-none placeholder:text-zinc-500"
        />
      </div>

      {visible.length === 0 ? (
        <EmptyState
          message="No notes match."
          action={
            <button
              type="button"
              onClick={() => setQuery("")}
              className="text-[13px] text-zinc-500 underline transition-colors hover:text-foreground"
            >
              Clear search
            </button>
          }
        />
      ) : (
        <CardList>
          {visible.map((note) => (
            <NoteRow key={note.id} note={note} />
          ))}
        </CardList>
      )}
    </div>
  );
}
