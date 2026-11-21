import { CardList } from "@/components/ui/card-list";
import { SectionHeader } from "@/components/ui/section-header";
import { NoteRow } from "@/features/notes/note-row";
import type { Note } from "@/lib/types";

interface RecentNotesProps {
  notes: Note[];
}

export function RecentNotes({ notes }: RecentNotesProps) {
  return (
    <section>
      <SectionHeader title="Recent notes" href="/notes" />

      {notes.length === 0 ? (
        <p className="mt-4 text-[14px] text-zinc-500">No notes yet.</p>
      ) : (
        <div className="mt-4">
          <CardList>
            {notes.map((note) => (
              <NoteRow key={note.id} note={note} href="/notes" compact />
            ))}
          </CardList>
        </div>
      )}
    </section>
  );
}
