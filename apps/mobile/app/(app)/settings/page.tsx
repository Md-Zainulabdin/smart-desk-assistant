import type { Metadata } from "next";

import { SettingsView } from "@/features/settings/settings-view";
import { API_URL } from "@/lib/env";

const APP_VERSION = "0.1.0";

export const metadata: Metadata = {
  title: "Settings",
};

export default function SettingsPage() {
  return <SettingsView version={APP_VERSION} apiUrl={API_URL} />;
}
