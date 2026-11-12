// Agla Kadam — SBI Youth Ideathon 2026 video-pitch deck (8 slides, official structure).
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");
const { applyTheme } = require("/root/.claude/skills/synced/65cd1ffd-4a95-465d-b082-8c82d31ef387_7fcff994-e63e-480e-a4cc-cb06acb64bc5/pptx/scripts/apply_theme.js");

const SHOTS = "/home/claude/agla-kadam/submission/screenshots/";
const OUT = "/home/claude/deck/Agla_Kadam_Innovation_Challenge_Pitch.pptx";

const HEX = {
  navy: "14325C", navy2: "0E2442", ink: "1B2430", muted: "5B6573", line: "D9DEE5", soft: "EEF2F7",
  orange: "F2A541", orangeDk: "B86E00", green: "1E8E5A", greenBg: "E6F4EC", red: "C0392B", redBg: "FBEAE8",
  amberBg: "FFF4E0", white: "FFFFFF",
};
const THEME = {
  name: "Agla Kadam", headFontFace: "Calibri", bodyFontFace: "Calibri",
  colors: { dk1: HEX.ink, lt1: HEX.white, dk2: HEX.navy, lt2: HEX.soft, accent1: HEX.navy, accent2: HEX.orange,
    accent3: HEX.green, accent4: HEX.red, accent5: "3A6EA5", accent6: HEX.muted, hlink: "1F5FA8", folHlink: "6B4FA0" },
};

