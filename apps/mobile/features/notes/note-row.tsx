import { CardRow } from "@/components/ui/card-list";
import { formatDateTime } from "@/lib/format";
import type { Note } from "@desk/shared-types";

interface NoteRowProps {
  note: Note;
  href?: string;
  compact?: boolean;
}

function splitNote(content: string): { title: string; snippet: string } {
  const [first = "", ...rest] = content.split(/\r?\n/);
  return {
    title: first.trim() || "Untitled note",
    snippet: rest.join(" ").trim(),
  };
}

export function NoteRow({ note, href, compact = false }: NoteRowProps) {
  const { title, snippet } = splitNote(note.content);

  return (
    <CardRow href={href}>
      <p className="text-[14px] font-medium tracking-tight">{title}</p>

      {snippet && (
        <p
          className={`mt-1 text-[13px] leading-snug text-zinc-500 ${
            compact ? "line-clamp-1" : "line-clamp-2"
          }`}
        >
          {snippet}
        </p>
      )}

      {!compact && (
        <p className="mt-1.5 text-[13px] text-zinc-500">{formatDateTime(note.created_at)}</p>
      )}
    </CardRow>
  );
}
