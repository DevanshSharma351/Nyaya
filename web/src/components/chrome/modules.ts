/**
 * The module map.
 *
 * One entry per route. It is a plain data file, and everything that needs to
 * know the shape of the application - the rail, the landing page, the previous
 * and next links at the foot of each module - reads it. Duplicating this list
 * is how navigation and content drift apart.
 */

export type Module = {
  href: string;
  name: string;
  /** The single question this module answers. Shown, not just documented. */
  question: string;
  /** Lucide icon name, resolved by the rail. */
  icon: IconName;
};

export type IconName =
  | "library"
  | "search"
  | "list-checks"
  | "file-text"
  | "shield-check"
  | "git-branch"
  | "activity"
  | "history"
  | "workflow";

export const MODULES: Module[] = [
  {
    href: "/corpus",
    icon: "library",
    name: "Corpus",
    question: "What does the regulation actually say?",
  },
  {
    href: "/retrieval",
    icon: "search",
    name: "Retrieval",
    question: "Which clause governs this?",
  },
  {
    href: "/requirements",
    icon: "list-checks",
    name: "Requirements",
    question: "What must the system do, in testable form?",
  },
  {
    href: "/workflow",
    icon: "workflow",
    name: "Workflow",
    question: "Which human gates require sign-off?",
  },
  {
    href: "/artefacts",
    icon: "file-text",
    name: "Artefacts",
    question: "What do we hand to the team?",
  },
  {
    href: "/coverage",
    icon: "shield-check",
    name: "Coverage",
    question: "Which mandatory controls does nothing cover?",
  },
  {
    href: "/lifecycle",
    icon: "git-branch",
    name: "Lifecycle",
    question: "Which SDLC fits this project, and why?",
  },
  {
    href: "/impact",
    icon: "activity",
    name: "Impact",
    question: "The regulator amended it — what is now wrong?",
  },
  {
    href: "/history",
    icon: "history",
    name: "History",
    question: "What did we extract previously?",
  },
];

export function moduleAt(pathname: string): Module | undefined {
  return MODULES.find((m) => pathname.startsWith(m.href));
}

export function neighbours(pathname: string) {
  const index = MODULES.findIndex((m) => m.href === pathname);
  if (index < 0) return { previous: undefined, next: undefined };
  return {
    previous: index > 0 ? MODULES[index - 1] : undefined,
    next: index < MODULES.length - 1 ? MODULES[index + 1] : undefined,
  };
}
