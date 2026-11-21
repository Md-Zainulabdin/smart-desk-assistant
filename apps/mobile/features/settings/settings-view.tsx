"use client";

import { useState } from "react";

import { AssistantStatusCard } from "@/components/ui/assistant-status-card";
import { CardList, CardRow } from "@/components/ui/card-list";
import { CheckIcon } from "@/components/ui/icons";
import type {
  Account,
  AssistantStatus,
  DeviceInfo,
  NotificationMode,
  NotificationOption,
} from "@/lib/types";

import { SettingsGroup } from "./settings-group";

interface SettingsViewProps {
  status: AssistantStatus;
  device: DeviceInfo;
  account: Account;
  notificationOptions: NotificationOption[];
  version: string;
  apiUrl: string;
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <span className="text-[14px]">{label}</span>
      <span className="truncate text-right text-[13px] text-zinc-500">{value}</span>
    </div>
  );
}

export function SettingsView({
  status,
  device,
  account,
  notificationOptions,
  version,
  apiUrl,
}: SettingsViewProps) {
  const [mode, setMode] = useState<NotificationMode>(status.notificationMode);

  return (
    <div className="flex flex-col gap-8">
      <SettingsGroup title="Assistant">
        <AssistantStatusCard status={status} />
        <CardList>
          <CardRow>
            <InfoRow label="Desk connection" value={device.isOnline ? "Online" : "Offline"} />
          </CardRow>
          <CardRow>
            <InfoRow label="Last sync" value={device.lastSyncLabel} />
          </CardRow>
        </CardList>
      </SettingsGroup>

      <SettingsGroup title="Notifications">
        <div role="radiogroup" aria-label="Notification mode">
          <CardList>
            {notificationOptions.map((option) => {
              const active = option.mode === mode;
              return (
                <CardRow key={option.mode}>
                  <label className="flex cursor-pointer items-start justify-between gap-4 rounded-lg has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-foreground">
                    <input
                      type="radio"
                      name="notification-mode"
                      value={option.mode}
                      checked={active}
                      onChange={() => setMode(option.mode)}
                      className="sr-only"
                    />
                    <span className="min-w-0">
                      <span className="block text-[14px] font-medium tracking-tight">
                        {option.label}
                      </span>
                      <span className="mt-1 block text-[13px] leading-snug text-zinc-500">
                        {option.description}
                      </span>
                    </span>
                    {active && <CheckIcon className="mt-0.5 shrink-0" />}
                  </label>
                </CardRow>
              );
            })}
          </CardList>
        </div>
      </SettingsGroup>

      <SettingsGroup title="Account">
        <CardList>
          <CardRow>
            <InfoRow label="Name" value={account.name} />
          </CardRow>
          <CardRow>
            <InfoRow label="Email" value={account.email} />
          </CardRow>
          <CardRow>
            <InfoRow label="Signed in with" value={account.provider} />
          </CardRow>
          <CardRow>
            <a
              href="/login"
              className="block text-center text-[14px] font-medium text-red-500 transition-colors hover:text-red-400"
            >
              Sign out
            </a>
          </CardRow>
        </CardList>
      </SettingsGroup>

      <SettingsGroup title="About">
        <CardList>
          <CardRow>
            <InfoRow label="Version" value={version} />
          </CardRow>
          <CardRow>
            <InfoRow label="Backend" value={apiUrl} />
          </CardRow>
          <CardRow>
            <p className="text-[13px] leading-relaxed text-zinc-500">
              Install this app from the browser menu to use it like a native app.
            </p>
          </CardRow>
        </CardList>
      </SettingsGroup>
    </div>
  );
}
