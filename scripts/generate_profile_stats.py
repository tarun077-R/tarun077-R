import datetime as dt
import html
import json
import os
import urllib.request
from collections import Counter
from pathlib import Path

USERNAME = os.environ.get("GITHUB_USERNAME", "tarun077-R")
TOKEN = os.environ.get("GITHUB_TOKEN")
OUT = Path("profile")
OUT.mkdir(parents=True, exist_ok=True)

if not TOKEN:
    raise SystemExit("GITHUB_TOKEN is required")


def github_graphql(query, variables):
    data = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=data,
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "tarun077-R-profile-stats",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    return payload["data"]


def github_rest(path):
    req = urllib.request.Request(
        "https://api.github.com" + path,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "tarun077-R-profile-stats",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def esc(value):
    return html.escape(str(value), quote=True)


def svg_shell(width, height, body):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" rx="14" fill="#0d1117" stroke="#30363d"/>
{body}
</svg>\n'''


def text(x, y, value, size=14, fill="#c9d1d9", weight="400", anchor="start"):
    return f'<text x="{x}" y="{y}" fill="{fill}" font-family="Segoe UI,Arial,sans-serif" font-size="{size}px" font-weight="{weight}" text-anchor="{anchor}">{esc(value)}</text>'


now = dt.datetime.now(dt.timezone.utc)
start = now - dt.timedelta(days=364)
end = now
query = """
query($login:String!, $from:DateTime!, $to:DateTime!) {
  user(login:$login) {
    followers { totalCount }
    repositories(ownerAffiliations:OWNER, first:100, isFork:false) {
      totalCount
      nodes {
        name
        isPrivate
        stargazerCount
        languages(first:10, orderBy:{field:SIZE, direction:DESC}) {
          edges { size node { name } }
        }
      }
    }
    contributionsCollection(from:$from, to:$to) {
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays { date contributionCount }
        }
      }
    }
  }
}
"""
data = github_graphql(query, {"login": USERNAME, "from": start.isoformat(), "to": end.isoformat()})
user = data["user"]
cc = user["contributionsCollection"]
calendar = cc["contributionCalendar"]
days = [d for w in calendar["weeks"] for d in w["contributionDays"]]

public_repos = github_rest(f"/users/{USERNAME}").get("public_repos", 0)
repo_nodes = user["repositories"]["nodes"]
total_stars = sum(r["stargazerCount"] for r in repo_nodes)

languages = Counter()
for repo in repo_nodes:
    for edge in repo.get("languages", {}).get("edges", []):
        languages[edge["node"]["name"]] += edge["size"]

language_total = sum(languages.values()) or 1
language_rows = languages.most_common(6)

counts = {d["date"]: d["contributionCount"] for d in days}
ordered = sorted(counts.items())
current = 0
cursor = end.date()
while counts.get(cursor.isoformat(), 0) > 0:
    current += 1
    cursor -= dt.timedelta(days=1)
longest = 0
run = 0
for _, count in ordered:
    if count > 0:
        run += 1
        longest = max(longest, run)
    else:
        run = 0

body = "".join([
    text(28, 34, "GitHub Analytics", 18, "#f0f6fc", "700"),
    text(28, 61, USERNAME, 13, "#8b949e"),
    text(28, 106, f"{calendar['totalContributions']}", 28, "#58a6ff", "700"),
    text(28, 128, "contributions", 12, "#8b949e"),
    text(190, 106, f"{public_repos}", 28, "#f0f6fc", "700"),
    text(190, 128, "public repos", 12, "#8b949e"),
    text(352, 106, f"{total_stars}", 28, "#f0f6fc", "700"),
    text(352, 128, "stars earned", 12, "#8b949e"),
    text(514, 106, f"{user['followers']['totalCount']}", 28, "#f0f6fc", "700"),
    text(514, 128, "followers", 12, "#8b949e"),
    '<line x1="28" y1="150" x2="632" y2="150" stroke="#30363d"/>',
    text(28, 180, f"Commits: {cc['totalCommitContributions']}", 13),
    text(220, 180, f"Pull requests: {cc['totalPullRequestContributions']}", 13),
    text(448, 180, f"Reviews: {cc['totalPullRequestReviewContributions']}", 13),
])
(OUT / "stats.svg").write_text(svg_shell(660, 210, body), encoding="utf-8")

body = text(24, 32, "Top Languages", 18, "#f0f6fc", "700")
y = 64
for name, size in language_rows:
    pct = size / language_total * 100
    width = max(2, pct * 4.8)
    body += text(24, y, name, 12, "#c9d1d9", "600")
    body += text(570, y, f"{pct:.1f}%", 12, "#8b949e", "400", "end")
    body += f'<rect x="24" y="{y+9}" width="540" height="7" rx="3.5" fill="#21262d"/><rect x="24" y="{y+9}" width="{width:.1f}" height="7" rx="3.5" fill="#58a6ff"/>'
    y += 38
(OUT / "top-languages.svg").write_text(svg_shell(600, 64 + 38 * max(1, len(language_rows)), body), encoding="utf-8")

levels = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
max_count = max(counts.values() or [1])
start_date = min(counts) if counts else start.date().isoformat()
first = dt.date.fromisoformat(start_date)
first_sunday = first - dt.timedelta(days=(first.weekday() + 1) % 7)
body = text(24, 32, "Contribution Activity", 18, "#f0f6fc", "700")
body += text(24, 54, f"{calendar['totalContributions']} contributions in the last year", 12, "#8b949e")
x0, y0 = 24, 76
for day_index in range(371):
    date = first_sunday + dt.timedelta(days=day_index)
    if date > end.date():
        continue
    week = (date - first_sunday).days // 7
    row = (date.weekday() + 1) % 7
    count = counts.get(date.isoformat(), 0)
    ratio = count / max_count if max_count else 0
    level = 0 if count == 0 else min(4, int(ratio * 4) + 1)
    x = x0 + week * 14
    y = y0 + row * 14
    body += f'<rect x="{x}" y="{y}" width="10" height="10" rx="2" fill="{levels[level]}"/>'
body += text(24, 191, f"Current streak: {current} days", 12, "#8b949e")
body += text(190, 191, f"Longest streak: {longest} days", 12, "#8b949e")
body += text(365, 191, "Less", 11, "#8b949e")
for i, color in enumerate(levels):
    body += f'<rect x="397" y="183" width="10" height="10" rx="2" fill="{color}"/>'
body += text(470, 191, "More", 11, "#8b949e")
(OUT / "activity.svg").write_text(svg_shell(800, 215, body), encoding="utf-8")

body = text(28, 34, "Contribution Streak", 18, "#f0f6fc", "700")
body += text(28, 94, str(calendar["totalContributions"]), 30, "#58a6ff", "700")
body += text(28, 116, "total contributions", 12, "#8b949e")
body += text(235, 94, str(current), 30, "#f0f6fc", "700")
body += text(235, 116, "current streak", 12, "#8b949e")
body += text(450, 94, str(longest), 30, "#f0f6fc", "700")
body += text(450, 116, "longest streak", 12, "#8b949e")
(OUT / "streak.svg").write_text(svg_shell(660, 145, body), encoding="utf-8")

print("Generated profile/stats.svg, profile/top-languages.svg, profile/activity.svg, profile/streak.svg")
