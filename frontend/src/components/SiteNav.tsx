import Link from "next/link";

const LINKS = [
  { href: "/", label: "대시보드" },
  { href: "/history", label: "추천 이력" },
  { href: "/settings", label: "정기 실행 설정" },
] as const;

export type NavHref = (typeof LINKS)[number]["href"];

/**
 * Every destination stays visible and the current one is marked, so the nav
 * keeps the same shape on all three pages instead of shifting as links drop out.
 */
export function SiteNav({ current }: { current: NavHref }) {
  return (
    <nav aria-label="주요 화면">
      <ul className="flex flex-wrap items-center gap-1">
        {LINKS.map((link) => {
          const isCurrent = link.href === current;
          return (
            <li key={link.href}>
              <Link
                href={link.href}
                aria-current={isCurrent ? "page" : undefined}
                className={`inline-block rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                  isCurrent
                    ? "bg-accent/15 text-accent-strong"
                    : "text-ink-muted hover:bg-surface-raised hover:text-ink"
                }`}
              >
                {link.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
