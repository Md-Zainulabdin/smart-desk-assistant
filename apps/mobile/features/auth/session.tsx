"use client";

import type { ReactNode } from "react";
import { createContext, useCallback, useContext, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { User } from "@desk/shared-types";

import { ApiError, getCurrentUser, logout as apiLogout } from "@/lib/api";

interface SessionValue {
  user: User;
  signOut: () => Promise<void>;
}

const SessionContext = createContext<SessionValue | null>(null);

async function clearServiceWorkerCaches(): Promise<void> {
  if (typeof caches === "undefined") return;
  const keys = await caches.keys();
  await Promise.all(keys.map((key) => caches.delete(key)));
}

function RedirectToLogin() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/login");
  }, [router]);

  return <p className="px-5 py-10 text-[14px] text-zinc-500">Redirecting to sign in…</p>;
}

/**
 * Keep authenticated screens behind a real session check. The API cookie is
 * HttpOnly, so the browser is the only place that can confirm it.
 */
export function SessionGate({ children }: { children: ReactNode }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const session = useQuery({
    queryKey: ["session"],
    queryFn: getCurrentUser,
    retry: false,
  });

  const signOut = useCallback(async () => {
    try {
      await apiLogout();
    } catch (cause) {
      // An expired session still needs local cleanup and a trip to /login.
      if (!(cause instanceof ApiError && cause.status === 401)) throw cause;
    }
    await clearServiceWorkerCaches();
    queryClient.clear();
    router.replace("/login");
  }, [queryClient, router]);
  const value = useMemo(
    () => (session.data ? { user: session.data, signOut } : null),
    [session.data, signOut],
  );

  if (session.isPending) {
    return <p className="px-5 py-10 text-[14px] text-zinc-500">Checking your session…</p>;
  }

  if (session.error instanceof ApiError && session.error.status === 401) {
    return <RedirectToLogin />;
  }

  if (session.error) {
    return (
      <div className="flex flex-col items-start gap-3 px-5 py-10">
        <p className="text-[14px] text-zinc-500">{session.error.message}</p>
        <button
          type="button"
          onClick={() => void session.refetch()}
          className="rounded-full bg-foreground px-5 py-2 text-sm font-medium text-background"
        >
          Try again
        </button>
      </div>
    );
  }

  if (!value) return null;

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const context = useContext(SessionContext);
  if (context === null) {
    throw new Error("useSession must be used inside SessionGate.");
  }
  return context;
}
