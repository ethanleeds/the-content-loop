#!/usr/bin/env python3
"""Measure how a creator cuts, and how you cut, with the same ruler.

    python scripts/teardown.py @hormozi --limit 20
    python scripts/teardown.py @yourhandle --limit 20 --label mine
    python scripts/teardown.py --urls urls.txt --label hormozi

Downloads with yt-dlp, finds every cut with PySceneDetect, and reads the spoken
hook with faster-whisper when it is installed. Writes one CSV row per video and
prints the summary.

It measures the difference between two creators. It does not explain it. Whether
closing a gap moves views is the Loop Ledger's job (vault/Loop-Ledger.md).
"""
import argparse, csv, json, os, shutil, statistics, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / ".teardown"


def have(cmd):
    return shutil.which(cmd) is not None


def fetch(target, limit, workdir, cookies_from, strict=True, cookies=""):
    """Pull up to `limit` videos. Instagram needs the browser cookies; TikTok does not.
    With strict off, a link that will not download is reported and skipped, so
    one deleted reel does not end a batch of sixty."""
    if not have("yt-dlp"):
        sys.exit("yt-dlp is not on PATH. pip install yt-dlp")
    if target.startswith("@"):
        url = f"https://www.tiktok.com/{target}"
    else:
        url = target
    cmd = ["yt-dlp", "-q", "--no-warnings", "--playlist-end", str(limit),
           "-f", "mp4", "-o", str(workdir / "%(id)s.%(ext)s"),
           "--write-info-json", url]
    if cookies:
        cmd += ["--cookies", cookies]
    elif cookies_from:
        cmd += ["--cookies-from-browser", cookies_from]
    before = set(workdir.glob("*.mp4"))
    r = subprocess.run(cmd, capture_output=True, text=True)
    files = sorted(set(workdir.glob("*.mp4")) - before) if not strict else sorted(workdir.glob("*.mp4"))
    if not files:
        if strict:
            sys.exit("nothing downloaded.\n" + (r.stderr or "")[-1200:])
        print(f"      could not download {target}: {(r.stderr or 'no error text').strip().splitlines()[-1][:160]}")
    return files


def cuts(path):
    """Every shot boundary, in seconds. detect-adaptive handles handheld motion
    better than detect-content, which is most of short-form."""
    from scenedetect import open_video, SceneManager, AdaptiveDetector
    video = open_video(str(path))
    sm = SceneManager()
    sm.add_detector(AdaptiveDetector())
    sm.detect_scenes(video, show_progress=False)
    scenes = sm.get_scene_list()
    if not scenes:
        return [], float(video.duration.seconds)
    starts = [s[0].seconds for s in scenes]
    return starts, float(scenes[-1][1].seconds)


