# gtavi-claudecode: defaults for this fork

Run everything with the project venv: `.venv/bin/python scripts/<name>.py`. ffmpeg/ffprobe are found in
`.tools/ffmpeg-portable/bin` automatically when they are not on PATH.

## Standing preferences (owner of this fork)

- **Global, English.** Sources, transcripts (`GTAVI_LANG=en`), hooks, titles and post captions are all English.
- **Only reusable, watermark-free sources.** Default to YouTube videos licensed Creative Commons Attribution, found and
  scanned with `scripts/sources.py` (skill `source-finder`). Check the contact sheets by eye before cutting.
  Do not clip streamers or standard-license videos unless the user names them or a campaign allows it.
- **Output folder.** Every finished clip is copied by `cut.py` to `~/Downloads/gtavi-clips/<YYYY-MM-DD>/<NN>-<hook-slug>/` (one folder per clip)
  holding the `.mp4`, `post.txt` (caption, credit line required by CC BY, hashtags), `cover.jpg` and `source.json`. Override with `GTAVI_EXPORT_DIR`.
- **Commit and push** code improvements to `origin main` (this fork) after a run, without asking.
- Nothing is ever uploaded to social platforms automatically.

## Default run ("make clips")

1. `scripts/sources.py --top 10` -> read `sources.md`, open contact sheets of clean rows, pick the 2 to 3 best.
2. `scripts/moments.py <url> --top 6 --min 12 --max 30` per source -> read `jobs/<id>/candidates.md`.
3. Write 3 English hooks per moment (skill `hook-writer`), pick one.
4. `scripts/cut.py jobs/<id> --pick <n> --layout blur --hook "..." --caption "..."` (`fill` when the action is centred).
5. `scripts/check.py jobs/<id>/edits/clip_<n>.mp4` and look at a few frames of the result.
6. Report the files in `~/Downloads/gtavi-clips/<date>/`.

If YouTube answers "Sign in to confirm you're not a bot", rerun with the browser's YouTube cookies:
`GTAVI_COOKIES=firefox:~/snap/firefox/common/.mozilla/firefox` (snap Firefox on this machine; `chrome` needs
`secretstorage`). Without cookies, wait 10 to 30 minutes and retry. Do not run `sources.py` many times in a row.
