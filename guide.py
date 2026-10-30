"""Builds an XMLTV guide for Jellyfin from the HDHomeRun's free guide service.

The service returns roughly 12 hours per request and only a couple of days ahead, so
this pages forward from now until it runs out, writes the file, and repeats.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from xml.sax.saxutils import escape, quoteattr

HOST = os.environ.get("HDHR_HOST")
if not HOST:
    sys.exit("HDHR_HOST is not set: give it your HDHomeRun's IP address or hostname")
OUT = os.environ.get("OUT", "/out/guide.xml")
INTERVAL = float(os.environ.get("INTERVAL_HOURS", "4")) * 3600
MAX_PAGES = 10

# HDHomeRun filter -> category Jellyfin uses to tag movies, sports, news and kids shows.
CATEGORIES = {"Movies": "Movie", "Sports": "Sports", "News": "News", "Kids": "Kids"}


def get_json(url):
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.load(resp)


def fetch():
    auth = get_json(f"http://{HOST}/discover.json")["DeviceAuth"]
    names = {c["GuideNumber"]: c["GuideName"] for c in get_json(f"http://{HOST}/lineup.json")}
    channels, programmes, start = {}, {}, None
    for _ in range(MAX_PAGES):
        url = f"https://api.hdhomerun.com/api/guide.php?DeviceAuth={auth}"
        if start:
            url += f"&Start={start}"
        try:
            page = get_json(url)
        except urllib.error.HTTPError as exc:
            if exc.code == 400 and start:  # past the end of the available guide
                break
            raise
        end = start or 0
        for ch in page:
            num = ch["GuideNumber"]
            channels.setdefault(num, {**ch, "LineupName": names.get(num)})
            for p in ch.get("Guide", []):
                programmes[(num, p["StartTime"])] = p
                end = max(end, p["EndTime"])
        if not page or end <= (start or 0):
            break
        start = end
        time.sleep(1)
    return channels, programmes


def ts(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y%m%d%H%M%S +0000")


def tag(name, text, **attrs):
    a = "".join(f" {k}={quoteattr(str(v))}" for k, v in attrs.items())
    return f"<{name}{a}>{escape(str(text))}</{name}>"


def to_xmltv(channels, programmes):
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<tv generator-info-name="hdhr-guide">']
    for num in sorted(channels, key=lambda n: [int(x) for x in n.split(".") if x.isdigit()]):
        ch = channels[num]
        out.append(f"  <channel id={quoteattr(num)}>")
        out.append("    " + tag("display-name", num))
        for name in dict.fromkeys(filter(None, [ch.get("LineupName"), ch.get("GuideName"), ch.get("Affiliate")])):
            out.append("    " + tag("display-name", name))
        out.append("    " + tag("lcn", num))
        if ch.get("ImageURL"):
            out.append(f"    <icon src={quoteattr(ch['ImageURL'])}/>")
        out.append("  </channel>")
    for (num, start), p in sorted(programmes.items()):
        out.append(f"  <programme start={quoteattr(ts(start))} stop={quoteattr(ts(p['EndTime']))} channel={quoteattr(num)}>")
        out.append("    " + tag("title", p["Title"]))
        if p.get("EpisodeTitle"):
            out.append("    " + tag("sub-title", p["EpisodeTitle"]))
        if p.get("Synopsis"):
            out.append("    " + tag("desc", p["Synopsis"]))
        for f in p.get("Filter", []):
            out.append("    " + tag("category", CATEGORIES.get(f, f)))
        image = p.get("PosterURL") or p.get("ImageURL")
        if image:
            out.append(f"    <icon src={quoteattr(image)}/>")
        ep = p.get("EpisodeNumber", "")
        if ep.startswith("S") and "E" in ep:
            season, episode = ep[1:].split("E", 1)
            if season.isdigit() and episode.isdigit():
                out.append("    " + tag("episode-num", f"{int(season) - 1}.{int(episode) - 1}.", system="xmltv_ns"))
            out.append("    " + tag("episode-num", ep, system="onscreen"))
        if p.get("First"):
            out.append("    <new/>")
        elif p.get("OriginalAirdate"):
            day = datetime.fromtimestamp(p["OriginalAirdate"], timezone.utc).strftime("%Y%m%d")
            out.append(f"    <previously-shown start={quoteattr(day)}/>")
        out.append("  </programme>")
    out.append("</tv>\n")
    return "\n".join(out)


def run_once():
    channels, programmes = fetch()
    if not programmes:
        raise RuntimeError("guide service returned no programmes")
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(to_xmltv(channels, programmes))
    os.replace(tmp, OUT)
    last = datetime.fromtimestamp(max(p["EndTime"] for p in programmes.values()), timezone.utc)
    print(f"{datetime.now():%Y-%m-%d %H:%M} wrote {len(channels)} channels, {len(programmes)} programmes through {last:%Y-%m-%d %H:%M} UTC", flush=True)


if __name__ == "__main__":
    while True:
        try:
            run_once()
        except Exception as exc:  # keep the last good file and try again next round
            print(f"{datetime.now():%Y-%m-%d %H:%M} update failed: {exc}", file=sys.stderr, flush=True)
        time.sleep(INTERVAL)
