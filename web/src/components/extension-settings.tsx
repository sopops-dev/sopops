// A Settings page an extension adds (GET …/settings/sections; open-source sopops has none): rows of label and value,
// some with a progress bar, then the extension's buttons, which open their URL in a new tab.
import { ExternalLink } from "lucide-react";
import type { SettingsRowOut, SettingsSectionOut } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Panel } from "./bits";
import { SectionHead } from "./settings";
import { Button } from "./ui/button";

export function ExtensionSettings({ section }: { section: SettingsSectionOut }) {
  return (
    <>
      <SectionHead title={section.title}>{section.description}</SectionHead>
      <Panel>
        <dl className="grid grid-cols-[minmax(0,1fr)] text-sm sm:grid-cols-[minmax(10rem,max-content)_minmax(0,1fr)] sm:gap-x-6">
          {section.rows.map((r, i) => (
            <Row key={`${r.label}-${i}`} row={r} />
          ))}
        </dl>
        {section.note && <p className="text-muted-foreground mt-4 mb-0 text-sm">{section.note}</p>}
        {section.actions.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {section.actions.map((a) => (
              <Button key={a.url + a.label} asChild variant={a.kind === "primary" ? "default" : "outline"}>
                <a href={a.url} target="_blank" rel="noopener noreferrer" className="hover:no-underline">
                  {a.label} <ExternalLink />
                </a>
              </Button>
            ))}
          </div>
        )}
      </Panel>
    </>
  );
}

function Row({ row }: { row: SettingsRowOut }) {
  const bar = row.used != null && row.limit != null && row.limit > 0;
  const pct = bar ? Math.min(100, Math.max(0, (row.used! / row.limit!) * 100)) : 0;
  return (
    <div className="col-span-full grid grid-cols-subgrid border-t py-2.5 first:border-t-0 first:pt-0 last:pb-0">
      <dt className="text-muted-foreground">{row.label}</dt>
      <dd className="m-0 grid gap-1.5">
        <span className="tabular-nums">{row.value}</span>
        {bar && (
          <div
            className="bg-muted h-1.5 overflow-hidden rounded-full"
            role="progressbar"
            aria-label={row.label}
            aria-valuenow={Math.round(pct)}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div className={cn("h-full transition-[width]", pct >= 100 ? "bg-destructive" : pct >= 80 ? "bg-warn" : "bg-primary")} style={{ width: `${pct}%` }} />
          </div>
        )}
        {row.note && <span className="text-muted-foreground text-xs">{row.note}</span>}
      </dd>
    </div>
  );
}
