import Link from "next/link";

const LINKS = [
  { href: "/", label: "대시보드" },
  { href: "/history", label: "추천 이력" },
  { href: "/settings", label: "정기 실행 설정" },
] as const;

export function SiteNav({ current }: { current: (typeof LINKS)[number]["href"] }) {
  return (
    <nav>
      {LINKS.filter((link) => link.href !== current).map((link) => (
        <Link key={link.href} href={link.href}>
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
