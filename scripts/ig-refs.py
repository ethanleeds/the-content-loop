#!/usr/bin/env python3
"""Turn the reels you send yourself on Instagram into a measured edit library.

Instagram has no API that reads your own DMs. The data export can: Accounts
Center, Your information and permissions, Download your information, pick
Messages (and Saved if you want those too), format JSON. It arrives as a zip.

    python scripts/ig-refs.py pull ~/Downloads/instagram-export.zip --saved
    python scripts/teardown.py --urls .teardown/ig-refs.txt --label refs --sheets --cookies ig-cookies.txt
    python scripts/ig-refs.py merge
    python scripts/ig-refs.py add https://www.instagram.com/reel/XXXX/   (one you just found)

`pull` reads the zip (or the unzipped folder), finds the thread with only you in
it, and keeps the links you shared there: reels, posts, TikToks, YouTube. It
keeps the link and whose video it is. It does NOT keep the text you typed to
yourself, because that thread is also where private notes go.

`merge` joins those links with the teardown numbers and writes the table into
vault/Edit-References.md between the refs markers. A Style column you fill in by
hand survives every rerun.
"""
import argparse, csv, json, re, sys, zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / ".teardown"
LINK = re.compile(r"https?://[^\s\"'<>]+")
KEEP = ("instagram.com/reel", "instagram.com/p/", "instagram.com/tv/",
        "tiktok.com/", "youtube.com/shorts", "youtu.be/", "youtube.com/watch")
START, END = "<!-- refs:start -->", "<!-- refs:end -->"


def fix(s):
    """Instagram writes UTF-8 bytes as latin-1 escapes. Undo it."""
    if not isinstance(s, str):
        return s
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def find_vault():
    v = HERE.parent / "vault"
    return v if v.is_dir() else None


class Source:
    """The export as a zip or as a folder, read the same way."""

    def __init__(self, path):
        self.path = Path(path)
        self.zip = zipfile.ZipFile(self.path) if self.path.is_file() else None

    def names(self):
        if self.zip:
            return self.zip.namelist()
        return [str(p.relative_to(self.path)).replace("\\", "/") for p in self.path.rglob("*.json")]

    def load(self, name):
        raw = self.zip.read(name) if self.zip else (self.path / name).read_bytes()
        return json.loads(raw.decode("utf-8"))


def threads(src):
    by = {}
    for n in src.names():
        if "/messages/inbox/" in "/" + n and re.search(r"message_\d+\.json$", n):
            by.setdefault(n.rsplit("/", 1)[0], []).append(n)
    return by


def norm(url):
    url = url.rstrip(").,")
    m = re.search(r"instagram\.com/(?:[^/]+/)?(reel|p|tv)/([A-Za-z0-9_-]+)", url)
    if m:
        return f"https://www.instagram.com/{'reel' if m.group(1) == 'reel' else m.group(1)}/{m.group(2)}/"
    return url.split("?")[0] if "tiktok.com" in url else url


def key(url):
    m = re.search(r"instagram\.com/(?:reel|p|tv)/([A-Za-z0-9_-]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"tiktok\.com/.*/video/(\d+)", url)
    if m:
        return m.group(1)
    m = re.search(r"(?:shorts/|youtu\.be/|v=)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else url


def pull(a):
    src = Source(a.export)
    ts = threads(src)
    if not ts:
        sys.exit("no messages/inbox in that export. Request it with Messages ticked and format JSON, not HTML.")

    self_threads, sizes = [], []
    for folder, files in ts.items():
        people, senders, msgs = set(), set(), []
        for f in files:
            d = src.load(f)
            people |= {fix(p.get("name", "")) for p in d.get("participants", [])}
            for m in d.get("messages", []):
                senders.add(fix(m.get("sender_name", "")))
                msgs.append(m)
        name = folder.rsplit("/", 1)[-1]
        sizes.append((len(msgs), name, sorted(people)))
        alone = len(people | senders) == 1
        if (a.thread and a.thread.lower() in name.lower()) or (not a.thread and alone):
            self_threads.append((name, msgs))

    if not self_threads:
        print("could not find a thread with only you in it. The biggest threads are:")
        for n, name, people in sorted(sizes, reverse=True)[:10]:
            print(f"  {name:40} {n:6} messages  {', '.join(people)[:60]}")
        sys.exit("rerun with --thread <folder name from the list>")

    refs = {}
    for name, msgs in self_threads:
        for m in msgs:
            links, owner = [], ""
            share = m.get("share") or {}
            if share.get("link"):
                links.append(share["link"])
                owner = fix(share.get("original_content_owner", ""))
            links += LINK.findall(fix(m.get("content", "")) or "")
            for u in links:
                if not any(k in u for k in KEEP):
                    continue
                u = norm(u)
                k = key(u)
                sent = datetime.fromtimestamp(m.get("timestamp_ms", 0) / 1000, timezone.utc).strftime("%Y-%m-%d")
                if k not in refs or sent > refs[k]["sent"]:
                    refs[k] = {"id": k, "sent": sent, "owner": owner or refs.get(k, {}).get("owner", ""),
                               "url": u, "from": "dm"}

    if a.saved:
        for n in src.names():
            if n.endswith("saved_posts.json") or n.endswith("saved_collections.json"):
                d = src.load(n)
                items = next((v for v in d.values() if isinstance(v, list)), []) if isinstance(d, dict) else d
                for it in items:
                    for v in (it.get("string_map_data") or {}).values():
                        u = v.get("href", "")
                        if any(k in u for k in KEEP):
                            u = norm(u)
                            k = key(u)
                            sent = datetime.fromtimestamp(v.get("timestamp", 0), timezone.utc).strftime("%Y-%m-%d")
                            refs.setdefault(k, {"id": k, "sent": sent, "owner": fix(it.get("title", "")),
                                                "url": u, "from": "saved"})

    rows = sorted(refs.values(), key=lambda r: r["sent"], reverse=True)
    if a.since:
        rows = [r for r in rows if r["sent"] >= a.since]
    if not rows:
        sys.exit("found the thread but no reel, post, TikTok or YouTube links in it.")

    OUT.mkdir(exist_ok=True)
    with (OUT / "ig-refs.csv").open("w", newline="", encoding="utf8") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "sent", "owner", "url", "from"])
        w.writeheader()
        w.writerows(rows)
    (OUT / "ig-refs.txt").write_text("\n".join(r["url"] for r in rows) + "\n", encoding="utf8")

    owners = {}
    for r in rows:
        owners[r["owner"] or "?"] = owners.get(r["owner"] or "?", 0) + 1
    print(f"{len(rows)} links from {', '.join(n for n, _ in self_threads)}"
          f"{' plus Saved' if a.saved else ''}, {rows[-1]['sent']} to {rows[0]['sent']}")
    print("most sent creators: " + ", ".join(f"{o} {c}" for o, c in sorted(owners.items(), key=lambda x: -x[1])[:8]))
    print(f"\n{OUT / 'ig-refs.txt'}\nnext: python scripts/teardown.py --urls .teardown/ig-refs.txt "
          f"--label refs --sheets --cookies ig-cookies.txt")
    write_table(rows, {})


