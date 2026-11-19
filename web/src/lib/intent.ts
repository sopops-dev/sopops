// The `?intent=` a link into the app can carry, kept in this browser through signing in until the person's team is
// made. The server's extensions then say where it sends them first; on open-source sopops, nowhere, and setup goes on.
import { call, sdk } from "./api";
import { assignApp } from "./paths";
import { prefs } from "./prefs";

const KEY = "intent";
const WORD = /^[a-z0-9-]{1,40}$/;
const KEEP_MS = 24 * 60 * 60 * 1000; // a day: an old visit's word shouldn't steer a team made much later

/** Keep the page's `?intent=`, if it has one. Run once, before the router drops the query. */
export function captureIntent() {
  const word = new URLSearchParams(window.location.search).get("intent");
  if (word && WORD.test(word)) prefs.set(KEY, `${word}:${Date.now()}`);
}

function takeIntent(): string | null {
  const [word, at] = (prefs.get(KEY) ?? "").split(":");
  prefs.remove(KEY);
  return word && WORD.test(word) && Date.now() - Number(at) < KEEP_MS ? word : null;
}

/** A new team: to where its intent sends it first, if anywhere, then on to `path` (its setup). */
export async function intoNewTeam(ws: string, path: string) {
  const intent = takeIntent();
  if (intent) {
    try {
      const { url } = await call(sdk.followIntent({ path: { workspace: ws }, body: { intent, next: path } }));
      if (url) return window.location.assign(url);
    } catch {
      // setup goes on without it
    }
  }
  assignApp(path);
}
