import Link from "next/link";
import type { ReactNode } from "react";

interface CardListProps {
  children: ReactNode;
}

interface CardRowProps {
  children: ReactNode;
  href?: string;
}

/* Rows space themselves; the card owns the outer padding, so the first and last
   row drop their own padding instead of every list re-implementing it. */
const ROW_CLASS = "py-4 first:pt-0 last:pb-0";

export function CardList({ children }: CardListProps) {
  return (
    <div className="surface-card">
      <div className="divide-y divide-hairline">{children}</div>
    </div>
  );
}

export function CardRow({ children, href }: CardRowProps) {
  if (href) {
    return (
      <Link href={href} className={`block transition-colors ${ROW_CLASS}`}>
        {children}
      </Link>
    );
  }

  return <div className={ROW_CLASS}>{children}</div>;
}
