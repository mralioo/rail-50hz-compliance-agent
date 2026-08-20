import { Link, useParams } from "react-router-dom";
import { AppShell } from "../components/layout/AppShell";
import { Topbar } from "../components/layout/Topbar";
import { SourceRow } from "../components/sources/SourceRow";
import { useJob } from "../queries/useJob";
import { useKnowledgeBases } from "../queries/useKnowledgeBases";

const EVAL_DOC =
  "https://github.com/mralioo/rail-50hz-compliance-agent/blob/main/docs/OPENSEARCH_NEO4J_EVALUATION.md";

/** Connect Sources — real mapping is narrower than the Anvil mockup's
 * generic multi-source connector list: the plan itself (already uploaded)
 * and the knowledge bases the Compliance Analyst / Plan Copilot actually
 * read from. Everything else in the mockup (graph DB, vector DB, SharePoint,
 * PLM) isn't live in this backend yet — shown disabled, not faked. */
export function JobSources() {
  const { jobId } = useParams<{ jobId: string }>();
  const { data: job } = useJob(jobId);
  const { data: knowledgeBases, isLoading, isError } = useKnowledgeBases();

  return (
    <AppShell>
      <div className="flex h-full flex-col">
        {job && <Topbar jobId={job.id} filename={job.filename} status={job.status} />}
        <div className="mx-auto w-full max-w-3xl px-6 py-10">
          <p className="text-xs font-medium uppercase tracking-widest text-ink-muted">
            {job?.filename}
          </p>
          <h1 className="mt-1 text-xl font-semibold text-ink-primary">
            Connect your data sources
          </h1>
          <p className="mt-1 max-w-xl text-sm text-ink-secondary">
            The plan the extraction agent reads from, and the regulation knowledge bases
            grounding the Compliance Analyst's findings and Plan Copilot's chat.
          </p>

          <div className="mt-6 overflow-hidden rounded-xl border border-line bg-navy-900">
            <SourceRow
              mono="PL"
              name={job?.filename ?? "Uploaded plan"}
              desc="DWG/DXF source — extraction, compliance, and Craftsman all read from this file"
              connected
            />
            {isLoading && (
              <p className="px-4 py-3 text-xs text-ink-muted">Loading knowledge bases…</p>
            )}
            {isError && (
              <p className="px-4 py-3 text-xs text-danger">Couldn't reach the backend.</p>
            )}
            {knowledgeBases?.map((kb) => (
              <SourceRow
                key={kb.id}
                mono="KB"
                name={kb.name}
                desc={`${kb.doc_count} regulation doc${kb.doc_count === 1 ? "" : "s"} — used by Compliance Analyst + Plan Copilot`}
                connected
              />
            ))}
            <SourceRow
              mono="GR"
              name="Neo4j — graph store"
              desc="Entity/relation graph for structural queries"
              comingSoon
              docHref={EVAL_DOC}
            />
            <SourceRow
              mono="VC"
              name="Vector store"
              desc="Embeddings for semantic retrieval"
              comingSoon
              docHref={EVAL_DOC}
            />
            <SourceRow
              mono="SP"
              name="SharePoint"
              desc="Legacy spec archive"
              comingSoon
            />
            <SourceRow
              mono="PL"
              name="Windchill PLM"
              desc="Change control + revisions"
              comingSoon
            />
          </div>

          {jobId && (
            <Link
              to={`/app/jobs/${jobId}/workflow`}
              className="mt-6 inline-block rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-navy-950 hover:bg-accent-dim"
            >
              Continue to workflow →
            </Link>
          )}
        </div>
      </div>
    </AppShell>
  );
}
