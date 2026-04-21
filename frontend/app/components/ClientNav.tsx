"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";

const tabs = [
  { href: "/",          label: "홈",        icon: "◈" },
  { href: "/orders",    label: "주문",       icon: "◎" },
  { href: "/portfolio", label: "포트폴리오", icon: "◧" },
  { href: "/themes",    label: "테마",       icon: "◉" },
  { href: "/strategy",  label: "전략",       icon: "◆" },
];

export default function ClientNav() {
  const path = usePathname();
  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-50"
      style={{
        background: "rgba(8,8,14,0.92)",
        backdropFilter: "blur(20px)",
        borderTop: "1px solid rgba(255,255,255,0.06)",
      }}
    >
      <div className="max-w-2xl mx-auto flex items-end pb-safe">
        {tabs.map((t) => {
          const active = path === t.href || (t.href !== "/" && path.startsWith(t.href));
          return (
            <Link
              key={t.href}
              href={t.href}
              className="flex-1 flex flex-col items-center py-2 gap-0.5 relative"
              prefetch={true}
            >
              {active && (
                <motion.div
                  layoutId="nav-dot"
                  className="absolute top-0 left-1/2 -translate-x-1/2 w-8 h-0.5 rounded-full"
                  style={{ background: "linear-gradient(90deg, #A855F7, #EC4899)", boxShadow: "0 0 8px rgba(168,85,247,0.8)" }}
                  transition={{ type: "spring", stiffness: 400, damping: 30 }}
                />
              )}
              <span
                className={`text-lg leading-none transition-all duration-200 ${active ? "text-npurple" : "text-muted"}`}
                style={active ? { filter: "drop-shadow(0 0 6px rgba(168,85,247,0.6))" } : undefined}
              >
                {t.icon}
              </span>
              <span className={`text-[10px] font-medium transition-colors ${active ? "text-npurple" : "text-muted"}`}>
                {t.label}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
