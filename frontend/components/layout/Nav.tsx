"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

const tabs = [
  { href: "/", label: "대시보드", icon: "⬛" },
  { href: "/themes", label: "테마", icon: "📊" },
  { href: "/portfolio", label: "포트폴리오", icon: "🗂" },
  { href: "/orders", label: "주문", icon: "✅" },
  { href: "/strategy", label: "전략", icon: "📈" },
];

export default function Nav() {
  const path = usePathname();
  return (
    <nav className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 pb-safe">
      <div className="max-w-2xl mx-auto flex">
        {tabs.map((t) => {
          const active = path === t.href || (t.href !== "/" && path.startsWith(t.href));
          return (
            <Link
              key={t.href}
              href={t.href}
              className={clsx(
                "flex-1 flex flex-col items-center py-2 text-xs transition-colors",
                active ? "text-primary font-semibold" : "text-muted"
              )}
            >
              <span className="text-lg leading-none mb-0.5">{t.icon}</span>
              {t.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
