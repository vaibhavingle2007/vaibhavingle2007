"""Generate a neofetch-style GitHub profile README.

Customize the constants and CONFIG dictionary below, then run:
    python scripts/generate_readme.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from PIL import Image, ImageOps

try:
    import requests
except ModuleNotFoundError:
    requests = None


GITHUB_USERNAME = "vaibhavingle2007"
README_PATH = Path("README.md")
SVG_PATH = Path("assets/profile-terminal.svg")
PROFILE_IMAGE_PATH = Path("profile.png")
CACHE_DIR = Path(".cache/profile-readme")
ASCII_CACHE_PATH = CACHE_DIR / "ascii.json"
REPO_CACHE_PATH = CACHE_DIR / "repos.json"

# Tweak these to change the portrait density and crop.
ASCII_WIDTH = 58
CHAR_RAMP = " .,:;irsXA253hMHGS#9B&@"
BACKGROUND_CUTOFF = 250
BACKGROUND_NEUTRAL_CUTOFF = 205
BACKGROUND_MAX_COLOR_SPREAD = 35
IMAGE_CROP = (0.18, 0.04, 0.82, 0.92)

INDIA_TZ = timezone(timedelta(hours=5, minutes=30))
BIRTHDAY = datetime(2007, 3, 23, 12, 59, tzinfo=INDIA_TZ)

# GitHub language byte counts are converted to approximate lines.
AVERAGE_BYTES_PER_LINE = 45

# Customize these joke/manual fields. Keep labels short for the neofetch look.
CONFIG = {
    "OS": "Windows, Linux",
    "Kernel": "Open-source mindset",
    "IDE": "VS Code",
    "Languages.Programming": "Python, JavaScript, Java, C++",
    "Hobbies": "Open source, automation, UI projects",
    "Contact.Email": "vaibhavingleg@gmail.com",
    "Contact.LinkedIn": "linkedin.com/in/vaibhavdilipingle",
    "Contact.Discord": "ninjavex_",
}

START_MARKER = "<!--START_SECTION:stats-->"
END_MARKER = "<!--END_SECTION:stats-->"


@dataclass
class RepoSummary:
    name: str
    pushed_at: str
    stars: int
    estimated_lines: int
    language_bytes: dict[str, int]


def main() -> int:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    token = os.environ.get("GH_TOKEN", "").strip()
    if not token:
        print("GH_TOKEN is missing. Public REST stats may work, but GraphQL commit totals will be skipped.")

    if requests is None:
        print("requests is not installed. Generating a local visual preview without live GitHub stats.")
        ascii_art = get_cached_ascii(PROFILE_IMAGE_PATH)
        SVG_PATH.parent.mkdir(parents=True, exist_ok=True)
        SVG_PATH.write_text(render_profile_svg(ascii_art, fallback_stats()), encoding="utf-8")
        inject_readme_block(README_PATH, render_stats_block())
        return 0

    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "neofetch-profile-readme",
        }
    )
    if token:
        session.headers["Authorization"] = f"Bearer {token}"

    try:
        ascii_art = get_cached_ascii(PROFILE_IMAGE_PATH)
        stats = fetch_github_stats(session, token)
    except RuntimeError as error:
        print(f"Error fetching stats: {error}. Using fallback stats.", file=sys.stderr)
        stats = fallback_stats()

    SVG_PATH.parent.mkdir(parents=True, exist_ok=True)
    SVG_PATH.write_text(render_profile_svg(ascii_art, stats), encoding="utf-8")
    block = render_stats_block()
    inject_readme_block(README_PATH, block)
    
    print("README.md updated successfully.")
    return 0


def get_cached_ascii(image_path: Path) -> list[list[dict[str, str]]]:
    if not image_path.exists():
        raise RuntimeError(f"Profile image not found: {image_path}")

    image_hash = sha256_file(image_path)
    cache = read_json(ASCII_CACHE_PATH, default={})
    if (
        cache.get("image_hash") == image_hash
        and cache.get("width") == ASCII_WIDTH
        and cache.get("char_ramp") == CHAR_RAMP
        and cache.get("background_cutoff") == BACKGROUND_CUTOFF
        and cache.get("background_neutral_cutoff") == BACKGROUND_NEUTRAL_CUTOFF
        and cache.get("background_max_color_spread") == BACKGROUND_MAX_COLOR_SPREAD
        and cache.get("image_crop") == list(IMAGE_CROP)
        and cache.get("color_mode") == "rgb-text"
    ):
        cached_lines = cache.get("lines")
        if isinstance(cached_lines, list) and cached_lines:
            return cached_lines

    lines = convert_image_to_ascii(image_path)
    write_json(
        ASCII_CACHE_PATH,
        {
            "image_hash": image_hash,
            "width": ASCII_WIDTH,
            "char_ramp": CHAR_RAMP,
            "background_cutoff": BACKGROUND_CUTOFF,
            "background_neutral_cutoff": BACKGROUND_NEUTRAL_CUTOFF,
            "background_max_color_spread": BACKGROUND_MAX_COLOR_SPREAD,
            "image_crop": list(IMAGE_CROP),
            "color_mode": "rgb-text",
            "lines": lines,
        },
    )
    return lines


def convert_image_to_ascii(image_path: Path) -> list[list[dict[str, str]]]:
    with Image.open(image_path) as source:
        image = source.convert("RGB")

    image = crop_image(image, IMAGE_CROP)
    image = ImageOps.autocontrast(image, cutoff=1)
    aspect_ratio = image.height / image.width
    ascii_height = max(1, int(ASCII_WIDTH * aspect_ratio * 0.5))
    image = image.resize((ASCII_WIDTH, ascii_height))

    lines: list[list[dict[str, str]]] = []
    for y in range(image.height):
        row: list[dict[str, str]] = []
        for x in range(image.width):
            red, green, blue = image.getpixel((x, y))
            brightness = int((red * 0.299) + (green * 0.587) + (blue * 0.114))
            color_spread = max(red, green, blue) - min(red, green, blue)
            is_light_background = (
                brightness >= BACKGROUND_NEUTRAL_CUTOFF and color_spread <= BACKGROUND_MAX_COLOR_SPREAD
            )
            if brightness >= BACKGROUND_CUTOFF or is_light_background:
                row.append({"char": " ", "color": "#000000"})
                continue
            ramp_index = int((255 - brightness) / 255 * (len(CHAR_RAMP) - 1))
            row.append({"char": CHAR_RAMP[ramp_index], "color": f"#{red:02x}{green:02x}{blue:02x}"})
        while row and row[-1]["char"] == " ":
            row.pop()
        lines.append(row)

    return lines


def crop_image(image: Image.Image, crop: tuple[float, float, float, float]) -> Image.Image:
    width, height = image.size
    left = int(width * crop[0])
    top = int(height * crop[1])
    right = int(width * crop[2])
    bottom = int(height * crop[3])
    return image.crop((left, top, right, bottom))


def fetch_github_stats(session: requests.Session, token: str) -> dict[str, Any]:
    user = request_json(session, f"https://api.github.com/users/{GITHUB_USERNAME}")
    repos = fetch_all_repos(session)
    repo_summaries = summarize_repos(session, repos)

    total_stars = sum(repo.stars for repo in repo_summaries)
    total_lines = sum(repo.estimated_lines for repo in repo_summaries)
    language_totals: dict[str, int] = {}
    for repo in repo_summaries:
        for language, byte_count in repo.language_bytes.items():
            language_totals[language] = language_totals.get(language, 0) + byte_count

    commits = fetch_commit_contributions(session) if token else None
    language_items = top_language_items(language_totals)

    return {
        "username": GITHUB_USERNAME,
        "public_repos": user.get("public_repos", len(repos)),
        "followers": user.get("followers", 0),
        "total_stars": total_stars,
        "total_commits": commits,
        "total_lines": total_lines,
        "top_languages": top_languages(language_items),
        "top_language_items": language_items,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


def fallback_stats() -> dict[str, Any]:
    return {
        "username": GITHUB_USERNAME,
        "public_repos": 14,
        "followers": 6,
        "total_stars": 2,
        "total_commits": 106,
        "total_lines": 38966,
        "top_languages": "TypeScript, Python, HTML, PHP, CSS",
        "top_language_items": [
            {"name": "TypeScript", "bytes": 890000, "percent": 46.0},
            {"name": "Python", "bytes": 460000, "percent": 24.0},
            {"name": "HTML", "bytes": 260000, "percent": 13.5},
            {"name": "PHP", "bytes": 190000, "percent": 9.8},
            {"name": "CSS", "bytes": 130000, "percent": 6.7},
        ],
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


def fetch_all_repos(session: requests.Session) -> list[dict[str, Any]]:
    repos: list[dict[str, Any]] = []
    page = 1
    while True:
        url = (
            f"https://api.github.com/users/{GITHUB_USERNAME}/repos"
            f"?per_page=100&page={page}&sort=updated&type=owner"
        )
        batch = request_json(session, url)
        if not isinstance(batch, list):
            raise RuntimeError("GitHub repos response was not a list.")
        repos.extend(repo for repo in batch if not repo.get("fork"))
        if len(batch) < 100:
            break
        page += 1
    return repos


def summarize_repos(session: requests.Session, repos: list[dict[str, Any]]) -> list[RepoSummary]:
    cache = read_json(REPO_CACHE_PATH, default={})
    cache_is_current = cache.get("average_bytes_per_line") == AVERAGE_BYTES_PER_LINE
    cached_repos: dict[str, Any] = cache.get("repos", {}) if isinstance(cache, dict) and cache_is_current else {}
    next_cache: dict[str, Any] = {"average_bytes_per_line": AVERAGE_BYTES_PER_LINE, "repos": {}}
    summaries: list[RepoSummary] = []

    for repo in repos:
        full_name = repo.get("full_name", "")
        pushed_at = repo.get("pushed_at") or repo.get("updated_at") or ""
        stars = int(repo.get("stargazers_count") or 0)
        cached = cached_repos.get(full_name)

        if cached and cached.get("pushed_at") == pushed_at:
            summary = RepoSummary(
                name=full_name,
                pushed_at=pushed_at,
                stars=stars,
                estimated_lines=int(cached.get("estimated_lines", 0)),
                language_bytes={str(k): int(v) for k, v in cached.get("language_bytes", {}).items()},
            )
        else:
            language_bytes = fetch_repo_languages(session, repo)
            estimated_lines = sum(language_bytes.values()) // AVERAGE_BYTES_PER_LINE
            summary = RepoSummary(
                name=full_name,
                pushed_at=pushed_at,
                stars=stars,
                estimated_lines=estimated_lines,
                language_bytes=language_bytes,
            )

        next_cache["repos"][full_name] = {
            "pushed_at": summary.pushed_at,
            "estimated_lines": summary.estimated_lines,
            "language_bytes": summary.language_bytes,
        }
        summaries.append(summary)

    write_json(REPO_CACHE_PATH, next_cache)
    return summaries


def fetch_repo_languages(session: requests.Session, repo: dict[str, Any]) -> dict[str, int]:
    languages_url = repo.get("languages_url")
    if not languages_url:
        return {}
    try:
        payload = request_json(session, languages_url)
    except RuntimeError as error:
        print(f"Warning: could not fetch languages for {repo.get('full_name')}: {error}")
        return {}
    return {str(language): int(bytes_count) for language, bytes_count in payload.items()}


def fetch_commit_contributions(session: requests.Session) -> int | None:
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          totalCommitContributions
        }
      }
    }
    """
    response = session.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": {"login": GITHUB_USERNAME}},
        timeout=30,
    )
    if response.status_code == 401:
        print("Warning: GH_TOKEN was rejected, so commit totals were skipped.")
        return None
    if response.status_code == 403:
        print(f"Warning: GraphQL API returned 403, commit totals skipped: {response.text[:200]}")
        return None
    if not response.ok:
        print(f"Warning: GraphQL commit totals skipped: {response.status_code} {response.text[:200]}")
        return None

    payload = response.json()
    errors = payload.get("errors")
    if errors:
        print(f"Warning: GraphQL returned errors, so commit totals were skipped: {errors}")
        return None
    return payload.get("data", {}).get("user", {}).get("contributionsCollection", {}).get(
        "totalCommitContributions"
    )


