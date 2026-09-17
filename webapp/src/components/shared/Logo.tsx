interface LogoProps {
  variant?: "lockup" | "mark";
  className?: string;
}

/** Renders the OmniDraft mark or the full OmniDraft · GLEIS OS lockup. */
export function Logo({ variant = "lockup", className }: LogoProps) {
  if (variant === "mark") {
    return (
      <img
        src="/brand/omnidraft-mark.svg"
        alt="OmniDraft"
        className={className ?? "h-8 w-8"}
      />
    );
  }
  return (
    <img
      src="/brand/omnidraft-lockup.svg"
      alt="OmniDraft · GLEIS OS"
      className={className ?? "h-8"}
    />
  );
}
