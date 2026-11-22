"""Shared helpers: paths, tool lookup, yt-dlp and ffmpeg wrappers."""
import hashlib, json, os, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(os.environ.get("CLIP_DESK_HOME", Path.cwd()))
JOBS = ROOT / "jobs"
REPO = Path(__file__).resolve().parent.parent
# Finished clips are copied here (mp4 + post caption with credit). Override with GTAVI_EXPORT_DIR.
EXPORT_DIR = Path(os.environ.get("GTAVI_EXPORT_DIR", Path.home() / "Downloads" / "gtavi-clips"))
# Language of sources, transcripts, hooks and captions. The page targets a global, English-speaking audience.
LANG = os.environ.get("GTAVI_LANG", "en")
LOCAL_BIN = [REPO / ".tools" / "ffmpeg-portable" / "bin", REPO / ".tools" / "bin"]


def tool(name):
    p = shutil.which(name)
    if not p:  # portable builds unpacked by the setup skill (no root needed)
        for b in LOCAL_BIN:
            for cand in (b / name, b / f"{name}.exe"):
                if cand.exists():
                    p = str(cand); break
            if p:
                break
    if not p:
        sys.exit(f"{name} not found. Run the setup skill first (it installs ffmpeg and yt-dlp).")
    return p


def run(cmd, check=True, capture=False):
    r = subprocess.run(cmd, check=False, text=True, encoding="utf-8", errors="replace",
                       stdout=subprocess.PIPE if capture else None, stderr=subprocess.PIPE if capture else None)
    if check and r.returncode != 0:
        msg = (r.stderr or "")[-1500:] if capture else ""
        sys.exit(f"command failed ({r.returncode}): {' '.join(map(str, cmd))[:200]}\n{msg}")
    return r


def ytdlp_base():
    import importlib.util
    exe = [sys.executable, "-m", "yt_dlp"] if importlib.util.find_spec("yt_dlp") else [tool("yt-dlp")]
    base = exe + ["--no-warnings", "--no-progress"]
    if not shutil.which("ffmpeg"):  # yt-dlp needs ffmpeg to merge video + audio
        base += ["--ffmpeg-location", str(Path(tool("ffmpeg")).parent)]
    if sys.platform == "win32":
        base += ["--compat-options", "no-certifi"]  # use the Windows certificate store
    if not shutil.which("deno") and shutil.which("node"):  # YouTube needs a JS runtime; yt-dlp only tries deno by default
        base += ["--js-runtimes", "node"]
    if os.environ.get("GTAVI_COOKIES"):  # e.g. "firefox" or "chrome": beats "Sign in to confirm you're not a bot"
        base += ["--cookies-from-browser", os.environ["GTAVI_COOKIES"]]
    return base


def ytdlp_json(url, extra=()):
    r = run(ytdlp_base() + ["-J", *extra, url], capture=True)
    return json.loads(r.stdout)


def is_url(s):
    return bool(re.match(r"https?://", s))


def job_dir(src):
    key = hashlib.sha1(src.encode()).hexdigest()[:8]
    stem = re.sub(r"[^a-z0-9]+", "-", Path(src).stem.lower() if not is_url(src) else src.split("v=")[-1].split("/")[-1].lower())[:24].strip("-")
    d = JOBS / f"{stem or 'job'}-{key}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def ffprobe(path):
    r = run([tool("ffprobe"), "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height,r_frame_rate",
             "-of", "json", str(path)], capture=True)
    return json.loads(r.stdout)


def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=_plain), encoding="utf-8")


def _plain(o):
    """numpy scalars (bool_, float32, int64...) and arrays -> plain Python for JSON."""
    if hasattr(o, "item") and getattr(o, "ndim", 0) == 0:
        return o.item()
    if hasattr(o, "tolist"):
        return o.tolist()
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
