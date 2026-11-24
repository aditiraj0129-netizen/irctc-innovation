import type { Lang, SEdge, SNode, StationMap as SMap } from "../api";
import { t } from "../i18n";

const ICON: Record<string, string> = { TICKET_COUNTER: "🎫", ATVM: "🏧", ENQUIRY: "ℹ", HELP_DESK: "🙋", WAITING_ROOM: "🪑",
  RETIRING_ROOM: "🛏", WASHROOM: "🚻", DRINKING_WATER: "🚰", FOOD: "🍲", CLOAKROOM: "🧳", RPF: "🛡", PARKING: "🅿", METRO: "Ⓜ" };

// A schematic SVG drawing of the station graph: platforms as bars, overbridges as dashed lines,
// entrances as squares, facilities as icons, and the chosen route highlighted. Not to scale.
export function StationMap({ map, path, lang, start, end }: { map: SMap; path: string[]; lang: Lang; start?: string | null; end?: string | null }) {
  const nodes = Object.fromEntries(map.nodes.map((n) => [n.id, n])) as Record<string, SNode>;
  const xs = map.nodes.map((n) => n.x), ys = map.nodes.map((n) => n.y);
  const minX = Math.min(...xs) - (map.kind === "TERMINUS" ? 260 : 70), maxX = Math.max(Math.max(...xs), 2 * Math.max(...map.nodes.filter((n) => n.kind === "PLATFORM").map((n) => n.x))) + 60, minY = Math.min(...ys) - 30, maxY = Math.max(...ys) + 30;
  const W = 900, sx = W / (maxX - minX), sy = sx, H = (maxY - minY) * sy;
  const X = (x: number) => (x - minX) * sx, Y = (y: number) => (y - minY) * sy;
  const groupsY: Record<number, number> = {};
  map.nodes.filter((n) => n.kind === "PLATFORM").forEach((n) => { if (n.group != null) groupsY[n.group] = n.y; });
  const L = 2 * Math.max(...map.nodes.filter((n) => n.kind === "PLATFORM").map((n) => n.x));   // platform node = middle
  const term = map.kind === "TERMINUS";
  const fobs: Record<string, SNode[]> = {};
  map.nodes.filter((n) => n.kind === "FOB").forEach((n) => { const k = n.id.replace(/_G\d+$/, ""); (fobs[k] ||= []).push(n); });
  const onPath = new Set<string>();
  path.forEach((p, i) => { if (i) onPath.add(`${path[i - 1]}|${p}`); });
  const isOn = (e: SEdge) => onPath.has(`${e.a}|${e.b}`) || onPath.has(`${e.b}|${e.a}`);
  const lifts = map.edges.filter((e) => e.kind === "LIFT");
  return (
    <figure className="smap" data-testid="station-map">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${map.name[lang]} — ${t(lang, "sn_schematic")}`}>
        {Object.entries(groupsY).map(([g, y]) => (
          <g key={g}>
            <rect x={X(0)} y={Y(y) - 7} width={X(L) - X(0)} height={14} rx={7} className="smap-pf" />
            <text x={term ? X(L) + 6 : X(0) - 6} y={Y(y) + 4} textAnchor={term ? "start" : "end"} fontSize={12} fontWeight={700} fill="#3b4250">{map.groups[Number(g)].join("·")}</text>
          </g>
        ))}
        {Object.entries(fobs).map(([k, ns]) => (
          <line key={k} x1={X(ns[0].x)} x2={X(ns[0].x)} y1={Y(Math.min(...ns.map((n) => n.y))) - 10} y2={Y(Math.max(...ns.map((n) => n.y))) + 10} className="smap-fob" />
        ))}
        {map.nodes.filter((n) => n.kind === "CONCOURSE").map((n) => <rect key={n.id} x={X(n.x) - 8} y={Y(n.y) - 10} width={16} height={20} className="smap-conc" />)}
        {lifts.map((e, i) => { const n = nodes[e.b]; return <text key={i} x={X(n.x) + 5} y={Y(n.y) - 9} className="smap-lift">⇅</text>; })}
        {map.edges.filter(isOn).map((e, i) => (
          <line key={i} x1={X(nodes[e.a].x)} y1={Y(nodes[e.a].y)} x2={X(nodes[e.b].x)} y2={Y(nodes[e.b].y)} className={`smap-route smap-route-${e.kind}`} />
        ))}
        {map.nodes.filter((n) => n.kind === "SIDE").map((n) => (
          <g key={n.id}><rect x={X(n.x) - 9} y={Y(n.y) - 9} width={18} height={18} rx={3} className="smap-side" />
            <text x={term ? X(n.x) - 14 : X(n.x) + 14} y={Y(n.y) + 4} textAnchor={term ? "end" : "start"} fontSize={11} fontWeight={600} fill="#0f2a4a">{n.label[lang]}</text></g>
        ))}
        {map.nodes.filter((n) => n.kind === "FACILITY").map((n) => (
          <text key={n.id} x={X(n.x)} y={Y(n.y) + 5} className={`smap-fac ${n.verification === "ILLUSTRATIVE" ? "smap-illus" : ""}`}>
            <title>{n.label[lang]}</title>{ICON[n.facility_type ?? ""] ?? "•"}</text>
        ))}
        {start && nodes[start] && <circle cx={X(nodes[start].x)} cy={Y(nodes[start].y)} r={9} className="smap-start" />}
        {end && nodes[end] && <circle cx={X(nodes[end].x)} cy={Y(nodes[end].y)} r={9} className="smap-end" />}
      </svg>
      <figcaption className="tiny muted">{t(lang, "sn_schematic")} <span className="smap-key">● {t(lang, "loc_title")} ● {t(lang, "fd_to")} ⇅ {t(lang, "via_LIFT")} ┆ FOB</span></figcaption>
    </figure>
  );
}
