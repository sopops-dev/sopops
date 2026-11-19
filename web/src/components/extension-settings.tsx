// A Settings page an extension adds (GET …/settings/sections; open-source sopops has none): rows of label and value,
// some with a progress bar, then the extension's buttons, which open their URL in a new tab. A button with a title is a
// card (title, value and badge, detail); buttons with a group show one group at a time, under a switch of the groups.
import { ExternalLink } from "lucide-react";
import { useState } from "react";
import type { SettingsActionOut, SettingsRowOut, SettingsSectionOut } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Panel } from "./bits";
import { SectionHead } from "./settings";
import { Button } from "./ui/button";
import { ToggleGroup, ToggleGroupItem } from "./ui/toggle-group";

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
        {section.actions.length > 0 && <Actions actions={section.actions} />}
      </Panel>
    </>
  );
}

function Actions({ actions }: { actions: SettingsActionOut[] }) {
  const groups = [...new Set(actions.flatMap((a) => (a.group ? [a.group] : [])))];
  const [picked, setPicked] = useState<string>();
  const group = picked && groups.includes(picked) ? picked : groups[0];
  const shown = actions.filter((a) => !a.group || a.group === group);
  const cards = shown.filter((a) => a.title);
  const buttons = shown.filter((a) => !a.title);
  return (
    <div className="mt-4 grid gap-3">
      {groups.length > 1 && (
        <ToggleGroup type="single" variant="outline" size="sm" value={group} onValueChange={(v) => v && setPicked(v)}>
          {groups.map((g) => (
            <ToggleGroupItem key={g} value={g} className="px-3">
              {g}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      )}
      {cards.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-[repeat(auto-fit,minmax(14rem,1fr))]">
          {cards.map((a) => (
            <div key={a.url + a.label} className={cn("grid content-start gap-1 rounded-lg border p-4", a.kind === "primary" && "border-primary")}>
              <span className="font-medium">{a.title}</span>
              {(a.value || a.badge) && (
                <span className="flex flex-wrap items-baseline gap-x-2">
                  {a.value && <span className="text-lg tabular-nums">{a.value}</span>}
                  {a.badge && <span className="text-primary text-xs font-medium">{a.badge}</span>}
                </span>
              )}
              {a.detail && <span className="text-muted-foreground text-xs">{a.detail}</span>}
              <ActionButton action={a} className="mt-2 w-full" />
            </div>
          ))}
        </div>
      )}
      {buttons.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {buttons.map((a) => (
            <ActionButton key={a.url + a.label} action={a} />
          ))}
        </div>
      )}
    </div>
  );
}

function ActionButton({ action, className }: { action: SettingsActionOut; className?: string }) {
  return (
    <Button asChild variant={action.kind === "primary" ? "default" : "outline"} className={className}>
      <a href={action.url} target="_blank" rel="noopener noreferrer" className="hover:no-underline">
        {action.label} <ExternalLink />
      </a>
    </Button>
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
