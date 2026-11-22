"use client";

import { useState } from "react";

import { CardList, CardRow } from "@/components/ui/card-list";
import { PageHeader } from "@/components/ui/page-header";
import { useSession } from "@/features/auth/session";

import { SettingsGroup } from "./settings-group";

interface SettingsViewProps {
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

export function SettingsView({ version, apiUrl }: SettingsViewProps) {
  const { user, signOut } = useSession();
  const [signingOut, setSigningOut] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSignOut() {
    setSigningOut(true);
    setError(null);
    try {
      await signOut();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not sign out.");
      setSigningOut(false);
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <PageHeader title="Settings" subtitle="Account and app" />

      <SettingsGroup title="Account">
        <CardList>
          <CardRow>
            <InfoRow label="Name" value={user.name ?? "Not set"} />
          </CardRow>
          <CardRow>
            <InfoRow label="Email" value={user.email} />
          </CardRow>
          <CardRow>
            <InfoRow label="Signed in with" value="Google" />
          </CardRow>
          <CardRow>
            <button
              type="button"
              onClick={() => void handleSignOut()}
              disabled={signingOut}
              className="block w-full text-center text-[14px] font-medium text-red-500 transition-colors hover:text-red-400 disabled:opacity-50"
            >
              {signingOut ? "Signing out…" : "Sign out"}
            </button>
          </CardRow>
        </CardList>
        {error && <p className="mt-3 text-[13px] text-red-500">{error}</p>}
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
