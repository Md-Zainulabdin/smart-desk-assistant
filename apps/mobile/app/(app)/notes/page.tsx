import type { Metadata } from "next";

import { PageHeader } from "@/components/ui/page-header";
import { NoteList } from "@/features/notes/note-list";
import { notes } from "@/lib/mock-data";

export const metadata: Metadata = {
  title: "Notes",
};

export default function NotesPage() {
  const pinned = notes.filter((note) => note.pinned).length;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Notes" subtitle={`${notes.length} notes · ${pinned} pinned`} />
      <NoteList notes={notes} />
    </div>
  );
}
