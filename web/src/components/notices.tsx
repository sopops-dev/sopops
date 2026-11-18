// Notices from the server's extensions (GET …/notices; open-source sopops has none). info and warning: a slim banner
// across the top of the workspace, dismissible for the browser session. blocking: a dialog; "Not now" closes it for the
// browser session and leaves it as a warning banner, which can't be dismissed, so it's never fully out of sight.
import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useState } from "react";
import { type NoticeOut, q } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "./ui/dialog";

const KEY = "sopops.notices.dismissed";

function readDismissed(): Set<string> {
  try {
    return new Set(JSON.parse(sessionStorage.getItem(KEY) ?? "[]") as string[]);
  } catch {
    return new Set(); // no storage: they show again on the next load, which is the safe side
  }
}

function useDismissed(): [Set<string>, (id: string) => void] {
  const [ids, setIds] = useState(readDismissed);
  const dismiss = (id: string) =>
    setIds((prev) => {
      const next = new Set(prev).add(id);
      try {
        sessionStorage.setItem(KEY, JSON.stringify([...next]));
      } catch {
        // kept in memory for this page
      }
      return next;
    });
  return [ids, dismiss];
}

export function Notices({ ws }: { ws: string }) {
  // every minute and on focus (the app's default), so a new notice shows without a reload
  const res = useQuery({ ...q.notices(ws), refetchInterval: 60_000 });
  const [dismissed, dismiss] = useDismissed();
  const notices = res.data?.notices ?? [];
  const blocking = notices.find((n) => n.level === "blocking" && !dismissed.has(n.id));
  // a blocking notice closed with "Not now" stays, as a warning
  const bands = notices.filter((n) => (n.level === "blocking" ? dismissed.has(n.id) : !dismissed.has(n.id)));
  return (
    <>
      {bands.length > 0 && (
        <div role="region" aria-label="Notices">
          {bands.map((n) => (
            <NoticeBand key={n.id} n={n} onDismiss={n.level === "blocking" ? undefined : () => dismiss(n.id)} />
          ))}
        </div>
      )}
      {blocking && <BlockingNotice key={blocking.id} n={blocking} onClose={() => dismiss(blocking.id)} />}
    </>
  );
}

function Action({ n, className }: { n: NoticeOut; className?: string }) {
  if (!n.action_label || !n.action_url) return null;
  return (
    <a href={n.action_url} target="_blank" rel="noopener noreferrer" className={className}>
      {n.action_label}
    </a>
  );
}

function NoticeBand({ n, onDismiss }: { n: NoticeOut; onDismiss?: () => void }) {
  const warn = n.level !== "info";
  return (
    <div role="status" className={cn("flex items-center gap-3 border-b px-4 py-2 text-sm md:px-6", warn ? "bg-warn-soft border-warn/30" : "bg-muted")}>
      <p className="min-w-0 flex-1">
        <b className="font-semibold">{n.title}</b> <span className="text-muted-foreground max-sm:hidden">{n.body}</span>
      </p>
      <Action n={n} className="t-label border-foreground hover:bg-foreground hover:text-background shrink-0 border px-3 py-1 text-inherit hover:no-underline" />
      {onDismiss && (
        <button type="button" onClick={onDismiss} aria-label={`Dismiss: ${n.title}`} className="hover:text-foreground text-muted-foreground shrink-0 cursor-pointer p-1">
          <X className="size-4" />
        </button>
      )}
    </div>
  );
}

/** Radix's dialog: focus stays inside, Esc and the overlay close it (as "Not now" does), and it's aria-modal. */
function BlockingNotice({ n, onClose }: { n: NoticeOut; onClose: () => void }) {
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="rounded-none sm:max-w-md" showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>{n.title}</DialogTitle>
          <DialogDescription className="text-foreground text-sm">{n.body}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Not now
          </Button>
          {n.action_label && n.action_url && (
            <Button asChild>
              <a href={n.action_url} target="_blank" rel="noopener noreferrer" className="hover:no-underline">
                {n.action_label}
              </a>
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
