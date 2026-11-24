// The passenger's own list of journeys and recent activity, kept ON THIS DEVICE only.
// We store journey ids (demo scenario ids) and short activity labels: no PNR, names or ticket details.
const KEY = "aglaKadam.myJourneys", ACT = "aglaKadam.activity";

function read<T>(k: string, fallback: T): T {
  try { const v = window.localStorage.getItem(k); return v ? (JSON.parse(v) as T) : fallback; } catch { return fallback; }
}
function write(k: string, v: unknown) { try { window.localStorage.setItem(k, JSON.stringify(v)); } catch { /* storage off */ } }

export const myJourneys = {
  list: (): string[] => read<string[]>(KEY, []).filter((x) => /^[a-z0-9_]{1,60}$/.test(x)),
  add(id: string) { const l = myJourneys.list().filter((x) => x !== id); write(KEY, [id, ...l].slice(0, 10)); },
  remove(id: string) { write(KEY, myJourneys.list().filter((x) => x !== id)); },
  last: (): string | null => myJourneys.list()[0] ?? null,
};

export interface Activity { id: string; what: string; at: string }
export const activity = {
  list: (): Activity[] => read<Activity[]>(ACT, []),
  log(id: string, what: string) {
    const l = activity.list().filter((a) => !(a.id === id && a.what === what));
    write(ACT, [{ id, what, at: new Date().toISOString() }, ...l].slice(0, 8));
  },
};
