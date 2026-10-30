import { CardRow } from "@/components/ui/card-list";
import type { Note } from "@/lib/types";

interface NoteRowProps {
  note: Note;
  href?: string;
  compact?: boolean;
}

export function NoteRow({ note, href, compact = false }: NoteRowProps) {
  return (
    <CardRow href={href}>
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-[14px] font-medium tracking-tight">{note.title}</p>
        {note.pinned && !compact && (
          <span className="shrink-0 text-[11px] font-medium uppercase tracking-wide text-zinc-500">
            Pinned
          </span>
        )}
      </div>

      <p
        className={`mt-1 text-[13px] leading-snug text-zinc-500 ${
          compact ? "line-clamp-1" : "line-clamp-2"
        }`}
      >
        {note.snippet}
      </p>

      {!compact && (
        <p className="mt-1.5 text-[13px] text-zinc-500">
          {note.tag} · {note.updatedLabel}
        </p>
      )}
    </CardRow>
  );
}
