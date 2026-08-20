type BadgeTone = "built" | "coming-soon" | "partial";

const TONE_CLASSES: Record<BadgeTone, string> = {
  built: "border-accent/40 bg-accent/10 text-accent",
  "coming-soon": "border-amber/40 bg-amber/10 text-amber",
  partial: "border-ink-secondary/40 bg-ink-secondary/10 text-ink-secondary",
};

const TONE_LABEL: Record<BadgeTone, string> = {
  built: "Built",
  "coming-soon": "Coming Soon",
  partial: "Partial",
};

export function BadgePill({ tone, label }: { tone: BadgeTone; label?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium tracking-wide ${TONE_CLASSES[tone]}`}
    >
      {label ?? TONE_LABEL[tone]}
    </span>
  );
}