def hook(path, seconds=6.0):
    """First words spoken. Optional: no faster-whisper means no hook column,
    and the pacing numbers still stand."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None
    model = WhisperModel("small.en", device="cpu", compute_type="int8")
    segs, _ = model.transcribe(str(path), beam_size=5, word_timestamps=False)
    words = []
    for s in segs:
        if s.start > seconds:
            break
        words += s.text.split()
    return " ".join(words).strip()


def sheet(path, starts, dur, folder, n=9):
    """One image per video: a frame from the middle of each of the first nine
    shots, tiled 3x3. It is how a session sees the caption font, where the
    text sits and how tight the framing is, without opening the video."""
    if not have("ffmpeg") or not starts:
        return ""
    folder.mkdir(parents=True, exist_ok=True)
    bounds = list(zip(starts, starts[1:] + [dur]))[:n]
    tmp = Path(tempfile.mkdtemp(prefix="sheet-"))
    for i, (a, b) in enumerate(bounds):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{(a + b) / 2:.2f}", "-i", str(path),
                        "-frames:v", "1", "-vf", "scale=360:-2", str(tmp / f"f{i:02d}.jpg")])
    out = folder / (path.stem + ".jpg")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "1", "-i", str(tmp / "f%02d.jpg"),
                    "-vf", "tile=3x3:padding=4", "-frames:v", "1", str(out)])
    # A second grid spread evenly over the whole video, for captions and text
    # on screen, which change on their own clock rather than on the cuts.
    for f in tmp.glob("*.jpg"):
        f.unlink()
    for i in range(n):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{dur * (i + 0.5) / n:.2f}", "-i", str(path),
                        "-frames:v", "1", "-vf", "scale=360:-2", str(tmp / f"f{i:02d}.jpg")])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "1", "-i", str(tmp / "f%02d.jpg"),
                    "-vf", "tile=3x3:padding=4", "-frames:v", "1", str(folder / (path.stem + "-time.jpg"))])
    shutil.rmtree(tmp, ignore_errors=True)
    return str(out) if out.exists() else ""


def loudness(path):
    """Integrated loudness, LUFS. Platforms normalise near -14; a hot mix sits
    louder. No audio track reads as blank."""
    if not have("ffmpeg"):
        return ""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True)
    import re
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr or "")
    return float(m[-1]) if m else ""


def measure(path, sheets=None):
    starts, dur = cuts(path)
    n = len(starts)
    shots = [b - a for a, b in zip(starts, starts[1:])] + ([dur - starts[-1]] if starts else [])
    shots = [s for s in shots if s > 0]
    info = {}
    j = path.with_suffix(".info.json")
    if j.exists():
        try:
            d = json.loads(j.read_text(encoding="utf8"))
            info = {"title": (d.get("title") or "")[:90], "views": d.get("view_count"),
                    "likes": d.get("like_count"), "url": d.get("webpage_url", "")}
        except Exception:
            pass
    return {
        "file": path.name,
        "seconds": round(dur, 2),
        "shots": n,
        "cuts": max(n - 1, 0),
        "cuts_per_min": round(max(n - 1, 0) / dur * 60, 1) if dur else 0,
        "first_cut_at": round(starts[1], 2) if len(starts) > 1 else "",
        "median_shot": round(statistics.median(shots), 2) if shots else "",
        "shortest_shot": round(min(shots), 2) if shots else "",
        **info,
        "lufs": loudness(path),
        **({"sheet": sheet(path, starts, dur, sheets)} if sheets else {}),
    }


def summarize(rows, label):
    def col(k):
        return [r[k] for r in rows if isinstance(r.get(k), (int, float))]
    out = {"label": label, "videos": len(rows)}
    for k in ("seconds", "cuts_per_min", "first_cut_at", "median_shot"):
        v = col(k)
        out["median_" + k] = round(statistics.median(v), 2) if v else None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", nargs="?", help="@handle, or a profile URL")
    ap.add_argument("--urls", help="file of video URLs, one per line")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--label", default="")
    ap.add_argument("--cookies-from", default="", help="browser name, needed for Instagram")
    ap.add_argument("--cookies", default=os.environ.get("IG_COOKIES", ""),
                    help="cookies.txt exported while signed in to Instagram. Defaults to IG_COOKIES. "
                         "Use this on Windows: Chrome no longer lets yt-dlp read its cookies")
    ap.add_argument("--keep", action="store_true", help="keep the downloads")
    ap.add_argument("--dir", help="measure mp4s already in this folder, no download")
    ap.add_argument("--sheets", action="store_true", help="save a 3x3 contact sheet per video to .teardown/sheets/<label>/")
    a = ap.parse_args()

    label = a.label or (a.target or "teardown").lstrip("@")
    OUT.mkdir(exist_ok=True)

    if a.dir:
        work = Path(a.dir)
        files = sorted(work.glob("*.mp4"))[: a.limit]
        tmp = None
        if not files:
            sys.exit(f"no mp4 files in {work}")
    else:
        tmp = tempfile.mkdtemp(prefix="teardown-")
        work = Path(tmp)
        if a.urls:
            urls = [l.strip() for l in Path(a.urls).read_text().splitlines() if l.strip()]
            files = []
            for i, u in enumerate(urls[: a.limit], 1):
                print(f"  download {i}/{min(len(urls), a.limit)}", flush=True)
                files += fetch(u, 1, work, a.cookies_from, strict=False, cookies=a.cookies)
            if not files:
                sys.exit("none of the links downloaded. Instagram needs a signed-in cookies file: --cookies or IG_COOKIES.")
            files = sorted(set(files))
        elif a.target:
            files = fetch(a.target, a.limit, work, a.cookies_from, cookies=a.cookies)
        else:
            sys.exit("give a @handle, --urls or --dir")

    rows = []
    for i, f in enumerate(files, 1):
        print(f"  [{i}/{len(files)}] {f.name}", flush=True)
        try:
            row = measure(f, OUT / "sheets" / label if a.sheets else None)
        except Exception as e:
            print(f"      skipped: {e}")
            continue
        h = hook(f)
        if h is not None:
            row["hook"] = h
            row["hook_words"] = len(h.split())
        rows.append(row)

    if not rows:
        sys.exit("nothing measured")

    cols = sorted({k for r in rows for k in r})
    csv_path = OUT / f"{label}.csv"
    with csv_path.open("w", newline="", encoding="utf8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    s = summarize(rows, label)
    (OUT / f"{label}.json").write_text(json.dumps(s, indent=2), encoding="utf8")
    print(f"\n{label}: {s['videos']} videos")
    print(f"  length        {s['median_seconds']}s median")
    print(f"  cuts/min      {s['median_cuts_per_min']}")
    print(f"  first cut at  {s['median_first_cut_at']}s")
    print(f"  median shot   {s['median_median_shot']}s")
    if any("hook_words" in r for r in rows):
        hw = [r["hook_words"] for r in rows if "hook_words" in r]
        print(f"  hook words    {round(statistics.median(hw), 1)}")
    else:
        print("  hook words    not measured, faster-whisper is not installed")
    print(f"\n{csv_path}")

    if tmp and not a.keep:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
