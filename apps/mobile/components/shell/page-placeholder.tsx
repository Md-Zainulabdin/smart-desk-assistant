export function PagePlaceholder({ title, description }: { title: string; description: string }) {
  return (
    <section className="flex flex-1 flex-col items-center justify-center gap-2 text-center">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      <p className="max-w-sm text-sm text-zinc-600 dark:text-zinc-400">{description}</p>
    </section>
  );
}
