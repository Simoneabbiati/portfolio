"""Refresh the GitHub section of index.html from live GitHub data.

Without a token: contribution calendar, contributions in the last year and active
days, read from the public contributions page (it includes private contributions
because the profile shows them).
With GH_STATS_TOKEN (classic PAT with read:user + repo): also commits in the last
year and the number of repositories, which need an authenticated query.
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.request

USER = "Simoneabbiati"
PAGE = "index.html"


def http(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "portfolio-stats", **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def calendar():
    t = http(f"https://github.com/users/{USER}/contributions")
    days = {}
    for m in re.finditer(r'<td[^>]*data-date="([\d-]+)"[^>]*id="contribution-day-component-(\d+)-(\d+)"[^>]*data-level="(\d)"', t):
        date, row, col, level = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
        days[f"contribution-day-component-{row}-{col}"] = {"date": date, "row": row, "col": col, "level": level, "count": 0}
    for m in re.finditer(r'<tool-tip[^>]*for="(contribution-day-component-\d+-\d+)"[^>]*>([^<]*)</tool-tip>', t):
        n = re.match(r"(\d+) contributions?", m.group(2))
        if m.group(1) in days and n:
            days[m.group(1)]["count"] = int(n.group(1))
    total = re.search(r"([\d,]+)\s+contributions?\s+in the last year", t)
    if not days or not total:
        sys.exit("Could not parse the public contributions page; leaving index.html unchanged.")
    return list(days.values()), int(total.group(1).replace(",", ""))


def authed_stats(token):
    q = ('query{user(login:"%s"){contributionsCollection{totalCommitContributions}'
         ' repositories(ownerAffiliations:OWNER){totalCount}}}' % USER)
    d = json.loads(http("https://api.github.com/graphql", json.dumps({"query": q}).encode(),
                        {"Authorization": f"bearer {token}", "Content-Type": "application/json"}))
    u = d["data"]["user"]
    return u["contributionsCollection"]["totalCommitContributions"], u["repositories"]["totalCount"]


def svg(days):
    cols = max(d["col"] for d in days) + 1
    rects = []
    for d in sorted(days, key=lambda d: (d["col"], d["row"])):
        rects.append(f'<rect x="{d["col"] * 14}" y="{d["row"] * 14}" width="11" height="11" rx="2.5" '
                     f'class="l{d["level"]}"><title>{d["count"]} contributions</title></rect>')
    return (f'<svg class="heat" viewBox="0 0 {cols * 14} 98" role="img" '
            f'aria-label="GitHub contributions over the last twelve months">' + "".join(rects) + "</svg>")


def main():
    s = open(PAGE, encoding="utf-8").read()
    days, total = calendar()
    active = sum(1 for d in days if d["count"] > 0)
    s = re.sub(r'<svg class="heat".*?</svg>', lambda _: svg(days), s, count=1, flags=re.S)
    s = re.sub(r"<b>[\d,]+</b> contributions in the last year", f"<b>{total}</b> contributions in the last year", s)
    s = re.sub(r"<b>[\d,]+</b> active days", f"<b>{active}</b> active days", s)
    s = re.sub(r"<b>[\d,]+</b><span>GitHub contributions, last 12 months",
               f"<b>{total}</b><span>GitHub contributions, last 12 months", s)
    token = os.environ.get("GH_STATS_TOKEN")
    if token:
        commits, repos = authed_stats(token)
        s = re.sub(r"<b>[\d,]+</b> commits", f"<b>{commits}</b> commits", s)
        s = re.sub(r"<b>[\d,]+</b><span>repositories", f"<b>{repos}</b><span>repositories", s)
    open(PAGE, "w", encoding="utf-8").write(s)
    print(f"{dt.date.today()}: {total} contributions, {active} active days"
          + (f", {commits} commits, {repos} repositories" if token else " (commits/repos unchanged: no token)"))


if __name__ == "__main__":
    main()
