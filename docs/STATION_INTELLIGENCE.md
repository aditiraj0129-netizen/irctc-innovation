# Station Intelligence — Station Navigator

**What it answers for a passenger:** "Which platform? How do I get there? Can I make my connection? Where is the
washroom / exit / metro?" — with an honest label on every answer.

Everything in this feature is a **prototype on simulated railway data and schematic maps**. Nothing here is an
official IRCTC or Indian Railways service.

## 1. What the passenger sees

| Screen | How to open | What it shows |
| --- | --- | --- |
| **Station** tab of a journey | Journey → *Station* tab, or `#/station/<journey id>` | Timeline (your train → expected arrival → arrival platform → walk → connecting platform → departure), a verdict (Comfortable / Possible but tight / High risk / Unlikely / Cannot assess), "Prepare to get off…" banner (only when data supports it), route directions, schematic map, "Enter the platform you see on the board" form, location picker, profile picker (Fastest / No stairs (lifts) / Fewer level changes) |
| **Stations** (find mode) | Bottom/side nav → *Stations*, or `#/stations/<CODE>?at=PF4` | "I'm at the station. Help me find something": pick a station, set your location, search facilities (exit, washroom, tickets, metro, …), route with steps and alternatives |
| **Copilot** | Ask "Which platform does my connecting train leave from?", "How do I get from platform 4 to 12 without stairs?", "Where is the nearest washroom?" | Answers built only from tool results (see §6) |

## 2. Platform intelligence — one status per platform

| Status | Where it comes from | Trusted for "Comfortable"? |
| --- | --- | --- |
| **Confirmed** | An observation marked confirmed (in the demo: simulated station-board feed) | Yes, while fresh |
| **Reported** | An observation from a report — e.g. the passenger typed what the board says | Yes, while fresh |
| **Scheduled** | `app/data/platforms.yaml` (simulated timetable platform) | No |
| **Predicted** | Rule: the same platform on **at least 5 of the last 7 runs** (simulated history) | No |
| **Unknown** | Nothing above | No |

- An observation older than **45 min** is **stale**: shown with its age and a "check boards" warning, never as live.
- A platform change keeps `changed_from` ("Platform 16 — changed from 12") and the connection is recalculated.
- If no live provider is connected, the app shows exactly:
  **"Live platform information is currently unavailable. Please verify station display boards and announcements."**
- The real provider (`OfficialPlatformProvider`) raises `ProviderNotConfigured` — no public live platform API was found (see `STATION_DATA_SOURCES.md`).
- **An unknown platform is never turned into a guessed one.** With an unknown platform the app invents no route and says *Cannot assess*.

## 3. Stations covered and why

| Station | Why chosen | Map type |
| --- | --- | --- |
| **New Delhi (NDLS)** | Busiest connection hub in the demo journeys (Bhopal → New Delhi → Chandigarh); two well-documented sides (Paharganj, Ajmeri Gate), two FOBs, metro on Ajmeri Gate side | Through station, schematic |
| **Howrah (HWH)** | Very large terminus with a clearly documented split: Old Complex (1–15) and New Complex (17–23), Howrah Metro | Terminus, schematic |
| **Mumbai CSMT** | Terminus with a documented split: suburban platforms (1–7) and long-distance platforms (8–18) with a separate entrance | Terminus, schematic |

Chosen because **public facts exist for their layout** (platform count, sides, complexes). Exact geometry,
FOB positions, lift positions and most facility positions are **not public**, so they are marked *illustrative*.

## 4. Verification level on every element

| Level | Meaning | Example |
| --- | --- | --- |
| `VERIFIED_PUBLIC` | Stated by a cited public source | NDLS has 16 platforms; Paharganj and Ajmeri Gate sides |
| `REPORTED` | From a secondary or older source | NDLS two FOBs (2010 article); HWH Old Complex entrance; CSMT D'Mello Road entrance |
| `ILLUSTRATIVE` | Placed by us to make a usable schematic; **not a real position** | Platform pairing, most facility positions, lift positions |

The map caption always says: *"Schematic map — not an official station map, not to scale."*
Every route carries `confidence: SCHEMATIC_DEMO` and the screen says *"not a verified station route."*

## 5. Where am I? (indoor positioning)

Order of preference — no GPS:
1. **Manual selection** — "Platform 4", "Paharganj side entrance", etc.
2. **QR-style link** — `#/stations/NDLS?at=PF2` (a sticker or board could carry this link). The screen says
   "Location from a link (like a QR code at the station)". These links are **demo links** — no QR codes exist at stations.
3. Default: in a journey, your arrival platform (labelled "your arrival platform").

We **do not** ask for location permission and **do not** claim phone GPS can find your platform.
The chosen location stays in the browser session only (find mode uses `sessionStorage`); it is never sent to an LLM or stored on the server.

## 6. Copilot station questions

Intents: `PLATFORM_ARRIVAL`, `PLATFORM_DEPARTURE`, `STATION_ROUTE`, `STATION_FACILITY` (EN and HI).
Allowlisted read-only tools: `get_platforms`, `station_route`, `find_facility`.
The LLM never invents platforms, running status, facility locations, walking distances, live availability or railway
rules. Answers are written from templates filled by tool results; if a tool has no data, the answer says so
(including the unavailable-platform message). Stale running data does not block station answers, but platform
age is shown.

## 7. What is real, simulated, estimated, unavailable

| Data | Status |
| --- | --- |
| Platform counts, station sides, complexes | Real public facts (cited) |
| Platform pairing, FOB/lift/facility positions, distances | Illustrative / estimated |
| Walking times | Estimated (speed ranges, see architecture doc) |
| Platform numbers for demo trains, platform changes | Simulated |
| Live platform feed, lift working status | **Unavailable** — always shown as unknown |

See also: [STATION_NAVIGATION_ARCHITECTURE.md](STATION_NAVIGATION_ARCHITECTURE.md), [STATION_DATA_SOURCES.md](STATION_DATA_SOURCES.md).
