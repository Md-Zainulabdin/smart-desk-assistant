import type { ReactNode } from "react";

interface IconButtonProps {
  label: string;
  onClick?: () => void;
  pressed?: boolean;
  disabled?: boolean;
  children: ReactNode;
}

export function IconButton({ label, onClick, pressed, disabled, children }: IconButtonProps) {
  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={pressed}
      disabled={disabled}
      title={disabled ? "Coming soon" : undefined}
      onClick={onClick}
      className="rounded-lg p-1.5 text-zinc-500 transition-colors hover:bg-black/[.05] hover:text-zinc-700 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-zinc-500 dark:hover:bg-white/[.06] dark:hover:text-zinc-300 dark:disabled:hover:bg-transparent dark:disabled:hover:text-zinc-500"
    >
      {children}
    </button>
  );
}
