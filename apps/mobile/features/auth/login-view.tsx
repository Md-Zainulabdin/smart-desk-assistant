import { GoogleIcon } from "@/components/ui/icons";
import { API_URL } from "@/lib/env";

export function LoginView() {
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-sm flex-col justify-center px-5 py-10">
      <p className="text-[13px] font-medium uppercase tracking-[0.14em] text-zinc-500">
        Smart Desk
      </p>

      <h1 className="mt-6 text-[26px] font-normal tracking-tight">Your desk, handled.</h1>
      <p className="mt-2 text-[15px] leading-relaxed text-zinc-500">
        Notes, reminders and meetings in one place. Sign in to keep your desk assistant in sync.
      </p>

      <div className="surface-card mt-8">
        {/* Full-page navigation, never a fetch: the session cookie must be first-party. */}
        <a
          href={`${API_URL}/auth/google`}
          className="flex h-12 items-center justify-center gap-2.5 rounded-xl border border-hairline bg-background text-[15px] font-medium transition-colors hover:bg-black/[.03] dark:hover:bg-white/[.05]"
        >
          <GoogleIcon />
          Continue with Google
        </a>
      </div>

      <p className="mt-4 text-center text-[13px] text-zinc-500">
        We only read your calendar and profile.
      </p>
    </main>
  );
}
