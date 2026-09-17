import { Link } from "react-router-dom";
import { Logo } from "../shared/Logo";

export function MarketingNav() {
  return (
    <nav className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
      <Logo className="h-7" />
      <div className="flex items-center gap-6 text-sm text-ink-secondary">
        <a href="#features" className="transition-colors hover:text-ink-primary">
          Features
        </a>
        <a href="#agents" className="transition-colors hover:text-ink-primary">
          Agents
        </a>
        <Link
          to="/app/dashboard"
          className="rounded-md border border-accent/40 bg-accent/10 px-4 py-2 font-medium text-accent transition-colors hover:bg-accent/20"
        >
          Open Demo Workspace
        </Link>
      </div>
    </nav>
  );
}
