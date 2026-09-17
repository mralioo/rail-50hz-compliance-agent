import { Link } from "react-router-dom";

export function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-navy-950 text-center">
      <p className="text-sm text-ink-muted">Page not found.</p>
      <Link to="/" className="text-sm text-accent hover:underline">
        ← Back home
      </Link>
    </div>
  );
}
