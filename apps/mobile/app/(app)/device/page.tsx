import type { Metadata } from "next";

import { PagePlaceholder } from "@/components/shell/page-placeholder";

export const metadata: Metadata = {
  title: "Device",
};

export default function DevicePage() {
  return (
    <PagePlaceholder title="Device" description="Device and context status are added in stage 7." />
  );
}
