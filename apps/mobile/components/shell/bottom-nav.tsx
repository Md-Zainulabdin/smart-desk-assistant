"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Home" },
  { href: "/notes", label: "Notes" },
  { href: "/reminders", label: "Reminders" },
  { href: "/calendar", label: "Calendar" },
  { href: "/device", label: "Device" },
] as const;

function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Primary"
      className="sticky bottom-0 border-t border-black/[.08] bg-background/80 backdrop-blur dark:border-white/[.145]"
    >
      <ul className="mx-auto flex w-full max-w-3xl">
        {NAV_ITEMS.map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <li key={item.href} className="flex-1">
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`flex h-14 items-center justify-center text-xs transition-colors ${
                  active
                    ? "font-semibold text-foreground"
                    : "font-medium text-zinc-500 hover:text-foreground dark:text-zinc-400"
                }`}
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
