import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { ArrowRight, CheckCheck, Headphones } from "lucide-react";
import { DEMO, DEMO_WS } from "@/lib/demo";
import { appHref } from "@/lib/paths";
import { calls, original, releases, revision } from "@/lib/pickup-sample";
import { Button } from "@/components/ui/button";

const views = ["Call evidence", "Similar calls", "Instruction edit", "Release comparison"] as const;
export const Route = createFileRoute("/call-review")({
  beforeLoad: () => {
    if (!DEMO) throw notFound();
  },
  validateSearch: (s: Record<string, unknown>) => ({
    stage: views.find((v) => v === s.stage) ?? views[0],
    call: calls.find((c) => c.id === Number(s.call))?.id ?? calls[0].id,
  }),
  component: Review,
});
const panel = "border bg-card p-5 md:p-7";
const label = "t-label text-muted-foreground";
const booking = "https://calendar.app.google/BUvPrnU1d3Kw57TJ8";
function Review() {
  const { stage, call } = Route.useSearch();
  const selected = calls.find((c) => c.id === call)!;
  const cohort = releases.find((r) => r.version === selected.release)!;
  const next = views[views.indexOf(stage) + 1];
  return (
    <main className="min-h-screen bg-background text-foreground">
      <header className="border-b bg-card">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-5 py-4">
          <span className="flex items-center gap-2 font-semibold">
            <CheckCheck className="text-primary" /> sopops <span className="ml-2 border-l pl-3 text-sm font-normal">Sample workspace</span>
          </span>
          <a className="text-sm underline" href={appHref("/w/" + DEMO_WS)}>
            Explore full dashboard ↗
          </a>
        </div>
      </header>
      <div className="mx-auto max-w-6xl px-5 py-8 md:py-12">
        <p className={label}>Tony’s Pizza · Pickup agent</p>
        <h1 className="mt-2 text-3xl font-semibold">Order read-back review</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Fictional calls from two prompt releases. Follow one instruction from the transcript to the result.
        </p>
        <nav aria-label="Review stages" className="my-7 flex flex-wrap gap-1 border-b pb-2">
          {views.map((v) => (
            <Link
              key={v}
              to="/call-review"
              search={{ stage: v, call }}
              aria-current={stage === v ? "page" : undefined}
              className={`px-3 py-2 text-sm ${stage === v ? "bg-primary text-primary-foreground" : "hover:bg-secondary"}`}
            >
              {v}
            </Link>
          ))}
        </nav>
        {stage === views[0] && (
          <div className="grid gap-4 md:grid-cols-[1.35fr_1fr]">
            <section className={panel}>
              <p className={label}>
                Call #{call} · Release {selected.release}
              </p>
              <h2 className="my-3 flex items-center gap-2 text-xl">
                <Headphones size={19} /> Call transcript
              </h2>
              <ol>
                {selected.turns.map((turn, i) => (
                  <li
                    key={i}
                    className={`grid grid-cols-[4rem_1fr] gap-2 border-t py-3 text-sm ${i === selected.turns.length - 1 && selected.skipped ? "bg-[var(--miss-soft)] px-2 text-black" : ""}`}
                  >
                    <span className="font-semibold">{i % 2 ? "Agent" : "Caller"}</span>
                    <span>{turn}</span>
                  </li>
                ))}
              </ol>
            </section>
            <aside className={panel}>
              <p className={label}>Expected step</p>
              <blockquote className="my-4 border-l-4 border-primary pl-4 text-xl">
                “{selected.release === 14 ? original : revision}”
              </blockquote>
              <h2 className="mt-7 text-lg">{selected.skipped ? "Missed step" : "Followed"}</h2>
              <p className="mt-2 text-sm">
                {selected.skipped
                  ? "The agent gave a pickup time and ended the call before confirming the order."
                  : "The agent repeated the items and waited for confirmation before quoting the pickup time."}
              </p>
              <p className="mt-6 border-t pt-3 text-sm text-muted-foreground">
                {cohort.misses} of {cohort.count} pickup calls missed this step on release {cohort.version}.
              </p>
            </aside>
          </div>
        )}
        {stage === views[1] && (
          <section className={panel}>
            <p className={label}>Release {cohort.version}</p>
            <h2 className="my-2 text-2xl">{cohort.misses} calls closed without a read-back</h2>
            <p className="mb-5 text-sm">
              Out of {cohort.count} pickup calls where this step applied. Select a call to inspect the exchange.
            </p>
            <ul className="max-h-96 overflow-auto border-y">
              {calls
                .filter((c) => c.skipped && c.release === cohort.version)
                .map((c) => (
                  <li key={c.id}>
                    <Link
                      to="/call-review"
                      search={{ stage: views[0], call: c.id }}
                      className="flex flex-wrap items-center gap-x-5 gap-y-1 border-b p-3 text-sm hover:bg-secondary"
                    >
                      <b>#{c.id}</b>
                      <span className="flex-1">“{c.turns[c.turns.length - 1]}”</span>
                      <ArrowRight size={15} />
                    </Link>
                  </li>
                ))}
            </ul>
          </section>
        )}
        {stage === views[2] && (
          <section className={panel}>
            <p className={label}>Recorded reviewer decision · Real mistake</p>
            <h2 className="my-3 text-2xl">Confirm the items before giving a pickup time</h2>
            <p className="mb-6 max-w-2xl text-sm">
              The reviewer kept the read-back requirement and changed when the agent should perform it.
            </p>
            <div className="grid gap-3 md:grid-cols-2">
              {[original, revision].map((v, i) => (
                <div key={v} className={`border p-5 ${i ? "border-primary bg-secondary" : ""}`}>
                  <p className={label}>{i ? "Approved · Release 15" : "Original · Release 14"}</p>
                  <blockquote className="mt-3 text-lg">{v}</blockquote>
                </div>
              ))}
            </div>
          </section>
        )}
        {stage === views[3] && (
          <section className={panel}>
            <p className={label}>Missed read-back · eligible pickup calls</p>
            <h2 className="my-3 text-2xl">
              Misses fell from {releases[0].percent}% to {releases[1].percent}%
            </h2>
            <div className="grid gap-4 md:grid-cols-2">
              {releases.map((r) => (
                <div key={r.version} className="border p-5">
                  <p className={label}>Release {r.version}</p>
                  <p className="my-3 text-3xl">{r.percent}%</p>
                  <div className="mb-3 h-2 bg-secondary">
                    <div className="h-full bg-primary" style={{ width: r.percent + "%" }} />
                  </div>
                  <Link
                    className="text-sm underline"
                    to="/call-review"
                    search={{ stage: views[1], call: calls.find((c) => c.release === r.version)!.id }}
                  >
                    {r.misses} misses out of {r.count} calls
                  </Link>
                </div>
              ))}
            </div>
          </section>
        )}
        <div className="mt-6 flex justify-end">
          <Button asChild>
            {next ? (
              <Link to="/call-review" search={{ stage: next, call }}>
                {next}
                <ArrowRight />
              </Link>
            ) : (
              <a href={booking}>
                Book a review of my calls
                <ArrowRight />
              </a>
            )}
          </Button>
        </div>
      </div>
    </main>
  );
}
