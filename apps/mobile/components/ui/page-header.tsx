interface PageHeaderProps {
  title: string;
  subtitle?: string;
}

export function PageHeader({ title, subtitle }: PageHeaderProps) {
  return (
    <header>
      <h1 className="text-[26px] font-normal tracking-tight">{title}</h1>
      {subtitle && <p className="mt-1.5 text-[15px] text-zinc-500">{subtitle}</p>}
    </header>
  );
}
