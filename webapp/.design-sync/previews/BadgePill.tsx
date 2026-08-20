import { BadgePill } from "../../src/components/shared/BadgePill";

export function Built() {
  return <BadgePill tone="built" />;
}

export function ComingSoon() {
  return <BadgePill tone="coming-soon" />;
}

export function Partial() {
  return <BadgePill tone="partial" />;
}

export function CustomLabel() {
  return <BadgePill tone="built" label="Live" />;
}
