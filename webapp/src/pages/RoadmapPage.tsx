import { useParams } from "react-router-dom";
import { AppShell } from "../components/layout/AppShell";
import { ComingSoon } from "../components/shared/ComingSoon";
import { getRoadmapEntry } from "../content/roadmap";
import { NotFound } from "./NotFound";

export function RoadmapPage() {
  const { slug } = useParams<{ slug: string }>();

  const entry = getRoadmapEntry(slug);
  if (!entry) return <NotFound />;

  return (
    <AppShell>
      <ComingSoon entry={entry} />
    </AppShell>
  );
}
