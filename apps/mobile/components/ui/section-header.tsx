import Link from "next/link";

interface SectionHeaderProps {
  title: string;
  href?: string;
}

export function SectionHeader({ title, href }: SectionHeaderProps) {
  return (
    <div className="flex items-baseline justify-between">
      <h2 className="text-[15px] font-medium tracking-tight text-zinc-500">{title}</h2>
      {href && (
        <Link
          href={href}
          className="text-[13px] text-zinc-500 transition-colors hover:text-foreground"
        >
          View all
        </Link>
      )}
    </div>
  );
}
