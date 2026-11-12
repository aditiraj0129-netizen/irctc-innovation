# Final submission checklist — deadline 16 November 2026

## A. Fill in before recording

- [ ] Slide 1: type your **UID**, **team name** and **college** in the grey fields. Optionally replace the navy
      "Agla Kadam" panel with a team photo (the official template asks for one).
- [ ] Slide 8: the GitHub link must open your public repo (see section C). If you use a different repo name, edit it.
- [ ] Open the `.pptx` in PowerPoint or Keynote once. The deck uses Calibri; if Keynote substitutes a font, check
      that no text wraps badly on slides 5 and 6.

## B. Verify the app (on your Mac)

```bash
cd ~/Downloads/agla-kadam/backend && source .venv/bin/activate && pytest          # expect 192 passed
cd ../frontend && npm run build && npm run test:e2e                                 # expect 15 passed
```

- [ ] Both pass. If not, don't quote the numbers on slide 6 until they do.
- [ ] Walk through `docs/LIVE_DEMO_SCRIPT.md` once.

## C. Push to GitHub (step by step)

Nothing has been pushed yet; there is no remote configured. Your existing work is safe: these steps only *add* a remote.

1. On github.com → **New repository** → name `agla-kadam` → **Public** → do **not** add a README, .gitignore or licence
   (the project already has them; adding them creates a conflict).
2. In Terminal:

```bash
cd ~/Downloads/agla-kadam
git status                         # should say "nothing to commit, working tree clean"
git log --oneline | head -3        # you should see the latest commits
git branch -M main                 # rename master -> main (GitHub's default)
git remote add origin https://github.com/aditiraj0129-netizen/agla-kadam.git
git push -u origin main
```

3. When asked for a password, use a **Personal Access Token** (GitHub → Settings → Developer settings → Tokens),
   not your account password.
4. Open `https://github.com/aditiraj0129-netizen/agla-kadam` in a private window and check that the README shows.
5. **Before pushing, check nothing secret is included:** `git ls-files | grep -i "\.env$"` must print nothing
   (only `.env.example` should be tracked).

If `git push` says "rejected (fetch first)", you created the repo with a README. Don't force-push; ask for help.

## D. Record the video

- [ ] Follow `docs/FINAL_VIDEO_SCRIPT.md` Version A. Time it: under 2:00.
- [ ] Face visible on slides 1 and 8.
- [ ] App shown for about 25 seconds (twin → options → What-If → wallet).
- [ ] "Simulated data" strip visible whenever the app is on screen.
- [ ] Every amount said with "if approved" where the screen says so.

## E. Truth check (every claim)

| Claim | Where it's backed |
| --- | --- |
| 192 backend + 15 E2E tests pass | `docs/TEST_REPORT.md` (re-run in step B) |
| 729 crore journeys in 2024-25 | Economic Survey 2025-26, Statistical Appendix Table 1.26 (7,293 million) |
| 50.6 crore IRCTC e-tickets, 89.1 crore passengers (2024-25) | IRCTC Internet Ticketing page |
| 12.1% of NR Mail/Express trains lost punctuality in Dec–Feb; ≈2.7% cancelled | Lok Sabha Starred Q.165, 11 Feb 2026 |
| TDR must be filed before actual departure for > 3 h delay | Refund Rules 2015, Rule 13(1) |
| < 8 h → no refund on cancelling a confirmed ticket | April 2026 slabs: govt publication; gazette text not found → labelled "announced" |
| No passenger feedback yet | Stated on slide 6 and in the script |
| No live IRCTC/NTES integration, simulated trains | Footer on every content slide; slide 5 data-source box |

## F. Upload

- [ ] Final video watched once start to end with sound.
- [ ] File name e.g. `AglaKadam_<UID>_pitch.mp4`.
- [ ] Use the submission link the organisers sent you for the 16 Nov deadline (the PDF's 10 Nov link/date is outdated).
