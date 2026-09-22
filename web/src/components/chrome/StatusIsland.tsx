"use client";

/**
 * The status island.
 *
 * One object, pinned above the page, that reports whatever the application is
 * currently doing. It exists because of a specific problem: extraction runs on
 * a local model and takes forty to a hundred seconds, and for most of that time
 * a static page is indistinguishable from a broken one.
 *
 * The usual answers are a toast stack or a spinner beside the button. Both are
 * worse here. Toasts pile up and cover content; a spinner beside the button
 * disappears the moment the reader scrolls. A single surface that changes shape
 * stays in one place, holds one message, and is followed with almost no effort
 * because there is only ever one of it.
 *
 * It reports and never demands: it is not modal, it never steals focus, and
 * every state it shows is also present in the page itself. Nobody should have
 * to watch it.
 *
 * It is also transient. An earlier version idled with the corpus size and model
 * reachability in it, which meant a pill sat permanently over the middle of
 * every page - on the impact module it covered a form field. Persistent state
 * belongs in the rail, where it is always in the same place and never on top of
 * anything; the island is for things that are happening now and then stop.
 *
 * What it shows is read from the job store rather than pushed into it by
 * whichever page happens to be mounted. That is what keeps the island and the
 * module consistent: previously a page reported a job starting, then unmounted
 * on navigation and never reported it finishing, so the island span forever
 * while the work had long since completed. One record, two readers.
 */

import { Check, Loader2, TriangleAlert } from "lucide-react";
import { useEffect } from "react";
import { useActiveJob } from "./Jobs";
import {
  DynamicContainer,
  DynamicDescription,
  DynamicIsland,
  DynamicIslandProvider,
  DynamicTitle,
  useDynamicIslandSize,
} from "@/components/ui/dynamic-island";

export type Task = {
  state: "running" | "done" | "failed";
  label: string;
  detail?: string;
};

function Body({ task }: { task: Task | null }) {
  const { setSize } = useDynamicIslandSize();

  useEffect(() => {
    if (!task) {
      setSize("empty");
      return;
    }
    setSize(task.state === "running" ? "long" : "large");
  }, [task, setSize]);

  if (!task) return null;

  if (task.state === "running") {
    return (
      <DynamicContainer className="flex items-center gap-3 px-5">
        <div className="flex h-full items-center gap-3">
          <Loader2 className="h-4 w-4 animate-spin" style={{ opacity: 0.9 }} />
          <DynamicTitle style={{ fontSize: "0.875rem", fontWeight: 550 }}>
            {task.label}
          </DynamicTitle>
          {task.detail && (
            <DynamicDescription
              className="mono"
              style={{ color: "rgba(255,255,255,0.6)", fontSize: "0.6875rem" }}
            >
              {task.detail}
            </DynamicDescription>
          )}
        </div>
      </DynamicContainer>
    );
  }

  const failed = task.state === "failed";
  return (
    <DynamicContainer className="flex items-center px-5">
      <div className="flex h-full items-center gap-3.5">
        {failed ? (
          <TriangleAlert className="h-5 w-5 shrink-0" style={{ color: "#fca5a5" }} />
        ) : (
          <Check className="h-5 w-5 shrink-0" style={{ color: "#4ade80" }} />
        )}
        <div className="min-w-0">
          <DynamicTitle style={{ fontSize: "0.875rem", fontWeight: 550 }}>
            {task.label}
          </DynamicTitle>
          {task.detail && (
            <DynamicDescription
              className="truncate"
              style={{ color: "rgba(255,255,255,0.62)", fontSize: "0.75rem" }}
            >
              {task.detail}
            </DynamicDescription>
          )}
        </div>
      </div>
    </DynamicContainer>
  );
}

export function StatusIsland() {
  const active = useActiveJob();
  const task: Task | null = active
    ? {
        state: active[1].state === "idle" ? "done" : active[1].state,
        label: active[1].label ?? "Working",
        detail: active[1].detail,
      }
    : null;

  return (
    <div
      className="pointer-events-none fixed inset-x-0 bottom-6 hidden md:block"
      style={{ zIndex: "var(--z-island)" as unknown as number }}
      role="status"
      aria-live="polite"
    >
      <DynamicIslandProvider initialSize="empty">
        <DynamicIsland id="nyaya-status">
          <Body task={task} />
        </DynamicIsland>
      </DynamicIslandProvider>
    </div>
  );
}
