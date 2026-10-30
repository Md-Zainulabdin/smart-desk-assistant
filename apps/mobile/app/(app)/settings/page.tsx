import type { Metadata } from "next";

import { PageHeader } from "@/components/ui/page-header";
import { SettingsView } from "@/features/settings/settings-view";
import { API_URL } from "@/lib/env";
import {
  account,
  appInfo,
  assistantStatus,
  deviceInfo,
  notificationOptions,
} from "@/lib/mock-data";

export const metadata: Metadata = {
  title: "Settings",
};

export default function SettingsPage() {
  return (
    <div className="flex flex-col gap-8">
      <PageHeader title="Settings" subtitle="Preferences and device" />
      <SettingsView
        status={assistantStatus}
        device={deviceInfo}
        account={account}
        notificationOptions={notificationOptions}
        version={appInfo.version}
        apiUrl={API_URL}
      />
    </div>
  );
}