def request_json(session: requests.Session, url: str) -> Any:
    response = session.get(url, timeout=30)
    if response.status_code == 403:
        explain_rate_limit(response)
    if response.status_code == 401:
        raise RuntimeError("GitHub token was rejected. Check GH_TOKEN or use the built-in Actions token.")
    if not response.ok:
        raise RuntimeError(f"GitHub API request failed: {response.status_code} {response.text[:200]}")
    return response.json()


def explain_rate_limit(response: requests.Response) -> None:
    remaining = response.headers.get("X-RateLimit-Remaining")
    reset = response.headers.get("X-RateLimit-Reset")
    if remaining == "0" and reset:
        reset_time = datetime.fromtimestamp(int(reset), timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        raise RuntimeError(f"GitHub API rate limit reached. Try again after {reset_time}.")
    raise RuntimeError(f"GitHub API returned 403: {response.text[:200]}")


def top_language_items(language_totals: dict[str, int], limit: int = 5) -> list[dict[str, float | int | str]]:
    if not language_totals:
        return []
    ordered = sorted(language_totals.items(), key=lambda item: item[1], reverse=True)[:limit]
    total = sum(bytes_count for _, bytes_count in ordered) or 1
    return [
        {
            "name": language,
            "bytes": bytes_count,
            "percent": round((bytes_count / total) * 100, 1),
        }
        for language, bytes_count in ordered
    ]


def top_languages(language_items: list[dict[str, float | int | str]]) -> str:
    if not language_items:
        return "N/A"
    return ", ".join(str(item["name"]) for item in language_items)


def render_profile_svg(ascii_art: list[list[dict[str, str]]], stats: dict[str, Any]) -> str:
    right_lines = build_right_column(stats)
    char_width = 9
    line_height = 18
    font_size = 14
    padding = 28
    ascii_x = padding
    ascii_y = padding + font_size
    info_x = padding + (ASCII_WIDTH * char_width) + 56
    value_x = info_x + 202  # fixed x for values (avoids font-width dependency)
    rows = max(len(ascii_art), len(right_lines))
    graph_y = ascii_y + len(right_lines) * line_height + 28
    width = info_x + 660
    height = max(padding * 2 + rows * line_height, graph_y + 250)

    parts = [
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">',
        f"<title id=\"title\">{escape(GITHUB_USERNAME)} GitHub neofetch profile</title>",
        "<desc id=\"desc\">Color ASCII portrait and live GitHub profile statistics.</desc>",
        '<rect width="100%" height="100%" rx="14" fill="#050b16"/>',
        '<rect x="0.5" y="0.5" width="99.9%" height="99.9%" rx="13.5" fill="none" stroke="#1f6feb" opacity="0.65"/>',
        '<style>text{font-family:Consolas,Monaco,"Liberation Mono",monospace;font-size:14px;dominant-baseline:central}.key{fill:#38bdf8;font-weight:700}.value{fill:#f8fafc}.muted{fill:#7dd3fc}.title{fill:#e0f2fe;font-weight:700}.note{fill:#93c5fd}.tiny{font-size:12px}.graph-label{fill:#bfdbfe;font-size:12px}.graph-value{fill:#f8fafc;font-size:12px}</style>',
    ]

    for row_index, row in enumerate(ascii_art):
        y = ascii_y + row_index * line_height
        for column_index, cell in enumerate(row):
            char = cell["char"]
            if char == " ":
                continue
            x = ascii_x + column_index * char_width
            parts.append(
                f'<text x="{x}" y="{y}" fill="{escape(cell["color"])}">{escape(char)}</text>'
            )

    for row_index, segments in enumerate(right_lines):
        y = ascii_y + row_index * line_height
        x = info_x
        if len(segments) == 1:
            seg = segments[0]
            parts.append(f'<text x="{x}" y="{y}" class="{seg["class"]}">{escape(seg["text"])}</text>')
        else:
            parts.append(f'<text y="{y}">')
            for seg in segments:
                klass = seg["class"]
                sx = x if klass == "key" else value_x
                parts.append(f'<tspan x="{sx}" class="{klass}">{escape(seg["text"].rstrip())}</tspan>')
            parts.append('</text>')

    parts.extend(render_language_graph(stats, info_x, graph_y))
    parts.extend(render_stat_meters(stats, info_x, graph_y + 128))
    parts.append("</svg>")
    return "\n".join(parts)


def render_language_graph(stats: dict[str, Any], x: int, y: int) -> list[str]:
    items = stats.get("top_language_items") or []
    if not items:
        return []

    colors = ["#38bdf8", "#60a5fa", "#818cf8", "#22d3ee", "#93c5fd"]
    parts = [
        f'<text x="{x}" y="{y}" class="title">- Language Graph ----------------------</text>',
    ]
    bar_x = x + 150
    bar_width = 330
    bar_height = 10

    for index, item in enumerate(items[:5]):
        row_y = y + 24 + index * 20
        percent = float(item.get("percent", 0))
        width = max(4, int(bar_width * percent / 100))
        color = colors[index % len(colors)]
        name = escape(str(item.get("name", "Unknown"))[:18])
        parts.extend(
            [
                f'<text x="{x}" y="{row_y}" class="graph-label">{name}</text>',
                f'<rect x="{bar_x}" y="{row_y - 6}" width="{bar_width}" height="{bar_height}" rx="5" fill="#0f1b2d"/>',
                f'<rect x="{bar_x}" y="{row_y - 6}" width="{width}" height="{bar_height}" rx="5" fill="{color}"/>',
                f'<text x="{bar_x + bar_width + 16}" y="{row_y}" class="graph-value">{percent:.1f}%</text>',
            ]
        )

    return parts


def render_stat_meters(stats: dict[str, Any], x: int, y: int) -> list[str]:
    meters = [
        ("Repos", stats.get("public_repos"), 50, "#38bdf8"),
        ("Stars", stats.get("total_stars"), 100, "#60a5fa"),
        ("Followers", stats.get("followers"), 100, "#818cf8"),
        ("Commits", stats.get("total_commits"), 1000, "#22d3ee"),
    ]
    parts = [f'<text x="{x}" y="{y}" class="title">- Activity Meters ---------------------</text>']
    bar_x = x + 150
    bar_width = 330
    bar_height = 10

    for index, (label, raw_value, max_value, color) in enumerate(meters):
        value = raw_value if isinstance(raw_value, int) else 0
        row_y = y + 24 + index * 20
        width = max(4, min(bar_width, int(bar_width * value / max_value)))
        parts.extend(
            [
                f'<text x="{x}" y="{row_y}" class="graph-label">{escape(label)}</text>',
                f'<rect x="{bar_x}" y="{row_y - 6}" width="{bar_width}" height="{bar_height}" rx="5" fill="#0f1b2d"/>',
                f'<rect x="{bar_x}" y="{row_y - 6}" width="{width}" height="{bar_height}" rx="5" fill="{color}"/>',
                f'<text x="{bar_x + bar_width + 16}" y="{row_y}" class="graph-value">{escape(format_number(raw_value))}</text>',
            ]
        )

    return parts


def build_right_column(stats: dict[str, Any]) -> list[list[dict[str, str]]]:
    lines: list[list[dict[str, str]]] = [
        [{"text": f"{GITHUB_USERNAME}@github", "class": "title"}],
        [{"text": "-" * (len(GITHUB_USERNAME) + 7), "class": "muted"}],
    ]

    for key, value in CONFIG.items():
        lines.append(format_pair(key, value))
        if key == "OS":
            lines.append(format_pair("Uptime", format_birthday_uptime()))

    lines.extend(
        [
            [{"text": "", "class": "value"}],
            [{"text": "- GitHub Stats " + "-" * 24, "class": "title"}],
            format_pair("Repos", format_number(stats["public_repos"])),
            format_pair("Stars", format_number(stats["total_stars"])),
            format_pair("Followers", format_number(stats["followers"])),
            format_pair("Commits", format_nullable(stats["total_commits"])),
            format_pair("Lines of Code", f"{format_number(stats['total_lines'])} approx"),
            format_pair("Top Languages", stats["top_languages"]),
            format_pair("Updated", stats["updated_at"]),
            [{"text": "", "class": "value"}],
            [{"text": "Note: LOC is approximate, derived from GitHub language byte counts.", "class": "note"}],
        ]
    )
    return lines


def format_pair(key: str, value: str) -> list[dict[str, str]]:
    return [
        {"text": f"{key}:", "class": "key"},
        {"text": str(value), "class": "value"},
    ]


def format_birthday_uptime() -> str:
    now = datetime.now(INDIA_TZ)
    years = now.year - BIRTHDAY.year
    anniversary = BIRTHDAY.replace(year=BIRTHDAY.year + years)
    if now < anniversary:
        years -= 1
        anniversary = BIRTHDAY.replace(year=BIRTHDAY.year + years)

    elapsed = now - anniversary
    days = elapsed.days
    hours, remainder = divmod(elapsed.seconds, 3600)
    minutes = remainder // 60
    return f"{years} years {days} days {hours} hours {minutes} min"


def render_stats_block() -> str:
    return (
        '<p align="center">\n'
        '  <img src="./assets/profile-terminal.svg" alt="Color neofetch GitHub profile" width="100%" />\n'
        "</p>"
    )


def format_number(value: Any) -> str:
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def format_nullable(value: Any) -> str:
    if value is None:
        return "N/A (token needed)"
    return format_number(value)


def inject_readme_block(readme_path: Path, block: str) -> None:
    replacement = f"{START_MARKER}\n{block}\n{END_MARKER}"
    if readme_path.exists():
        content = readme_path.read_text(encoding="utf-8")
    else:
        content = default_readme()

    if START_MARKER not in content or END_MARKER not in content:
        content = default_readme()

    before, marker_and_after = content.split(START_MARKER, 1)
    _, after = marker_and_after.split(END_MARKER, 1)
    readme_path.write_text(before + replacement + after, encoding="utf-8")


def default_readme() -> str:
    return (
        "# Vaibhav Ingle\n\n"
        f"{START_MARKER}\n"
        "Color stats card will appear here after the GitHub Action runs.\n"
        f"{END_MARKER}\n"
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