def add(a):
    """Going forward: paste a link, it joins the same list the export fills."""
    OUT.mkdir(exist_ok=True)
    p = OUT / "ig-refs.csv"
    rows = list(csv.DictReader(p.open(encoding="utf8"))) if p.exists() else []
    have = {r["id"] for r in rows}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    n = 0
    for u in a.urls:
        u = norm(u)
        if key(u) in have:
            continue
        rows.insert(0, {"id": key(u), "sent": today, "owner": a.owner or "", "url": u, "from": "pasted"})
        have.add(key(u))
        n += 1
    with p.open("w", newline="", encoding="utf8") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "sent", "owner", "url", "from"])
        w.writeheader()
        w.writerows(rows)
    (OUT / "ig-refs.txt").write_text("\n".join(r["url"] for r in rows) + "\n", encoding="utf8")
    print(f"added {n}, {len(rows)} in the list")
    write_table(rows, {})


def merge(a):
    p = OUT / "ig-refs.csv"
    if not p.exists():
        sys.exit("run pull first")
    rows = list(csv.DictReader(p.open(encoding="utf8")))
    meas = {}
    t = OUT / f"{a.label}.csv"
    if t.exists():
        for r in csv.DictReader(t.open(encoding="utf8")):
            k = key(r.get("url", "")) if r.get("url") else r.get("file", "").rsplit(".", 1)[0]
            meas[k] = r
            meas[r.get("file", "").rsplit(".", 1)[0]] = r
    else:
        print(f"no {t.name} yet, writing the table without numbers")
    write_table(rows, meas)
    print(f"{sum(1 for r in rows if r['id'] in meas)} of {len(rows)} measured")


def write_table(rows, meas):
    vault = find_vault()
    if not vault:
        print("vault/ not found, table not written.")
        return
    note = vault / "Edit-References.md"
    if not note.exists():
        print(f"{note} is missing")
        return
    text = note.read_text("utf8")
    if START not in text or END not in text:
        print("refs markers missing from the note, table not written")
        return
    head, rest = text.split(START, 1)
    old, tail = rest.split(END, 1)
    # Keep the Style column you or an agent already filled in. It is the one
    # column a person writes, so a rerun must never wipe it.
    styles = {}
    for l in old.splitlines():
        c = [x.strip() for x in l.strip().strip("|").split("|")]
        if len(c) == 9 and c[8] and c[2].startswith("["):
            styles[c[2][1:].split("]")[0]] = c[8]
    lines = ["| Sent | Creator | Link | Secs | Cuts/min | First cut | Median shot | Hook | Style |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        m = meas.get(r["id"], {})
        hook = (m.get("hook") or "").replace("|", "/")[:60]
        lines.append(f"| {r['sent']} | {r['owner'] or '?'} | [{r['id']}]({r['url']}) | {m.get('seconds', '')} | "
                     f"{m.get('cuts_per_min', '')} | {m.get('first_cut_at', '')} | {m.get('median_shot', '')} | "
                     f"{hook} | {styles.get(r['id'], '')} |")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    body = f"{START}\n_Written by `ig-refs.py` {stamp}. {len(rows)} references._\n\n" + "\n".join(lines) + f"\n{END}"
    note.write_text(head + body + tail, encoding="utf8")
    print(f"wrote {note}")



def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pull")
    p.add_argument("export", help="the Instagram export zip, or the folder it unzipped to")
    p.add_argument("--thread", help="folder name of the thread, if it cannot find the one with only you")
    p.add_argument("--saved", action="store_true", help="also take your Saved posts")
    p.add_argument("--since", help="only links sent on or after YYYY-MM-DD")
    m = sub.add_parser("merge")
    m.add_argument("--label", default="refs")
    d = sub.add_parser("add")
    d.add_argument("urls", nargs="+", help="reel, TikTok or YouTube links")
    d.add_argument("--owner", help="whose video it is, if you know")
    a = ap.parse_args()
    {"pull": pull, "merge": merge, "add": add}[a.cmd](a)


if __name__ == "__main__":
    main()
