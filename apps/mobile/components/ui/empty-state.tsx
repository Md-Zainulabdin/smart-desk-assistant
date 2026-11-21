import type { ReactNode } from "react";

interface EmptyStateProps {
  message: string;
  action?: ReactNode;
}

export function EmptyState({ message, action }: EmptyStateProps) {
  return (
    <div className="surface-card flex flex-col items-center gap-3 py-8 text-center">
      <p className="text-[14px] text-zinc-500">{message}</p>
      {action}
    </div>
  );
}
