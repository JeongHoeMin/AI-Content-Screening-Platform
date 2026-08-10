import type { ReactNode } from "react";

import { SiteNav, type NavHref } from "@/components/SiteNav";

/**
 * The page frame every screen shares: a sticky bar that owns the navigation,
 * and a single centered column that owns all page padding and section spacing.
 */
export function AppShell({
  current,
  title,
  description,
  actions,
  children,
}: {
  current: NavHref;
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-line bg-canvas/85 backdrop-blur">
        <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-3 sm:px-6 lg:px-8">
          <span className="text-sm font-semibold tracking-tight text-ink">
            AI 콘텐츠 스크리닝
          </span>
          <SiteNav current={current} />
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
          <div className="min-w-0">
            <h1 className="text-2xl font-bold tracking-tight text-ink sm:text-3xl">
              {title}
            </h1>
            {description && (
              <p className="mt-2 max-w-3xl text-sm leading-relaxed text-ink-muted">
                {description}
              </p>
            )}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>

        <div className="space-y-5">{children}</div>
      </main>
    </div>
  );
}
