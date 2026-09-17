import type { JobStatus } from "../../api/types";

const STEPS: JobStatus[] = ["queued", "converting", "extracting", "analyzing", "ready"];

export function JobStatusStepper({ status }: { status: JobStatus }) {
  const currentIndex = STEPS.indexOf(status);

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-6">
      <div className="flex items-center gap-2">
        {STEPS.map((step, index) => {
          const isDone = currentIndex > index;
          const isActive = currentIndex === index;
          return (
            <div key={step} className="flex items-center gap-2">
              <div
                className={`flex h-8 w-8 items-center justify-center rounded-full border text-xs ${
                  isDone
                    ? "border-accent bg-accent/20 text-accent"
                    : isActive
                      ? "animate-pulse border-accent text-accent"
                      : "border-line-light text-ink-muted"
                }`}
              >
                {index + 1}
              </div>
              {index < STEPS.length - 1 && (
                <div className={`h-px w-8 ${isDone ? "bg-accent/50" : "bg-line-light"}`} />
              )}
            </div>
          );
        })}
      </div>
      <p className="text-sm capitalize text-ink-secondary">
        {status === "queued" ? "Queued for processing…" : `${status}…`}
      </p>
    </div>
  );
}
