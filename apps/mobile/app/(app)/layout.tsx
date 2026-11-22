import type { ReactNode } from "react";

import { AppShell } from "@/components/shell/app-shell";
import { SessionGate } from "@/features/auth/session";

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <SessionGate>
      <AppShell>{children}</AppShell>
    </SessionGate>
  );
}
