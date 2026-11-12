# Live product demo — Agla Kadam (local, no internet needed)

**Scenario:** "Fog: connection at Prayagraj at risk" (PNR `8100000004`).
It shows every required step: journey → disruption → rights and deadline → What-If → recommendation → why → Wallet.
Everything runs on your laptop, and the data is simulated, so it doesn't depend on the internet or any railway API.

## Before you start (5 minutes before)

```bash
# Terminal 1
cd ~/Downloads/agla-kadam/backend && source .venv/bin/activate
uvicorn app.main:app
# Terminal 2
cd ~/Downloads/agla-kadam/frontend && npm run build
```

1. Open **http://localhost:8000** in Chrome. Press `Cmd+Option+I` → device toolbar → "Pixel 7" (phone size). Zoom 100%.
2. In a second tab, open **http://localhost:8000/#/presenter**. Pick each journey and press **Reset scenario**.
3. Turn off notifications. Close other tabs.

## The demo (about 75 seconds; the 2-minute video uses the first 25 seconds of it)

| # | Click | You should see | Say |
| --- | --- | --- | --- |
| 1 | Home → **"Fog: connection at Prayagraj at risk"** | My journey. Alert "Your connection at Prayagraj Jn is at risk." | "A fog delay on a two-train journey." |
| 2 | Look at **Live journey picture** | "Journey broken: act now"; 90203 "Likely missed"; red box "Change not possible · −1h 25m to spare · Must reach by 05:45" | "The digital twin knows my change of train is no longer possible." |
| 3 | Tap the **Options** tab | Rights Clock "Decide by 09:15"; green box "Why this is first"; #1 "Take another train and file a TDR", **₹455 back · if approved**, Act by **09:15 (deadline not yet officially confirmed)** | "Ranked options, the money, the rule and the deadline. Notice it says 'if approved' and that this deadline isn't officially confirmed yet. We never guarantee." |
| 4 | Point at **"If things change"** | "If you wait 30 min: nothing changes" | "It also tells me what happens if I wait." |
| 5 | Tap **What-If** → drag **How long you wait** to **7h 0m** | "Wait, then decide (7h 0m)" card shows "Options lost by waiting" | "If I wait seven hours, my best train is gone. Same rules engine, nothing guessed." |
| 6 | Point at **Cancel the ticket now** | "₹455 lost" | "Cancelling now would cost me money." |
| 7 | Tap **Wallet** → open **Rule** on the TDR card | Rule id, version, effective date, source, "Still uncertain" line | "Every rupee shows its rule, version and source." |
| 8 | Tap **I filed it** | Stage changes to "Filed by you"; History shows "Claim update" | "And it tracks my claim, step by step." |
| 9 (optional) | Tap **हिं** | Same screen in Hindi | "And in Hindi." |

**Recommended bonus, if you have 15 extra seconds:** open the presenter tab and pick "Edge case: delay hovering
around 3 hours". Set the delay to **170** and press *Send delay update*. On the phone view (Options), the TDR plan
disappears within 3 seconds: "the rights change live as the delay changes".

## If something goes wrong

| Problem | Fix |
| --- | --- |
| Blank page / "Can't reach the server" | Terminal 1 stopped: run `uvicorn app.main:app` again |
| "Address already in use" | `lsof -ti:8000 \| xargs kill`, then start again |
| Numbers differ from this script | The journey was changed. Reset it on the presenter page |
| Presenter says "Presenter token required" | Only on a deployment with `DEMO_TOKEN`; type the token in the presenter page |
| Anything else | Switch to the backup |

## Backup plan (no localhost)

1. **Screenshots:** `submission/screenshots/` has real screenshots of every step (02 twin, 03 options/why, 04 Rights Clock,
   05 What-If, 06 Wallet, 07 Hinglish assistant, 08 family, 09 offline card, 10 Hindi). Put them in a slideshow in order.
2. **Recorded clip:** record steps 1–8 once while everything works (macOS: `Cmd+Shift+5` → Record selected portion).
   Keep the file on the desktop and on a USB stick.
3. **The deck itself:** slide 5 already shows three real screens.
