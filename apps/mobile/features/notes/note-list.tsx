"use client";

import { useMemo, useState } from "react";

import { CardList } from "@/components/ui/card-list";
import { EmptyState } from "@/components/ui/empty-state";
import { FilterChips } from "@/components/ui/filter-chips";
import { SearchIcon } from "@/components/ui/icons";
import { SectionHeader } from "@/components/ui/section-header";
import type { Note } from "@/lib/types";

import { NoteRow } from "./note-row";

interface NoteListProps {
  notes: Note[];
}

export function NoteList({ notes }: NoteListProps) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");

  const filters = useMemo(
    () => [
      { value: "all", label: "All" },
      { value: "pinned", label: "Pinned" },
      ...Array.from(new Set(notes.map((note) => note.tag))).map((tag) => ({
        value: tag,
        label: tag,
      })),
    ],
    [notes],
  );

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return notes.filter((note) => {
      if (filter === "pinned" && !note.pinned) return false;
      if (filter !== "all" && filter !== "pinned" && note.tag !== filter) {
        return false;
      }
      if (!needle) return true;
      return `${note.title} ${note.snippet}`.toLowerCase().includes(needle);
    });
  }, [notes, query, filter]);

  const pinned = visible.filter((note) => note.pinned);
  const rest = visible.filter((note) => !note.pinned);

  function resetFilters() {
    setQuery("");
    setFilter("all");
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

      <FilterChips label="Filter notes" options={filters} value={filter} onChange={setFilter} />

      {visible.length === 0 ? (
        <EmptyState
          message="No notes match."
          action={
            <button
              type="button"
              onClick={resetFilters}
              className="text-[13px] text-zinc-500 underline transition-colors hover:text-foreground"
            >
              Clear filters
            </button>
          }
        />
      ) : (
        <div className="flex flex-col gap-8">
          {pinned.length > 0 && (
            <section>
              <SectionHeader title="Pinned" />
              <div className="mt-4">
                <CardList>
                  {pinned.map((note) => (
                    <NoteRow key={note.id} note={note} />
                  ))}
                </CardList>
              </div>
            </section>
          )}

          {rest.length > 0 && (
            <section>
              <SectionHeader title={pinned.length > 0 ? "All notes" : "Notes"} />
              <div className="mt-4">
                <CardList>
                  {rest.map((note) => (
                    <NoteRow key={note.id} note={note} />
                  ))}
                </CardList>
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
