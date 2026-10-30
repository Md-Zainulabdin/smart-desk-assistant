"use client";

import { ApiError } from "@/lib/api";

export function ErrorState({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const message = error instanceof ApiError ? error.message : "Something went wrong.";

  return (
    <section className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
      <h2 className="text-lg font-semibold tracking-tight">That did not work</h2>
      <p className="max-w-sm text-sm text-zinc-600 dark:text-zinc-400">{message}</p>
      {/* The code is for debugging; users only need the message. */}
      {process.env.NODE_ENV === "development" && error instanceof ApiError && (
        <p className="font-mono text-xs text-zinc-500">{error.code}</p>
      )}
      <button
        type="button"
        onClick={reset}
        className="mt-1 rounded-full bg-foreground px-5 py-2 text-sm font-medium text-background"
      >
        Try again
      </button>
    </section>
  );
}
