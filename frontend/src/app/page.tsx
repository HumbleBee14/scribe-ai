export default function Home() {
  return (
    <main className="min-h-screen bg-[#0f1117] text-zinc-100">
      <div className="mx-auto flex min-h-screen w-full max-w-6xl flex-col px-6 py-10">
        <header className="mb-10 flex flex-col gap-3">
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-orange-300">
            Prox Challenge
          </p>
          <h1 className="max-w-3xl text-4xl font-semibold tracking-tight text-white sm:text-5xl">
            Vulcan OmniPro 220 multimodal support assistant
          </h1>
          <p className="max-w-2xl text-base leading-7 text-zinc-300">
            Phase 1 scaffold is live. The final product will answer exact technical
            questions, surface grounded manual evidence, and generate diagrams,
            calculators, and troubleshooting flows.
          </p>
        </header>

        <section className="grid flex-1 gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 p-6 shadow-2xl shadow-black/20">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-white">Chat Workspace</h2>
                <p className="text-sm text-zinc-400">
                  Streaming chat, tool calls, and artifact rendering land here next.
                </p>
              </div>
              <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-300">
                Phase 1
              </span>
            </div>

            <div className="rounded-xl border border-dashed border-zinc-800 bg-zinc-900/60 p-5">
              <p className="mb-4 text-sm text-zinc-400">Quick actions</p>
              <div className="flex flex-wrap gap-3">
                {["Set up MIG", "Set up TIG", "Troubleshoot", "View Specs"].map((label) => (
                  <button
                    key={label}
                    type="button"
                    className="rounded-full border border-zinc-700 bg-zinc-950 px-4 py-2 text-sm text-zinc-200 transition hover:border-orange-400 hover:text-white"
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <aside className="rounded-2xl border border-zinc-800 bg-zinc-950/80 p-6">
            <h2 className="mb-4 text-lg font-semibold text-white">Planned Surfaces</h2>
            <ul className="space-y-3 text-sm text-zinc-300">
              <li>Evidence cards with page previews and exactness labels</li>
              <li>Source viewer with highlight overlays and region crops</li>
              <li>Artifact pane for SVG diagrams, calculators, and flowcharts</li>
              <li>Session context for process, voltage, material, and setup state</li>
            </ul>
          </aside>
        </section>
      </div>
    </main>
  );
}
