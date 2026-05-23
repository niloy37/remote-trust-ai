import Link from "next/link";
import { ShieldCheck } from "lucide-react";

const navItems = [
  { href: "/analyze", label: "Analyze" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/#pillars", label: "Scoring" }
];

export function Header() {
  return (
    <header className="sticky top-0 z-50 border-b border-line bg-ink/[0.78] backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
        <Link href="/" className="flex min-w-0 items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-mint/30 bg-mint/[0.12] text-mint">
            <ShieldCheck size={22} aria-hidden="true" />
          </span>
          <span className="truncate text-base font-bold text-white">RemoteTrust AI</span>
        </Link>
        <nav className="flex items-center gap-1 sm:gap-2">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-lg px-3 py-2 text-sm font-medium text-slate-300 transition hover:bg-white/[0.07] hover:text-white"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
