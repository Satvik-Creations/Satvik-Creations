import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path


USERNAME = os.environ.get("GITHUB_USERNAME", "Satvik-Creations")
TOKEN = os.environ["GITHUB_TOKEN"]

OUTPUT = Path("assets/github-dashboard.svg")
OUTPUT.parent.mkdir(parents=True, exist_ok=True)


def github_graphql(query, variables):
    data = json.dumps({
        "query": query,
        "variables": variables
    }).encode()

    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=data,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "GitHub-Dashboard"
        },
        method="POST"
    )

    with urllib.request.urlopen(request) as response:
        result = json.loads(response.read().decode())

    if "errors" in result:
        raise RuntimeError(json.dumps(result["errors"], indent=2))

    return result["data"]


now = datetime.now(timezone.utc)
one_year_ago = now - timedelta(days=365)

query = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {

    login
    name

    repositories(
      first: 100
      ownerAffiliations: OWNER
      isFork: false
    ) {
      nodes {
        name
        stargazerCount

        languages(
          first: 10
          orderBy: {field: SIZE, direction: DESC}
        ) {
          edges {
            size
            node {
              name
            }
          }
        }
      }
    }

    contributionsCollection(from: $from, to: $to) {

      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      restrictedContributionsCount

      contributionCalendar {
        totalContributions

        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""

data = github_graphql(
    query,
    {
        "login": USERNAME,
        "from": one_year_ago.isoformat(),
        "to": now.isoformat()
    }
)

user = data["user"]
repos = user["repositories"]["nodes"]
contributions = user["contributionsCollection"]
calendar = contributions["contributionCalendar"]


# ---------------------------------------------------------
# Basic statistics
# ---------------------------------------------------------

stars = sum(repo["stargazerCount"] for repo in repos)

commits = contributions["totalCommitContributions"]
prs = contributions["totalPullRequestContributions"]
issues = contributions["totalIssueContributions"]

total_contributions = calendar["totalContributions"]


# ---------------------------------------------------------
# Language statistics
# ---------------------------------------------------------

languages = {}

for repo in repos:
    for edge in repo["languages"]["edges"]:
        name = edge["node"]["name"]
        size = edge["size"]

        languages[name] = languages.get(name, 0) + size

total_language_size = sum(languages.values())

language_data = []

if total_language_size:
    for name, size in sorted(
        languages.items(),
        key=lambda x: x[1],
        reverse=True
    ):
        percentage = size / total_language_size * 100

        if percentage >= 0.15:
            language_data.append((name, percentage))


language_data = language_data[:5]


# ---------------------------------------------------------
# Contribution days
# ---------------------------------------------------------

days = []

for week in calendar["weeks"]:
    for day in week["contributionDays"]:
        days.append({
            "date": day["date"],
            "count": day["contributionCount"]
        })

days.sort(key=lambda x: x["date"])


# ---------------------------------------------------------
# Current streak
# ---------------------------------------------------------

current_streak = 0

for day in reversed(days):
    if day["count"] > 0:
        current_streak += 1
    else:
        break


# ---------------------------------------------------------
# Longest streak
# ---------------------------------------------------------

longest_streak = 0
running = 0

for day in days:
    if day["count"] > 0:
        running += 1
        longest_streak = max(longest_streak, running)
    else:
        running = 0


# ---------------------------------------------------------
# Last 30 days for activity graph
# ---------------------------------------------------------

graph_days = days[-30:]

if len(graph_days) < 2:
    graph_days = days


# ---------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------

def text(x, y, value, size=16, fill="#8b949e",
         weight="400", anchor="start"):
    return (
        f'<text x="{x}" y="{y}" '
        f'font-family="Arial, Helvetica, sans-serif" '
        f'font-size="{size}px" fill="{fill}" '
        f'font-weight="{weight}" text-anchor="{anchor}">'
        f'{escape(str(value))}</text>'
    )


def rect(x, y, w, h, fill="#161b22", radius=8, stroke="none"):
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
        f'rx="{radius}" fill="{fill}" stroke="{stroke}"/>'
    )


# ---------------------------------------------------------
# Build SVG
# ---------------------------------------------------------

W = 1200
H = 820

svg = [
    f'<svg xmlns="http://www.w3.org/2000/svg" '
    f'width="{W}" height="{H}" viewBox="0 0 {W} {H}">',

    '<rect width="1200" height="820" fill="#0d1117"/>',

    text(45, 50, "📊 GitHub Stats", 28, "#f0f6fc", "700"),

    '<line x1="45" y1="72" x2="1155" y2="72" '
    'stroke="#30363d" stroke-width="1"/>'
]


# ---------------------------------------------------------
# Stats card
# ---------------------------------------------------------

svg.append(rect(80, 95, 530, 230, "#1b1f2a", 7))

svg.append(
    text(
        105,
        130,
        f"{user['name'] or USERNAME}'s GitHub Stats",
        22,
        "#79a8ff",
        "700"
    )
)

stats = [
    ("☆", "Total Stars Earned:", stars),
    ("◷", "Total Commits (last year):", commits),
    ("⑂", "Total PRs:", prs),
    ("ⓘ", "Total Issues:", issues),
    ("▣", "Contributed to (last year):", total_contributions),
]

y = 165

for icon, label, value in stats:
    svg.append(text(105, y, icon, 20, "#b88cff", "400"))
    svg.append(text(135, y, label, 15, "#39d0c8", "700"))
    svg.append(
        text(
            410,
            y,
            value,
            15,
            "#39d0c8",
            "700"
        )
    )
    y += 30


# ---------------------------------------------------------
# Language card
# ---------------------------------------------------------

svg.append(rect(630, 95, 490, 230, "#1b1f2a", 7))

svg.append(
    text(
        660,
        135,
        "Most Used Languages",
        22,
        "#79a8ff",
        "700"
    )
)

colors = [
    "#3178c6",
    "#e34c26",
    "#f1e05a",
    "#563d7c",
    "#3572A5"
]

bar_x = 660
bar_y = 165
bar_w = 420
bar_h = 12

current_x = bar_x

for index, (name, percentage) in enumerate(language_data):

    width = bar_w * percentage / 100

    svg.append(
        f'<rect x="{current_x}" y="{bar_y}" '
        f'width="{width}" height="{bar_h}" '
        f'fill="{colors[index % len(colors)]}"/>'
    )

    current_x += width


y = 205

for index, (name, percentage) in enumerate(language_data):

    svg.append(
        f'<circle cx="666" cy="{y-5}" r="6" '
        f'fill="{colors[index % len(colors)]}"/>'
    )

    svg.append(
        text(
            680,
            y,
            f"{name} {percentage:.2f}%",
            14,
            "#39d0c8"
        )
    )

    y += 28


# ---------------------------------------------------------
# Streak / contribution card
# ---------------------------------------------------------

svg.append(rect(290, 350, 620, 170, "#1b1f2a", 7))

# Vertical separators

svg.append(
    '<line x1="495" y1="375" x2="495" y2="495" '
    'stroke="#d0d7de" stroke-width="1"/>'
)

svg.append(
    '<line x1="705" y1="375" x2="705" y2="495" '
    'stroke="#d0d7de" stroke-width="1"/>'
)

# Total contributions

svg.append(
    text(
        395,
        420,
        total_contributions,
        30,
        "#79a8ff",
        "700",
        "middle"
    )
)

svg.append(
    text(
        395,
        450,
        "Total Contributions",
        13,
        "#79a8ff",
        "400",
        "middle"
    )
)

svg.append(
    text(
        395,
        475,
        f"{days[0]['date']} - Present",
        12,
        "#39d0c8",
        "400",
        "middle"
    )
)


# Current streak

svg.append(
    f'<circle cx="600" cy="415" r="39" '
    f'fill="none" stroke="#79a8ff" stroke-width="6"/>'
)

svg.append(
    text(
        600,
        425,
        current_streak,
        27,
        "#79a8ff",
        "700",
        "middle"
    )
)

svg.append(
    text(
        600,
        465,
        "Current Streak",
        13,
        "#c78cff",
        "700",
        "middle"
    )
)


# Longest streak

svg.append(
    text(
        805,
        420,
        longest_streak,
        30,
        "#79a8ff",
        "700",
        "middle"
    )
)

svg.append(
    text(
        805,
        450,
        "Longest Streak",
        13,
        "#79a8ff",
        "400",
        "middle"
    )
)


# ---------------------------------------------------------
# Contribution Graph
# ---------------------------------------------------------

svg.append(
    text(
        600,
        575,
        f"{user['name'] or USERNAME}'s Contribution Graph",
        17,
        "#8b949e",
        "400",
        "middle"
    )
)


graph_x = 125
graph_y = 610
graph_w = 950
graph_h = 145

max_count = max(
    [d["count"] for d in graph_days] or [1]
)

# Grid

for i in range(6):

    gy = graph_y + graph_h - (i * graph_h / 5)

    svg.append(
        f'<line x1="{graph_x}" y1="{gy}" '
        f'x2="{graph_x + graph_w}" y2="{gy}" '
        f'stroke="#21262d" stroke-width="1"/>'
    )

    value = round(max_count * i / 5)

    svg.append(
        text(
            graph_x - 15,
            gy + 5,
            value,
            10,
            "#8b949e",
            "400",
            "end"
        )
    )


points = []

for i, day in enumerate(graph_days):

    if len(graph_days) == 1:
        x = graph_x
    else:
        x = graph_x + (
            i / (len(graph_days) - 1)
        ) * graph_w

    y = graph_y + graph_h - (
        day["count"] / max_count * graph_h
    )

    points.append((x, y))

# Smooth-ish polyline

if points:
    point_string = " ".join(
        f"{x:.1f},{y:.1f}"
        for x, y in points
    )

    svg.append(
        f'<polyline points="{point_string}" '
        f'fill="none" stroke="#238636" '
        f'stroke-width="3" stroke-linejoin="round" '
        f'stroke-linecap="round"/>'
    )

# Data points

for x, y in points:

    svg.append(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" '
        f'r="4" fill="#8b949e"/>'
    )


# X-axis dates

for i in range(0, len(graph_days), 3):

    day = graph_days[i]

    if len(graph_days) == 1:
        x = graph_x
    else:
        x = graph_x + (
            i / (len(graph_days) - 1)
        ) * graph_w

    date_label = datetime.strptime(
        day["date"],
        "%Y-%m-%d"
    ).strftime("%d")

    svg.append(
        text(
            x,
            graph_y + graph_h + 25,
            date_label,
            10,
            "#8b949e",
            "400",
            "middle"
        )
    )


svg.append("</svg>")

OUTPUT.write_text(
    "\n".join(svg),
    encoding="utf-8"
)

print(f"Generated {OUTPUT}")