async function icon(Comp, color, size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color: "#" + color, size: String(size) }));
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5
  pres.title = "Agla Kadam — Your Next Move During a Disrupted Train Journey";
  pres.author = "Aditi";
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  const C = pres.SchemeColor;

  // ---------- layouts ----------
  pres.defineSlideMaster({
    title: "CONTENT", background: { color: HEX.white },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 10.4, h: 0.75, fontSize: 32, bold: true, align: "left",
        color: C.text2, valign: "middle", margin: 0 }, text: "" } },
      { text: { text: "AGLA KADAM", options: { x: 11.0, y: 0.45, w: 1.75, h: 0.3, fontSize: 10, bold: true, color: C.accent2,
        align: "right", charSpacing: 2, margin: 0 } } },
      { text: { text: "Prototype · simulated railway data · not an official IRCTC app", options: { x: 0.6, y: 7.08, w: 8, h: 0.25,
        fontSize: 9, color: C.accent6, margin: 0 } } },
    ],
    slideNumber: { x: 12.35, y: 7.05, w: 0.4, h: 0.3, fontSize: 9, color: HEX.muted, align: "right" },
  });
  pres.defineSlideMaster({ title: "DARK", background: { color: HEX.navy2 }, objects: [] });
  pres.defineSlideMaster({ title: "BLANK", background: { color: HEX.white }, objects: [] });

  const ic = {
    train: await icon(fa.FaTrain, HEX.white), clock: await icon(fa.FaClock, HEX.white), wallet: await icon(fa.FaWallet, HEX.white),
    route: await icon(fa.FaRoute, HEX.white), check: await icon(fa.FaCheckCircle, HEX.white), search: await icon(fa.FaSearch, HEX.white),
    balance: await icon(fa.FaBalanceScale, HEX.white), random: await icon(fa.FaRandom, HEX.white),
    grad: await icon(fa.FaUserGraduate, HEX.navy), users: await icon(fa.FaUsers, HEX.navy), senior: await icon(fa.FaBlind, HEX.navy),
    link: await icon(fa.FaExchangeAlt, HEX.navy), road: await icon(fa.FaRoad, HEX.navy), lang: await icon(fa.FaLanguage, HEX.navy),
    q: await icon(fa.FaQuestion, HEX.orangeDk), flask: await icon(fa.FaFlask, HEX.white), shield: await icon(fa.FaShieldAlt, HEX.white),
    gavel: await icon(fa.FaBalanceScale, HEX.white), ear: await icon(fa.FaComments, HEX.white), wifi: await icon(fa.FaWifi, HEX.white),
    github: await icon(fa.FaGithub, HEX.white), arrow: await icon(fa.FaArrowRight, HEX.orange),
  };

  const phone = (s, file, x, y, h, name) => {
    const w = h * (1000 / 2150);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x - 0.07, y: y - 0.07, w: w + 0.14, h: h + 0.14, rectRadius: 0.12,
      fill: { color: HEX.navy2 }, line: { color: HEX.navy2 }, objectName: name + " frame",
      shadow: { type: "outer", color: "000000", opacity: 0.22, blur: 8, offset: 3, angle: 90 } });
    s.addImage({ path: SHOTS + file, x, y, w, h, objectName: name, altText: name + " (real screenshot of the prototype)" });
    return w;
  };

  // =====================================================================
  // 1. OPENING (official template + idea panel)
  // =====================================================================
  pres.addSection({ title: "Opening" });
  let s = pres.addSlide({ masterName: "BLANK", sectionTitle: "Opening" });
  s.addImage({ path: "/home/claude/deck/tpl-4.png", x: 0, y: 0, w: 13.333, h: 7.5, objectName: "Official opening template",
    altText: "SBI Youth Ideathon 2026 official opening screen template" });
  // Idea panel over the "team picture" area (replace with a team photo if you prefer)
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 7.7, y: 1.05, w: 4.6, h: 2.55, rectRadius: 0.15, fill: { color: HEX.navy2 },
    line: { color: HEX.navy2 }, objectName: "Idea panel" });
  s.addText("AGLA KADAM", { x: 7.95, y: 1.22, w: 4.1, h: 0.62, fontSize: 34, bold: true, color: HEX.white, charSpacing: 3,
    margin: 0, isTextBox: true, objectName: "Idea title" });
  s.addText("Your next move during a disrupted train journey", { x: 7.95, y: 1.83, w: 4.1, h: 0.4, fontSize: 14,
    color: "C9D6E8", margin: 0, isTextBox: true });
  // journey motif: station dots, a delay break, then a clear next step
  const ly = 2.85;
  s.addShape(pres.shapes.LINE, { x: 8.05, y: ly, w: 1.35, h: 0, line: { color: "8DA2BF", width: 2.5 } });
  s.addShape(pres.shapes.LINE, { x: 9.4, y: ly, w: 0.9, h: 0, line: { color: HEX.red, width: 2.5, dashType: "dash" } });
  s.addShape(pres.shapes.LINE, { x: 10.3, y: ly, w: 1.5, h: 0, line: { color: HEX.orange, width: 3 } });
  [[8.0, "8DA2BF", "Start"], [9.35, HEX.red, "Delay"], [10.25, HEX.orange, "Decide"], [11.75, HEX.green, "Arrive"]].forEach(([x, col, lab]) => {
    s.addShape(pres.shapes.OVAL, { x, y: ly - 0.1, w: 0.2, h: 0.2, fill: { color: col }, line: { color: HEX.white, width: 1.5 } });
    s.addText(lab, { x: x - 0.35, y: ly + 0.14, w: 0.9, h: 0.28, fontSize: 11, color: "C9D6E8", align: "center", margin: 0, isTextBox: true });
  });
  // fields (UID / team / school are left for the participant to type)
  const field = (txt, x, y, w, ph) => s.addText(txt, { x, y, w, h: 0.36, fontSize: ph ? 13 : 15, bold: !ph, italic: ph,
    color: ph ? "8A93A0" : HEX.navy2, margin: 0, valign: "middle", isTextBox: true });
  field("type your UID", 9.05, 4.0, 3.2, true);
  field("type your team name", 10.15, 4.66, 2.1, true);
  field("Agla Kadam", 10.0, 5.33, 2.3, false);
  field("type your college", 10.65, 5.99, 1.75, true);
  s.addNotes(`[0:00–0:08] Face on camera. "Imagine it's 2:30 in the morning. Your train is stuck in fog… and your connecting train leaves at 6:15."
Fill UID, team name and school/college in the grey fields before recording (official template fields).`);

  // =====================================================================
  // 2. PROBLEM
  // =====================================================================
  pres.addSection({ title: "Problem" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Problem" });
  s.addText("2:30 a.m. Fog. One delay breaks the whole journey", { placeholder: "title" });
  s.addText("Illustrative scenario (the same one our prototype simulates)", { x: 0.6, y: 1.08, w: 8, h: 0.3, fontSize: 12,
    italic: true, color: C.accent6, margin: 0, isTextBox: true });
  // journey strip
  const jy = 2.15;
  const stops = [[0.9, "New Delhi", "Dep 21:00"], [5.2, "Prayagraj Jn", "Change: 06:15 train"], [10.9, "Darbhanga", "Booked arrival 16:30"]];
  s.addShape(pres.shapes.LINE, { x: 1.0, y: jy, w: 4.3, h: 0, line: { color: HEX.navy, width: 3 } });
  s.addShape(pres.shapes.LINE, { x: 5.3, y: jy, w: 5.7, h: 0, line: { color: "9AA6B5", width: 3, dashType: "dash" } });
  stops.forEach(([x, n, sub]) => {
    s.addShape(pres.shapes.OVAL, { x, y: jy - 0.14, w: 0.28, h: 0.28, fill: { color: HEX.navy }, line: { color: HEX.white, width: 2 } });
    s.addText(n, { x: x - 0.8, y: jy + 0.22, w: 1.9, h: 0.32, fontSize: 15, bold: true, color: C.text1, align: "center", margin: 0, isTextBox: true });
    s.addText(sub, { x: x - 0.8, y: jy + 0.52, w: 1.9, h: 0.28, fontSize: 12, color: C.accent6, align: "center", margin: 0, isTextBox: true });
  });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 2.0, y: 1.45, w: 2.45, h: 0.48, rectRadius: 0.08, fill: { color: HEX.redBg },
    line: { color: HEX.red, width: 1 } });
  s.addText("Running 2 h 10 m late", { x: 2.0, y: 1.45, w: 2.45, h: 0.48, fontSize: 14, bold: true, color: HEX.red, align: "center",
    valign: "middle", margin: 0, isTextBox: true });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 6.2, y: 1.45, w: 3.9, h: 0.48, rectRadius: 0.08, fill: { color: HEX.amberBg },
    line: { color: HEX.orange, width: 1 } });
  s.addText("Now arrives 07:10 — connection gone?", { x: 6.2, y: 1.45, w: 3.9, h: 0.48, fontSize: 14, bold: true,
    color: HEX.orangeDk, align: "center", valign: "middle", margin: 0, isTextBox: true });
  // questions grid
  const qs = ["Should I wait for the next train or book another?", "If I cancel now, how much money comes back?",
    "Can I claim a refund (TDR)? Before which deadline?", "Is another route possible — and can I make the change in time?",
    "What about my family on a different PNR?", "Is the information I'm seeing even up to date?"];
  qs.forEach((q, i) => {
    const x = 0.6 + (i % 3) * 4.1, y = 3.45 + Math.floor(i / 3) * 1.12;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 3.9, h: 0.95, rectRadius: 0.1, fill: { color: HEX.soft }, line: { color: HEX.soft } });
    s.addShape(pres.shapes.OVAL, { x: x + 0.2, y: y + 0.24, w: 0.46, h: 0.46, fill: { color: HEX.amberBg }, line: { color: HEX.orange, width: 1 } });
    s.addImage({ data: ic.q, x: x + 0.33, y: y + 0.37, w: 0.2, h: 0.2 });
    s.addText(q, { x: x + 0.82, y, w: 2.95, h: 0.95, fontSize: 14, color: C.text1, valign: "middle", margin: 0, isTextBox: true });
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 5.85, w: 12.1, h: 0.95, fill: { color: HEX.navy }, line: { color: HEX.navy } });
  s.addText("Passengers don't just need train updates. They need to know what to do next.", { x: 0.9, y: 5.85, w: 11.5, h: 0.95,
    fontSize: 22, bold: true, color: HEX.white, valign: "middle", margin: 0, isTextBox: true });
  s.addNotes(`Apps already tell you a train is late (Indian Railways even sends SMS alerts for delays — Lok Sabha reply, 11 Feb 2026).
What's missing is the decision: wait, cancel, rebook, or claim — and by when. Refund rules are time-based, so a late or wrong decision costs real money.
Scenario is illustrative; trains in the prototype are simulated (90xxx numbers).`);

  // =====================================================================
  // 3. WHO
  // =====================================================================
  pres.addSection({ title: "Who" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Who" });
  s.addText("Who gets stuck at that moment", { placeholder: "title" });
  s.addText("Example passenger groups (personas based on the rules and situations we modelled — not interview data yet)", {
    x: 0.6, y: 1.08, w: 11.5, h: 0.3, fontSize: 12, italic: true, color: C.accent6, margin: 0, isTextBox: true });
  const who = [
    [ic.grad, "Students & first-time travellers", "Don't know what a TDR is, or that it must be filed before the train actually leaves."],
    [ic.users, "Families on two PNRs", "Two confirmed, two waitlisted after the chart. Travel together or split?"],
    [ic.senior, "Senior citizens", "A 30-minute change of train can be impossible without lifts or ramps."],
    [ic.link, "Passengers with connections", "One delay breaks the next train. Linked PNRs change what refund applies."],
    [ic.road, "Long-distance travellers", "More hours on the move means more chances of delay — often at night, with weak signal."],
    [ic.lang, "Limited rule or digital knowledge", "Rules are in English PDFs. They need plain Hindi or Hinglish answers."],
  ];
  who.forEach(([img, h, d], i) => {
    const x = 0.6 + (i % 3) * 4.1, y = 1.65 + Math.floor(i / 3) * 2.6;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 3.9, h: 2.35, rectRadius: 0.12, fill: { color: HEX.white },
      line: { color: HEX.line, width: 1 }, shadow: { type: "outer", color: "000000", opacity: 0.08, blur: 6, offset: 2, angle: 90 } });
    s.addShape(pres.shapes.OVAL, { x: x + 0.3, y: y + 0.3, w: 0.75, h: 0.75, fill: { color: HEX.soft }, line: { color: HEX.soft } });
    s.addImage({ data: img, x: x + 0.47, y: y + 0.47, w: 0.41, h: 0.41 });
    s.addText(h, { x: x + 1.2, y: y + 0.3, w: 2.55, h: 0.75, fontSize: 17, bold: true, color: C.text2, valign: "middle", margin: 0, isTextBox: true });
    s.addText(d, { x: x + 0.3, y: y + 1.2, w: 3.35, h: 1.0, fontSize: 14, color: C.text1, valign: "top", margin: 0, isTextBox: true });
  });
  s.addNotes(`Mention: these are the groups our scenarios are built around. We have not interviewed them yet — that is the first thing on our 3-week plan.`);

  // =====================================================================
  // 4. SCALE
  // =====================================================================
  pres.addSection({ title: "Scale" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Scale" });
  s.addText("How big is it — and why every hour matters", { placeholder: "title" });
  const stats = [
    ["729 crore", "passenger journeys on Indian Railways in 2024-25", "Official · Economic Survey 2025-26, Table 1.26 (7,293 million originating; includes suburban)"],
    ["50.6 crore", "e-tickets booked via IRCTC in 2024-25 (89.1 crore passengers)", "Official · IRCTC, Internet Ticketing page"],
    ["12.1%", "of scheduled Mail/Express trains on Northern Railway lost punctuality in Dec–Feb (≈2.7% cancelled)", "Official · Lok Sabha Starred Q.165, 11 Feb 2026 (winters 2021-22 to 2025-26)"],
  ];
  stats.forEach(([n, l, src], i) => {
    const x = 0.6 + i * 4.1;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.4, w: 3.9, h: 2.75, rectRadius: 0.12, fill: { color: HEX.navy }, line: { color: HEX.navy } });
    s.addText(n, { x: x + 0.3, y: 1.55, w: 3.3, h: 0.95, fontSize: 44, bold: true, color: HEX.orange, margin: 0, isTextBox: true });
    s.addText(l, { x: x + 0.3, y: 2.5, w: 3.3, h: 0.95, fontSize: 15, color: HEX.white, valign: "top", margin: 0, isTextBox: true });
    s.addText(src, { x: x + 0.3, y: 3.45, w: 3.3, h: 0.6, fontSize: 10, color: "B9C6D8", valign: "top", margin: 0, isTextBox: true });
  });
  // why it matters: time-based rules
  s.addText("Why timing matters: the rules are a clock", { x: 0.6, y: 4.4, w: 7.4, h: 0.4, fontSize: 18, bold: true, color: C.text2, margin: 0, isTextBox: true });
  const clock = [["> 3 h late", "Full fare back only if the TDR is filed before the train actually departs", "Rule 13(1), Refund Rules 2015"],
    ["< 8 h to go", "Cancelling a confirmed ticket returns nothing (announced April 2026 slabs)", "Govt publication; gazette text not yet found"],
    ["After chart", "Waitlisted e-ticket is refunded automatically — no need to cancel", "E-ticket rules (₹60 clerkage per passenger)"]];
  clock.forEach(([k, v, src], i) => {
    const y = 4.9 + i * 0.68;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y, w: 1.45, h: 0.55, rectRadius: 0.08, fill: { color: HEX.amberBg }, line: { color: HEX.orange, width: 1 } });
    s.addText(k, { x: 0.6, y, w: 1.45, h: 0.55, fontSize: 14, bold: true, color: HEX.orangeDk, align: "center", valign: "middle", margin: 0, isTextBox: true });
    s.addText([{ text: v, options: { fontSize: 14, color: HEX.ink, breakLine: true } }, { text: src, options: { fontSize: 10, color: HEX.muted } }],
      { x: 2.2, y: y - 0.04, w: 5.9, h: 0.64, valign: "middle", margin: 0, isTextBox: true });
  });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 8.5, y: 4.4, w: 4.2, h: 2.2, rectRadius: 0.12, fill: { color: HEX.soft }, line: { color: HEX.line } });
  s.addText([
    { text: "What nobody measures yet", options: { fontSize: 16, bold: true, color: HEX.navy, breakLine: true } },
    { text: "We found no official figure for how many passengers miss a connection or a refund deadline. We won't invent one — measuring it is part of our pilot.", options: { fontSize: 14, color: HEX.ink } },
  ], { x: 8.75, y: 4.6, w: 3.75, h: 1.85, valign: "top", margin: 0, paraSpaceAfter: 6, isTextBox: true });
  s.addNotes(`Sources:
- Economic Survey 2025-26, Statistical Appendix Table 1.26: passengers originating 2024-25 = 7,293 million.
- IRCTC Internet Ticketing page: FY 2024-25, 5,065 lakh e-tickets; 8,911 lakh passengers; 86.38% of reserved tickets.
- Lok Sabha Starred Question 165, answered 11.02.2026: Dec–Feb, ~2.7% of scheduled Mail/Express trains on Northern Railway cancelled due to fog; 12.1% lost punctuality (period 2021-22 to 2025-26).
- Rule 13(1), Railway Passengers (Cancellation of Ticket and Refund of Fare) Rules, 2015 (Indian Kanoon).
- April 2026 slabs: New India Samachar (PIB), 16-30 Apr 2026. Gazette text not located, so the app labels them "announced, not yet confirmed".
No official statistic exists for missed connections or missed refund deadlines — stated as such.`);

  // =====================================================================
  // 5. SOLUTION + PROTOTYPE + ARCHITECTURE
  // =====================================================================
  pres.addSection({ title: "Prototype" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Prototype" });
  s.addText("Built and working: from delay to next step", { placeholder: "title" });
  // 5-stage flow with features
  const stages = [
    [ic.search, "Detect", "Journey Digital Twin · Disruption detection · Station transfer check"],
    [ic.balance, "Know rights", "Versioned rules engine · Rights Wallet · Rights Clock"],
    [ic.random, "Simulate", "What-If simulator (7 scenarios) · Resilience score"],
    [ic.route, "Compare", "Alternative routes · Explainable ranking · Family Guardian"],
    [ic.check, "Act", "Official steps · Hindi/English voice + text · Offline card · Station reports"],
  ];
  stages.forEach(([img, h, d], i) => {
    const x = 0.6 + i * 2.46;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.25, w: 2.26, h: 1.55, rectRadius: 0.1, fill: { color: HEX.soft }, line: { color: HEX.soft } });
    s.addShape(pres.shapes.OVAL, { x: x + 0.18, y: 1.4, w: 0.5, h: 0.5, fill: { color: HEX.navy }, line: { color: HEX.navy } });
    s.addImage({ data: img, x: x + 0.3, y: 1.52, w: 0.26, h: 0.26 });
    s.addText(`${i + 1}. ${h}`, { x: x + 0.78, y: 1.4, w: 1.4, h: 0.5, fontSize: 16, bold: true, color: C.text2, valign: "middle", margin: 0, isTextBox: true });
    s.addText(d, { x: x + 0.18, y: 1.98, w: 1.95, h: 0.78, fontSize: 11, color: C.text1, valign: "top", margin: 0, isTextBox: true });
    if (i < 4) s.addImage({ data: ic.arrow, x: x + 2.29, y: 1.9, w: 0.15, h: 0.15 });
  });
  // architecture (left)
  s.addText("How it works", { x: 0.6, y: 3.0, w: 4, h: 0.35, fontSize: 16, bold: true, color: C.text2, margin: 0, isTextBox: true });
  const arch = [
    ["Passenger app", "React PWA · Hindi/English · voice · offline", HEX.navy, HEX.white],
    ["FastAPI backend", "REST APIs · validation · security", "2D5A8C", HEX.white],
    ["Digital Twin + Detector", "every leg and change of train", HEX.soft, HEX.ink],
    ["Rules & Rights Engine", "versioned, cited, exact paise", HEX.amberBg, HEX.ink],
    ["What-If + Route search", "Connection Scan Algorithm", HEX.soft, HEX.ink],
    ["Ranking + Explanation", "why #1 · AI never sets numbers", HEX.greenBg, HEX.ink],
  ];
  arch.forEach(([h, d, fill, col], i) => {
    const y = 3.42 + i * 0.58;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y, w: 4.95, h: 0.5, rectRadius: 0.06, fill: { color: fill }, line: { color: fill === HEX.soft ? HEX.line : fill } });
    s.addText([{ text: h + "  ", options: { bold: true, fontSize: 13, color: col } }, { text: d, options: { fontSize: 11, color: col } }],
      { x: 0.75, y, w: 4.7, h: 0.5, valign: "middle", margin: 0, isTextBox: true });
  });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.7, y: 3.42, w: 1.55, h: 3.42, rectRadius: 0.08, fill: { color: HEX.white },
    line: { color: HEX.orange, width: 1.25, dashType: "dash" } });
  s.addText([{ text: "Data source", options: { bold: true, fontSize: 12, color: HEX.orangeDk, breakLine: true } },
    { text: "Simulated trains (90xxx) today.", options: { fontSize: 11, color: HEX.ink, breakLine: true } },
    { text: "Empty slot for authorised NTES / IRCTC data later.", options: { fontSize: 11, color: HEX.ink, breakLine: true } },
    { text: "No scraping. No live integration claimed.", options: { fontSize: 11, color: HEX.red } }],
    { x: 5.8, y: 3.52, w: 1.38, h: 3.25, valign: "top", margin: 0, paraSpaceAfter: 6, isTextBox: true });
  // screenshots (right)
  const ph = 3.5, py = 3.15;
  let px = 7.5;
  [["02_twin_missed_connection.png", "Twin: change not possible"], ["03_options_recommendation.png", "Why option #1"],
    ["05_whatif.png", "What-If: options lost by waiting"]].forEach(([f, cap]) => {
    const w = phone(s, f, px, py, ph, cap);
    s.addText(cap, { x: px - 0.1, y: py + ph + 0.1, w: w + 0.2, h: 0.25, fontSize: 10, color: C.accent6, align: "center", margin: 0, isTextBox: true });
    px += w + 0.2;
  });
    s.addNotes(`Real screenshots from the running prototype (local, simulated data).
Flow: Detect → Know rights → Simulate → Compare → Act.
Ten main features: Digital Twin, What-If simulator, Family Guardian, Offline Guardian, Station Transfer Intelligence, Rights Wallet, Hindi/English voice+text assistant, Resilience score (experimental), counterfactual "why", Community reports (unverified). Plus disruption detection, Rights Clock, alternative ranking from the original build.
Evidence: 192 backend + 15 end-to-end tests passing (run 13 Nov 2026).`);

  // =====================================================================
  // 6. FEEDBACK / VALIDATION
  // =====================================================================
  pres.addSection({ title: "Feedback" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Feedback" });
  s.addText("Feedback so far: tests, audit and rule checks", { placeholder: "title" });
  const cols = [
    [ic.flask, HEX.green, "Tested", [
      "192 backend tests pass (refund maths, deadlines, boundaries, every API)",
      "15 end-to-end tests on a phone-size screen",
      "10 passenger scenarios simulated: 3-h delay, missed connection, waitlist, cancellation, family, stale data, offline, Hindi…"]],
    [ic.shield, HEX.navy, "Reviewed & fixed", [
      "Security and trust audit: 1 critical + 6 other issues fixed, each with a test",
      "Refunds from rules not yet officially confirmed are labelled, never shown as certain",
      "AI can never invent a number; app works with AI off"]],
    [ic.gavel, HEX.orangeDk, "Checked against sources", [
      "3-hour TDR rule: Rule 13(1), Refund Rules 2015 ✓",
      "April 2026 slabs: govt publication found, gazette text not yet ⚠",
      "Missed-connection TDR deadline: still unverified ⚠"]],
    [ic.ear, HEX.red, "Not validated yet", [
      "No passenger interviews or user tests yet — we say so openly",
      "Voice and offline not yet tried on real phones",
      "Next: 10–15 travellers try the fog scenario; we measure time to decide and refund understanding"]],
  ];
  cols.forEach(([img, col, h, items], i) => {
    const x = 0.6 + i * 3.08;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.3, w: 2.9, h: 4.55, rectRadius: 0.12, fill: { color: HEX.white },
      line: { color: HEX.line }, shadow: { type: "outer", color: "000000", opacity: 0.08, blur: 6, offset: 2, angle: 90 } });
    s.addShape(pres.shapes.OVAL, { x: x + 0.25, y: 1.5, w: 0.6, h: 0.6, fill: { color: col }, line: { color: col } });
    s.addImage({ data: img, x: x + 0.4, y: 1.65, w: 0.3, h: 0.3 });
    s.addText(h, { x: x + 0.95, y: 1.5, w: 1.85, h: 0.6, fontSize: 17, bold: true, color: col, valign: "middle", margin: 0, isTextBox: true });
    s.addText(items.map((t, k) => ({ text: t, options: { bullet: true, breakLine: k < items.length - 1 } })),
      { x: x + 0.2, y: 2.3, w: 2.55, h: 3.4, fontSize: 14, color: HEX.ink, valign: "top", margin: 0, paraSpaceAfter: 8, isTextBox: true });
  });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 6.1, w: 12.1, h: 0.6, rectRadius: 0.08, fill: { color: HEX.soft }, line: { color: HEX.soft } });
  s.addText("Honest status: working prototype on simulated data. No railway partnership, no live integration, no user ratings yet.",
    { x: 0.8, y: 6.1, w: 11.8, h: 0.6, fontSize: 15, bold: true, color: HEX.navy, valign: "middle", margin: 0, isTextBox: true });
  s.addNotes(`Do NOT present any of this as passenger reviews. Feedback so far is technical: automated tests, a security/trust audit, and checking rules against legal and government sources. Passenger testing is the first roadmap step.`);

  // =====================================================================
  // 7. ROADMAP
  // =====================================================================
  pres.addSection({ title: "Roadmap" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Roadmap" });
  s.addText("What happens next", { placeholder: "title" });
  const road = [
    ["Next 3 weeks", "Prove it helps", ["Test the fog scenario with 10–15 real travellers", "Try voice + offline on real Android phones", "Fix what confuses people", "Find official text for the 2 unverified rules", "Deploy a public demo link"], "Goal: passengers pick the right option faster"],
    ["Next 3 months", "Make it real-world ready", ["Apply for authorised railway data access (no scraping)", "Cover more disruptions: diversions, short termination", "Small pilot with a student travel group", "Better alternatives with real timetables"], "Goal: first pilot with consenting users"],
    ["Next 12 months", "Grow responsibly", ["More Indian languages", "Wider disruption coverage", "Seek partnerships with railway services", "Scalable, monitored deployment", "Explore a 'my journey changed' button inside existing railway apps"], "Goal: one trusted place to decide what's next"],
  ];
  road.forEach(([when, h, items, goal], i) => {
    const x = 0.6 + i * 4.1;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.3, w: 3.9, h: 5.55, rectRadius: 0.12, fill: { color: i === 0 ? HEX.navy : HEX.soft },
      line: { color: i === 0 ? HEX.navy : HEX.soft } });
    const fg = i === 0 ? HEX.white : HEX.ink, acc = i === 0 ? HEX.orange : HEX.orangeDk;
    s.addText(when, { x: x + 0.3, y: 1.5, w: 3.3, h: 0.4, fontSize: 14, bold: true, color: acc, charSpacing: 1, margin: 0, isTextBox: true });
    s.addText(h, { x: x + 0.3, y: 1.9, w: 3.3, h: 0.55, fontSize: 22, bold: true, color: i === 0 ? HEX.white : HEX.navy, margin: 0, isTextBox: true });
    s.addText(items.map((t, k) => ({ text: t, options: { bullet: true, breakLine: k < items.length - 1 } })),
      { x: x + 0.3, y: 2.65, w: 3.35, h: 3.1, fontSize: 14, color: fg, valign: "top", margin: 0, paraSpaceAfter: 7, isTextBox: true });
    s.addText(goal, { x: x + 0.3, y: 5.95, w: 3.35, h: 0.7, fontSize: 13, italic: true, bold: true, color: acc, valign: "middle", margin: 0, isTextBox: true });
  });
  s.addNotes(`No partnerships or API access exist today — the roadmap says "apply for" and "seek", not "have".`);

  // =====================================================================
  // 8. CLOSING (statement + official sponsor screen)
  // =====================================================================
  pres.addSection({ title: "Closing" });
  s = pres.addSlide({ masterName: "DARK", sectionTitle: "Closing" });
  s.addText("When a train journey goes wrong, every minute matters.", { x: 0.6, y: 1.0, w: 6.0, h: 1.4, fontSize: 30, bold: true,
    color: HEX.white, valign: "top", margin: 0, isTextBox: true });
  s.addText("Agla Kadam helps passengers understand their rights, compare their options, and make their next move with confidence.",
    { x: 0.6, y: 2.5, w: 5.9, h: 1.3, fontSize: 18, color: "C9D6E8", valign: "top", margin: 0, isTextBox: true });
  s.addText("AGLA KADAM", { x: 0.6, y: 4.0, w: 5.5, h: 0.6, fontSize: 30, bold: true, color: HEX.orange, charSpacing: 3, margin: 0, isTextBox: true });
  s.addText("Aditi · SBI Youth Ideathon 2026 · Think Ticketing, Think IRCTC", { x: 0.6, y: 4.6, w: 6.0, h: 0.4, fontSize: 14,
    color: HEX.white, margin: 0, isTextBox: true });
  s.addImage({ data: ic.github, x: 0.6, y: 5.25, w: 0.3, h: 0.3 });
  s.addText("github.com/aditiraj0129-netizen/agla-kadam", { x: 1.0, y: 5.2, w: 5.4, h: 0.4, fontSize: 14, color: HEX.white,
    margin: 0, valign: "middle", isTextBox: true, objectName: "GitHub link (check after pushing)" });
  s.addText("Working prototype · simulated railway data · not an official IRCTC app", { x: 0.6, y: 5.75, w: 6.0, h: 0.35, fontSize: 12,
    color: "8DA2BF", margin: 0, isTextBox: true });
  s.addImage({ path: "/home/claude/deck/tpl-5.png", x: 6.95, y: 2.1, w: 5.95, h: 5.95 * 619 / 1100, objectName: "Official sponsor closing screen",
    altText: "SBI Youth Ideathon 2026 official closing screen: Thank you to our sponsors" });
  s.addNotes(`[1:50–2:00] Face on camera for the closing line. Check the GitHub link works before recording.`);

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
