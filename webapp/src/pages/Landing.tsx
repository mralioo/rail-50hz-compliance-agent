import { Link } from "react-router-dom";
import { MarketingNav } from "../components/layout/MarketingNav";
import { MarketingFooter } from "../components/layout/MarketingFooter";
import { BadgePill } from "../components/shared/BadgePill";
import { FEATURE_MATRIX } from "../content/featureMatrix";

const PROBLEMS = [
  {
    title: "Manual Ril/VDE cross-checking",
    description:
      "Every 50Hz plan gets checked against bending-radius, pulling-force, and clearance rules by hand — hours per drawing, easy to miss a clause.",
  },
  {
    title: "Tribal-knowledge findings",
    description:
      "Which codes are still active, which were superseded, and why — lives in a senior engineer's head, not in a system a whole team can query.",
  },
  {
    title: "Slow plan review cycles",
    description:
      "Finding \"where is the Schalthaus?\" or verifying one cable run means opening the DWG in desktop CAD and hunting layer by layer.",
  },
];

const PROOF_BADGES = [
  "5 built agents",
  "Ril/VDE-grounded RAG",
  "Live on real DWG/DXF uploads",
];

const ROADMAP_INTEGRATIONS = ["SharePoint", "Autodesk Construction Cloud", "Procore"];

export function Landing() {
  return (
    <div className="min-h-screen bg-navy-950">
      <MarketingNav />

      {/* Hero */}
      <section className="mx-auto max-w-4xl px-6 pb-20 pt-16 text-center">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-accent">
          OmniDraft · GLEIS OS
        </p>
        <h1 className="mt-4 text-4xl font-semibold leading-tight text-ink-primary sm:text-5xl">
          50Hz railway electrical compliance,
          <br />
          without the week of manual cross-checking.
        </h1>
        <p className="mx-auto mt-5 max-w-xl text-base text-ink-secondary">
          OmniDraft is the AI drafting &amp; compliance platform for AEC firms. GLEIS OS is its
          railway electrical planning module — upload a plan, get grounded findings, chat with a
          copilot that cites its sources.
        </p>
        <div className="mt-8 flex items-center justify-center gap-4">
          <Link
            to="/app/dashboard"
            className="rounded-md bg-accent px-6 py-3 text-sm font-semibold text-navy-950 transition-opacity hover:opacity-90"
          >
            Open Demo Workspace
          </Link>
          <a
            href="#features"
            className="rounded-md border border-line-light px-6 py-3 text-sm font-medium text-ink-secondary transition-colors hover:text-ink-primary"
          >
            See how it works
          </a>
        </div>
        <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
          {PROOF_BADGES.map((badge) => (
            <span
              key={badge}
              className="rounded-full border border-line-light px-3 py-1 text-xs text-ink-secondary"
            >
              {badge}
            </span>
          ))}
        </div>
      </section>

      {/* Problem */}
      <section className="border-t border-line py-16">
        <div className="mx-auto max-w-6xl px-6">
          <p className="text-xs font-medium uppercase tracking-widest text-ink-muted">
            Why this exists
          </p>
          <h2 className="mt-2 text-2xl font-semibold text-ink-primary">
            Built for the planner buried in Ril/VDE cross-checks.
          </h2>
          <div className="mt-8 grid gap-6 sm:grid-cols-3">
            {PROBLEMS.map((problem) => (
              <div key={problem.title} className="rounded-lg border border-line bg-navy-900 p-5">
                <p className="text-sm font-semibold text-ink-primary">{problem.title}</p>
                <p className="mt-2 text-xs leading-relaxed text-ink-secondary">
                  {problem.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Feature grid */}
      <section id="features" className="border-t border-line py-16">
        <div className="mx-auto max-w-6xl px-6">
          <p className="text-xs font-medium uppercase tracking-widest text-ink-muted">
            Platform
          </p>
          <h2 className="mt-2 text-2xl font-semibold text-ink-primary">
            Everything on the roadmap — honestly labeled.
          </h2>
          <p className="mt-2 max-w-2xl text-sm text-ink-secondary">
            Every capability below is either shipped and running against the demo workspace, or
            clearly marked Coming Soon — nothing here is faked.
          </p>
          <div id="agents" className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURE_MATRIX.map((feature) => (
              <div key={feature.title} className="rounded-lg border border-line bg-navy-900 p-5">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm font-medium text-ink-primary">{feature.title}</p>
                  <BadgePill tone={feature.tone} />
                </div>
                <p className="mt-2 text-xs leading-relaxed text-ink-secondary">
                  {feature.description}
                </p>
                {feature.roadmapSlug && (
                  <Link
                    to={`/app/roadmap/${feature.roadmapSlug}`}
                    className="mt-3 inline-block text-xs text-accent hover:underline"
                  >
                    Roadmap details →
                  </Link>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Roadmap integrations */}
      <section className="border-t border-line py-16">
        <div className="mx-auto max-w-6xl px-6">
          <p className="text-xs font-medium uppercase tracking-widest text-ink-muted">
            Roadmap integrations
          </p>
          <p className="mt-2 max-w-xl text-sm text-ink-secondary">
            Planned connectors into the systems firms already use — none of these exist yet.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            {ROADMAP_INTEGRATIONS.map((name) => (
              <span
                key={name}
                className="rounded-md border border-dashed border-line-light px-4 py-2 text-xs text-ink-muted"
              >
                {name} — planned
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="border-t border-line py-16 text-center">
        <h2 className="text-2xl font-semibold text-ink-primary">
          Upload a real plan. See it working, not a slide deck.
        </h2>
        <Link
          to="/app/dashboard"
          className="mt-6 inline-block rounded-md bg-accent px-6 py-3 text-sm font-semibold text-navy-950 transition-opacity hover:opacity-90"
        >
          Open Demo Workspace
        </Link>
      </section>

      <MarketingFooter />
    </div>
  );
}
