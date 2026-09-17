import { useRef, useState } from "react";
import type { DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useCreateJob } from "../../queries/useJobs";

const ACCEPTED_EXTENSIONS = [".dwg", ".dxf"];

function isAccepted(file: File): boolean {
  const lower = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

export function UploadDropzone() {
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const createJob = useCreateJob();
  const navigate = useNavigate();

  async function handleFile(file: File) {
    setError(null);
    if (!isAccepted(file)) {
      setError("Upload a .dwg or .dxf file.");
      return;
    }
    try {
      const job = await createJob.mutateAsync(file);
      navigate(`/app/jobs/${job.id}/workflow`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    }
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    const file = event.dataTransfer.files[0];
    if (file) void handleFile(file);
  }

  return (
    <div>
      <div
        onDragOver={(event) => {
          event.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") inputRef.current?.click();
        }}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors ${
          isDragging
            ? "border-accent bg-accent/5"
            : "border-line-light bg-navy-900 hover:border-accent/40"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".dwg,.dxf"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void handleFile(file);
            event.target.value = "";
          }}
        />
        <p className="text-sm font-medium text-ink-primary">
          {createJob.isPending ? "Uploading…" : "Drop a .dwg or .dxf plan here"}
        </p>
        <p className="mt-1 text-xs text-ink-muted">or click to browse</p>
      </div>
      {error && <p className="mt-2 text-xs text-danger">{error}</p>}
    </div>
  );
}
