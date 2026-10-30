import type { AssistantStatus } from "@/lib/types";

interface AssistantStatusCardProps {
  status: AssistantStatus;
}

export function AssistantStatusCard({ status }: AssistantStatusCardProps) {
  return (
    <div className="surface-card">
      <div className="flex items-center gap-2.5">
        <span
          className={`inline-block h-[7px] w-[7px] rounded-full ${
            status.isOnline ? "bg-emerald-500" : "bg-zinc-500"
          }`}
          aria-hidden="true"
        />
        <span className="text-[14px] font-medium tracking-tight">
          Desk assistant {status.isOnline ? "online" : "offline"}
        </span>
      </div>

      <p className="mt-2.5 text-[13px] text-zinc-500">{status.statusLabel}</p>

      <p className="mt-3.5 text-[13px] leading-relaxed text-zinc-500">{status.explanation}</p>
    </div>
  );
}
