import type { ReactNode } from "react";

import { SectionHeader } from "@/components/ui/section-header";

interface SettingsGroupProps {
  title: string;
  children: ReactNode;
}

export function SettingsGroup({ title, children }: SettingsGroupProps) {
  return (
    <section>
      <SectionHeader title={title} />
      <div className="mt-4 flex flex-col gap-4">{children}</div>
    </section>
  );
}
