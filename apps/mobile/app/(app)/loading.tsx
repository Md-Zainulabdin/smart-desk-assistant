export default function Loading() {
  return (
    <div className="flex flex-1 flex-col gap-3" aria-busy="true">
      <div className="h-7 w-40 animate-pulse rounded bg-black/[.06] dark:bg-white/[.08]" />
      <div className="h-4 w-full animate-pulse rounded bg-black/[.06] dark:bg-white/[.08]" />
      <div className="h-4 w-3/4 animate-pulse rounded bg-black/[.06] dark:bg-white/[.08]" />
      <span className="sr-only">Loading</span>
    </div>
  );
}
