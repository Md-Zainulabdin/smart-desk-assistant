"use client";

interface LoadStateProps {
  label?: string;
}

export function LoadingState({ label = "Loading…" }: LoadStateProps) {
  return <p className="text-[14px] text-zinc-500">{label}</p>;
}

export function LoadError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="surface-card flex flex-col items-start gap-3">
      <p className="text-[14px] text-zinc-500">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="rounded-full bg-foreground px-5 py-2 text-sm font-medium text-background"
      >
        Try again
      </button>
    </div>
  );
}
