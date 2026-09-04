import Coverage from "@/components/Coverage";
import Extraction from "@/components/Extraction";
import Hero from "@/components/Hero";
import Lifecycle from "@/components/Lifecycle";
import Retrieval from "@/components/Retrieval";

export default function Home() {
  return (
    <main>
      <Hero />

      <div className="mx-auto flex max-w-7xl flex-col gap-6 px-6 pb-32 lg:px-10">
        <Retrieval />
        <Extraction />
        <div className="grid gap-6 xl:grid-cols-2">
          <Coverage />
          <Lifecycle />
        </div>

        <footer className="mt-10 flex flex-wrap items-center justify-between gap-4">
          <div className="caption">
            Nyaya · न्याय — the school of logic concerned with what counts as
            admissible evidence for a claim.
          </div>
          <div className="caption">
            Figures shown are measured on a 49-pair labelled set with a single
            annotator, and thresholds are fitted on it. Optimistic until a
            held-out set exists.
          </div>
        </footer>
      </div>
    </main>
  );
}
