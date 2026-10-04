"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  FileText,
  FolderGit2,
  GitBranch,
  ListChecks,
  Plus,
  RefreshCw,
  ShieldCheck,
  Workflow,
} from "lucide-react";
import { api, type Project } from "@/lib/api";

export function ProjectSelector({
  currentProjectId,
  onSelectProject,
  activeModule,
  onNewExtraction,
}: {
  currentProjectId: string | null;
  onSelectProject: (id: string) => void;
  activeModule: "requirements" | "artefacts" | "coverage" | "lifecycle" | "workflow";
  onNewExtraction?: () => void;
}) {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    api.projects()
      .then((list) => {
        if (!cancelled) setProjects(list);
      })
      .catch((err: unknown) => {
        console.error("Failed to load projects:", err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const selected = projects.find((p) => p.id === currentProjectId) ?? null;

  const navigateTo = (path: string) => {
    if (currentProjectId) {
      sessionStorage.setItem("nyaya_project_id", currentProjectId);
    }
    router.push(path);
  };

  return (
    <div className="rounded-xl border border-[var(--hairline)] bg-[var(--surface)] p-4 shadow-xs mb-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        {/* Project Selector Dropdown */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--surface-raised)] text-[var(--accent)]">
            <FolderGit2 size={16} />
          </div>

          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <span className="caption font-medium text-[var(--text-secondary)]">
                Selected Project:
              </span>
              <select
                value={currentProjectId ?? ""}
                onChange={(e) => {
                  const val = e.target.value;
                  if (val) {
                    sessionStorage.setItem("nyaya_project_id", val);
                    onSelectProject(val);
                  }
                }}
                className="rounded-lg border border-[var(--hairline)] bg-[var(--surface-raised)] px-2.5 py-1 text-xs font-semibold text-[var(--text)] focus:outline-none focus:ring-1 focus:ring-[var(--focus)] max-w-xs md:max-w-md truncate"
              >
                {projects.length === 0 && <option value="">No projects in database</option>}
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.requirement_count} req{p.requirement_count !== 1 ? "s" : ""} • {p.domain})
                  </option>
                ))}
              </select>

              {loading && <RefreshCw size={13} className="animate-spin text-[var(--text-tertiary)]" />}
            </div>

            {selected?.description && (
              <p className="caption text-[var(--text-tertiary)] max-w-xl truncate mt-0.5">
                {selected.description}
              </p>
            )}
          </div>
        </div>

        {/* Cross-Module Quick Jump Navigation Bar */}
        <div className="flex flex-wrap items-center gap-1.5 self-start lg:self-center">
          <button
            type="button"
            onClick={() => navigateTo("/requirements")}
            className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors ${
              activeModule === "requirements"
                ? "bg-[var(--accent)] text-white shadow-xs font-semibold"
                : "border border-[var(--hairline)] bg-[var(--surface-raised)] text-[var(--text-secondary)] hover:text-[var(--text)] hover:bg-[var(--surface)]"
            }`}
          >
            <ListChecks size={13} />
            Requirements
          </button>

          <button
            type="button"
            onClick={() => navigateTo("/artefacts")}
            className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors ${
              activeModule === "artefacts"
                ? "bg-[var(--accent)] text-white shadow-xs font-semibold"
                : "border border-[var(--hairline)] bg-[var(--surface-raised)] text-[var(--text-secondary)] hover:text-[var(--text)] hover:bg-[var(--surface)]"
            }`}
          >
            <FileText size={13} />
            SRS Artefacts
          </button>

          <button
            type="button"
            onClick={() => navigateTo("/coverage")}
            className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors ${
              activeModule === "coverage"
                ? "bg-[var(--accent)] text-white shadow-xs font-semibold"
                : "border border-[var(--hairline)] bg-[var(--surface-raised)] text-[var(--text-secondary)] hover:text-[var(--text)] hover:bg-[var(--surface)]"
            }`}
          >
            <ShieldCheck size={13} />
            Coverage
          </button>

          <button
            type="button"
            onClick={() => navigateTo("/lifecycle")}
            className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors ${
              activeModule === "lifecycle"
                ? "bg-[var(--accent)] text-white shadow-xs font-semibold"
                : "border border-[var(--hairline)] bg-[var(--surface-raised)] text-[var(--text-secondary)] hover:text-[var(--text)] hover:bg-[var(--surface)]"
            }`}
          >
            <GitBranch size={13} />
            SDLC Model
          </button>

          <button
            type="button"
            onClick={() => navigateTo("/workflow")}
            className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors ${
              activeModule === "workflow"
                ? "bg-[var(--accent)] text-white shadow-xs font-semibold"
                : "border border-[var(--hairline)] bg-[var(--surface-raised)] text-[var(--text-secondary)] hover:text-[var(--text)] hover:bg-[var(--surface)]"
            }`}
          >
            <Workflow size={13} />
            Workflow &amp; Gates
          </button>

          {onNewExtraction ? (
            <button
              type="button"
              onClick={onNewExtraction}
              className="inline-flex items-center gap-1 rounded-lg border border-[var(--hairline)] bg-[var(--surface-raised)] px-2 py-1.5 text-xs font-medium text-[var(--accent)] hover:bg-[var(--accent)]/10 transition-colors ml-1"
            >
              <Plus size={13} />
              New Brief
            </button>
          ) : (
            <Link
              href="/requirements?new=1"
              className="inline-flex items-center gap-1 rounded-lg border border-[var(--hairline)] bg-[var(--surface-raised)] px-2 py-1.5 text-xs font-medium text-[var(--accent)] hover:bg-[var(--accent)]/10 transition-colors ml-1"
            >
              <Plus size={13} />
              New Brief
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
