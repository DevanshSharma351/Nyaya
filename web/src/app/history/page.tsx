"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { FolderGit2 } from "lucide-react";
import { Block, ModuleShell } from "@/components/chrome/ModuleShell";
import { api, type Project, type SDLCFromBrief } from "@/lib/api";
import { useJobs } from "@/components/chrome/Jobs";

export default function HistoryPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const { setResult } = useJobs();
  const router = useRouter();

  useEffect(() => {
    let cancelled = false;
    api
      .projects()
      .then((data) => {
        if (!cancelled) setProjects(data);
      })
      .catch((err) => {
        console.error("Failed to load history:", err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSelect = async (project: Project) => {
    try {
      const sdlc = await api.projectSdlc(project.id);
      
      // Load into the lifecycle job — pass the project description so the textarea
      // shows the original brief rather than just the project name.
      setResult("lifecycle", project.description || project.name, sdlc, (result: SDLCFromBrief) => {
        const title =
          result.workflow.phases.length > 0
            ? `${result.recommendation.recommended} (${result.workflow.phases.length} phases)`
            : result.recommendation.recommended;
        return {
          label: title,
          detail: `${result.requirements_extracted} requirements`,
        };
      });
      
      router.push("/lifecycle");
    } catch (err) {
      console.error("Failed to load SDLC history:", err);
    }
  };

  return (
    <ModuleShell
      pathname="/history"
      eyebrow="History"
      title="What did we extract previously?"
      lede="Reload previous project SDLC assessments and extractions instantly without running the LLM."
    >
      <Block>
        <div className="flex flex-col gap-4 max-w-3xl">
          {loading && (
            <div className="glass-panel p-8 text-center text-[var(--text-tertiary)]">
              Loading extraction history...
            </div>
          )}
          {!loading && projects.length === 0 && (
            <div className="glass-panel p-8 text-center text-[var(--text-tertiary)]">
              No previous extractions found in the database. Head to Requirements to start one!
            </div>
          )}
          {!loading &&
            projects.map((p) => (
              <button
                key={p.id}
                onClick={() => handleSelect(p)}
                className="glass-panel group p-6 text-left hover:border-[var(--brand)] hover:shadow-[0_0_0_1px_var(--brand)] transition-all flex items-start gap-4"
              >
                <FolderGit2 className="mt-1 flex-shrink-0 text-[var(--text-tertiary)] group-hover:text-[var(--brand)] transition-colors" />
                <div className="flex flex-col gap-1">
                  <div className="text-[1.125rem] font-semibold text-[var(--text)] group-hover:text-[var(--brand)] transition-colors">
                    {p.name}
                  </div>
                  <div className="text-[0.875rem] text-[var(--text-secondary)]">
                    {p.domain} • {new Date(p.created_at).toLocaleString()}
                  </div>
                  <div className="text-[0.875rem] font-medium text-[var(--text-tertiary)] mt-2 bg-[var(--surface-raised)] px-2 py-1 rounded w-fit">
                    {p.requirement_count} requirements extracted
                  </div>
                </div>
              </button>
            ))}
        </div>
      </Block>
    </ModuleShell>
  );
}
