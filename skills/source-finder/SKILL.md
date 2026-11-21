---
name: source-finder
description: Find GTA 6 gameplay you may legally reuse - Creative Commons licensed, English, no watermark. Use before moment-finder whenever the user wants clips "without watermark", "reusable", "safe to repost", or does not name a source video.
---

# Source finder

Run:

`python "${CLAUDE_PLUGIN_ROOT}/scripts/sources.py" --top 10`

It searches YouTube with the Creative Commons filter, re-checks every video's license, keeps English, 1 to 30 minute
gameplay videos (talk, drama, glitch, leak and review titles are dropped), then scans the top ones for watermarks:
static logos, burned-in text or facecams that stay still while the game moves. Output: `sources.md`, `sources.json`
and a `contact-sheet.jpg` per scanned video in `jobs/_sources/<id>/`.

Then:

1. Open the contact sheet of every `clean: yes` row and confirm by eye: pure gameplay, no channel logo, no facecam,
   no subscribe banner. The game HUD (minimap, wanted stars, money) is fine. The last row of the sheet is the
   static-graphics mask: it should be black.
2. Drop anything that is not GTA 6 footage.
3. Pass the best 2 or 3 to `moment-finder`.

If yt-dlp says "Sign in to confirm you're not a bot", YouTube is rate limiting: wait 10 to 30 minutes and retry.
Do not read browser cookies without the user's explicit OK.

CC BY requires credit: `cut.py` writes the credit line into the post text next to every exported clip.
