// Display helpers. Amounts arrive in paise from the rules engine; we only format them.
export function rupees(paise: number): string {
  const r = Math.floor(paise / 100);
  return "₹" + r.toLocaleString("en-IN");
}

const IST = "Asia/Kolkata";

export function time(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: IST });
}

export function dayTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: IST });
}

export function minutesBetween(a: string, b: string): number {
  return Math.round((new Date(b).getTime() - new Date(a).getTime()) / 60000);
}

export function duration(mins: number, lang: "en" | "hi"): string {
  const sign = mins < 0 ? "-" : "";
  const m = Math.abs(mins);
  const h = Math.floor(m / 60), r = m % 60;
  if (lang === "hi") return `${sign}${h ? h + " घं " : ""}${r} मि`;
  return `${sign}${h ? h + "h " : ""}${r}m`;
}
