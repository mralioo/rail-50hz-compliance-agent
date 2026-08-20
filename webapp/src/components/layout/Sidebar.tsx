import { NavLink } from "react-router-dom";
import { Logo } from "../shared/Logo";

const REAL_NAV = [
  { to: "/app/dashboard", label: "Projects" },
  { to: "/app/viewer", label: "DWG Viewer" },
  { to: "/app/settings", label: "Settings" },
];

const DEBUG_NAV = [{ to: "/app/debug", label: "Debug Console" }];

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `block rounded-md px-3 py-2 text-sm transition-colors ${
    isActive
      ? "bg-accent/10 text-accent"
      : "text-ink-secondary hover:bg-navy-800 hover:text-ink-primary"
  }`;

export function Sidebar() {
  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r border-line bg-navy-900">
      <div className="border-b border-line px-4 py-4">
        <Logo className="h-7" />
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4">
        <p className="px-3 pb-2 text-xs font-medium uppercase tracking-wider text-ink-muted">
          Workspace
        </p>
        <div className="space-y-1">
          {REAL_NAV.map((item) => (
            <NavLink key={item.to} to={item.to} className={navLinkClass}>
              {item.label}
            </NavLink>
          ))}
        </div>

        <p className="mt-6 px-3 pb-2 text-xs font-medium uppercase tracking-wider text-ink-muted">
          Dev
        </p>
        <div className="space-y-1">
          {DEBUG_NAV.map((item) => (
            <NavLink key={item.to} to={item.to} className={navLinkClass}>
              {item.label}
            </NavLink>
          ))}
        </div>
      </nav>

      <div className="border-t border-line px-4 py-3 text-xs text-ink-muted">Demo Workspace</div>
    </aside>
  );
}
