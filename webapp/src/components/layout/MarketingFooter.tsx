import { Logo } from "../shared/Logo";

export function MarketingFooter() {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-6 py-10 sm:flex-row sm:items-center sm:justify-between">
        <Logo className="h-6" />
        <p className="text-xs text-ink-muted">
          OmniDraft is an internal product mock built on the Rail50Hz.ai compliance-agent
          backend. GLEIS OS is its 50Hz railway electrical planning module.
        </p>
      </div>
    </footer>
  );
}
