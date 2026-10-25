import type { Metadata } from "next";

import { PagePlaceholder } from "@/components/shell/page-placeholder";

export const metadata: Metadata = {
  title: "Notes",
};

export default function NotesPage() {
  return (
    <PagePlaceholder
      title="Notes"
      description="Notes are added in stage 4. The backend endpoints do not exist yet."
    />
  );
}
