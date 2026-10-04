"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  FolderGit2,
  GitBranch,
  ListChecks,
  Plus,
  Search,
  Trash2,
  Workflow,
  RefreshCw,
} from "lucide-react";
import { Block, ModuleShell } from "@/components/chrome/ModuleShell";
import { Badge, Button, Empty, Failure } from "@/components/ui";
import { api, type Project, type SDLCFromBrief } from "@/lib/api";
import { useJobs } from "@/components/chrome/Jobs";

export default function HistoryPage() {
  const { setResult } = useJobs();
  const router = useRouter();

  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const loadProjects = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await api.projects();
      setProjects(list);
    } catch (err: unknown) {
      setError((err as Error)?.message || "Failed to load projects");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    api.projects()
      .then((list) => {
        if (!cancelled) {
          setProjects(list);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError((err as Error)?.message || "Failed to load projects");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const filteredProjects = useMemo(() => {
    if (!search.trim()) return projects;
    const q = search.toLowerCase();
    return projects.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.domain.toLowerCase().includes(q) ||
        (p.description && p.description.toLowerCase().includes(q))
    );
  }, [projects, search]);

  const handleOpenRequirements = (project: Project) => {
    sessionStorage.setItem("nyaya_project_id", project.id);
    router.push("/requirements");
  };

  const handleOpenWorkflow = (project: Project) => {
    sessionStorage.setItem("nyaya_project_id", project.id);
    router.push("/workflow");
  };

  const handleOpenLifecycle = async (project: Project) => {
    setActionLoadingId(project.id);
    setError(null);
    try {
      const sdlc = await api.projectSdlc(project.id);

      setResult(
        "lifecycle",
        project.description || project.name,
        sdlc,
        (result: SDLCFromBrief) => {
          const title =
            result.workflow.phases.length > 0
              ? `${result.recommendation.recommended} (${result.workflow.phases.length} phases)`
              : result.recommendation.recommended;
          return {
            label: title,
            detail: `${result.requirements_extracted} requirements`,
          };
        }
      );

      router.push("/lifecycle");
    } catch (err: unknown) {
      setError((err as Error)?.message || "Failed to load SDLC assessment for this project");
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleDelete = async (e: React.MouseEvent, projectId: string) => {
    e.stopPropagation();
    setActionLoadingId(projectId);
    setError(null);
    try {
      await api.deleteProject(projectId);
      setProjects((prev) => prev.filter((p) => p.id !== projectId));
      setConfirmDeleteId(null);
    } catch (err: unknown) {
      setError((err as Error)?.message || "Failed to delete project");
    } finally {
      setActionLoadingId(null);
    }
  };

  return (
    <ModuleShell
      pathname="/history"
      eyebrow="History & Engagements"
      title="Project Repository & Extraction History"
      lede="Browse, reload, and manage all requirements engineering engagements and multi-agent workflow checkpoints."
    >
      {/* Search and Action Bar */}
      <Block>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative flex-1 max-w-md">
            <Search
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)]"
            />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search engagements by name or domain..."
              className="w-full rounded-xl border border-[var(--hairline)] bg-[var(--surface)] py-2 pl-9 pr-4 text-sm text-[var(--text)] placeholder-[var(--text-tertiary)] focus:outline-none focus:ring-1 focus:ring-[var(--focus)]"
            />
          </div>

          <div className="flex items-center gap-2">
            <Button variant="quiet" onClick={() => void loadProjects()} disabled={loading}>
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
              Refresh
            </Button>
            <Button variant="primary" onClick={() => router.push("/requirements")}>
              <Plus size={14} />
              New Extraction
            </Button>
          </div>
        </div>
      </Block>

      {error && <Failure message={error} />}

      <Block>
        <div className="flex flex-col gap-4">
          {loading && (
            <div className="rounded-xl border border-[var(--hairline)] bg-[var(--surface)] p-8 text-center text-sm text-[var(--text-tertiary)]">
              Loading engagements repository...
            </div>
          )}

          {!loading && projects.length === 0 && (
            <Empty>
              No project extractions found in the database. Navigate to the Requirements module to extract your first regulatory brief!
            </Empty>
          )}

          {!loading && projects.length > 0 && filteredProjects.length === 0 && (
            <div className="rounded-xl border border-[var(--hairline)] bg-[var(--surface)] p-6 text-center text-sm text-[var(--text-secondary)]">
              No projects match &ldquo;{search}&rdquo;.
            </div>
          )}

          {!loading &&
            filteredProjects.map((p) => {
              const isActionBusy = actionLoadingId === p.id;
              const isConfirmingDelete = confirmDeleteId === p.id;

              return (
                <div
                  key={p.id}
                  className="rounded-xl border border-[var(--hairline)] bg-[var(--surface)] p-5 transition-all hover:border-[var(--text-tertiary)]"
                >
                  <div className="flex flex-col justify-between gap-4 md:flex-row md:items-start">
                    {/* Project Header Info */}
                    <div className="flex items-start gap-3.5">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[var(--surface-raised)] text-[var(--text-secondary)]">
                        <FolderGit2 size={20} />
                      </div>

                      <div className="flex flex-col gap-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="text-base font-semibold text-[var(--text)]">
                            {p.name}
                          </h3>
                          <Badge tone="var(--accent)">
                            {p.requirement_count} requirement{p.requirement_count !== 1 ? "s" : ""}
                          </Badge>
                          <Badge tone="var(--clause)">{p.domain}</Badge>
                        </div>

                        {p.description && (
                          <p className="caption max-w-2xl text-[var(--text-secondary)] line-clamp-2">
                            {p.description}
                          </p>
                        )}

                        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-[var(--text-tertiary)]">
                          <span>Created {new Date(p.created_at).toLocaleString()}</span>
                          {p.jurisdictions && p.jurisdictions.length > 0 && (
                            <span>• Jurisdictions: {p.jurisdictions.join(", ")}</span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Action buttons */}
                    <div className="flex flex-wrap items-center gap-2 self-end md:self-center">
                      <button
                        type="button"
                        onClick={() => handleOpenRequirements(p)}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--hairline)] bg-[var(--surface-raised)] px-3 py-1.5 text-xs font-medium text-[var(--text)] hover:bg-[var(--surface)] hover:border-[var(--text-secondary)] transition-colors"
                      >
                        <ListChecks size={13} />
                        Requirements
                      </button>

                      <button
                        type="button"
                        onClick={() => handleOpenWorkflow(p)}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--hairline)] bg-[var(--surface-raised)] px-3 py-1.5 text-xs font-medium text-[var(--text)] hover:bg-[var(--surface)] hover:border-[var(--text-secondary)] transition-colors"
                      >
                        <Workflow size={13} />
                        Workflow &amp; Gates
                      </button>

                      <button
                        type="button"
                        onClick={() => handleOpenLifecycle(p)}
                        disabled={isActionBusy}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--accent)]/40 bg-[var(--accent)]/10 px-3 py-1.5 text-xs font-medium text-[var(--accent)] hover:bg-[var(--accent)]/20 transition-colors disabled:opacity-50"
                      >
                        <GitBranch size={13} />
                        {isActionBusy ? "Loading SDLC…" : "SDLC Model"}
                      </button>

                      {isConfirmingDelete ? (
                        <div className="flex items-center gap-1.5 rounded-lg border border-rose-500/40 bg-rose-500/10 p-1 text-xs">
                          <span className="text-rose-300 px-1 font-medium">Delete?</span>
                          <button
                            type="button"
                            onClick={(e) => handleDelete(e, p.id)}
                            disabled={isActionBusy}
                            className="rounded bg-rose-600 px-2 py-0.5 font-semibold text-white hover:bg-rose-500"
                          >
                            Yes
                          </button>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setConfirmDeleteId(null);
                            }}
                            className="rounded px-1.5 py-0.5 text-[var(--text-secondary)] hover:text-white"
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setConfirmDeleteId(p.id);
                          }}
                          className="rounded-lg p-1.5 text-[var(--text-tertiary)] hover:bg-rose-500/15 hover:text-rose-400 transition-colors"
                          title="Delete Project"
                        >
                          <Trash2 size={15} />
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
        </div>
      </Block>
    </ModuleShell>
  );
}
