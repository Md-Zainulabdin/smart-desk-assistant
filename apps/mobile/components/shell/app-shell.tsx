import type { ReactNode } from "react";

import { BottomNav } from "./bottom-nav";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-full flex-1 flex-col">
      <header className="sticky top-0 z-10 border-b border-black/[.08] bg-background/80 backdrop-blur dark:border-white/[.145]">
        <div className="mx-auto flex w-full max-w-3xl items-center px-4 py-3">
          <span className="text-sm font-semibold tracking-tight">Smart Desk</span>
        </div>
      </header>
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 py-6">{children}</main>
      <BottomNav />
    </div>
  );
}
