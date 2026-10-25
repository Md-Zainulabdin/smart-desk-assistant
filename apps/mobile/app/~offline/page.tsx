import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Offline",
};

export default function Offline() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-2 p-6 text-center">
      <h1 className="text-2xl font-semibold tracking-tight">You are offline</h1>
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        This screen is cached. Notes, reminders, and calendar need the server.
      </p>
    </main>
  );
}
