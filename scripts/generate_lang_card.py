#!/usr/bin/env python3
import argparse
import json
import math
import os
import urllib.request


API_BASE = "https://api.github.com"


def fetch_json(url, token):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "lang-card-generator",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def list_repos(username, token):
    repos = []
    page = 1
    while True:
        url = f"{API_BASE}/users/{username}/repos?per_page=100&page={page}&sort=updated"
        data = fetch_json(url, token)
        if not data:
            break
        repos.extend(data)
        page += 1
    return repos


def collect_language_totals(username, token):
    totals = {}
    for repo in list_repos(username, token):
        if repo.get("fork"):
            continue
        if repo.get("archived") or repo.get("disabled"):
            continue
        languages_url = repo.get("languages_url")
        if not languages_url:
            continue
        try:
            languages = fetch_json(languages_url, token)
        except Exception:
            continue
        for language, size in languages.items():
            totals[language] = totals.get(language, 0) + size
    return totals


def format_percent(value):
    return f"{value:.2f}%"


def build_svg(items, total_bytes, width=720, height=220):
    title = "Languages"
    title_x = 28
    title_y = 42

    donut_cx = 560
    donut_cy = 120
    donut_radius = 72
    ring_width = 18
    circumference = 2 * math.pi * donut_radius

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{title} stats">',
        '<style>',
        '  .title { font: 600 18px "IBM Plex Sans", "Segoe UI", Tahoma, sans-serif; fill: #111827; }',
        '  .label { font: 500 13px "IBM Plex Sans", "Segoe UI", Tahoma, sans-serif; fill: #1f2937; }',
        '  .muted { fill: #6b7280; }',
        "</style>",
        f'<rect x="0.5" y="0.5" width="{width-1}" height="{height-1}" rx="14" '
        'fill="#ffffff" stroke="#e5e7eb"/>',
        f'<text x="{title_x}" y="{title_y}" class="title">{title}</text>',
    ]

    if not items or total_bytes == 0:
        svg.append(
            f'<text x="{title_x}" y="{title_y + 32}" class="label muted">No language data</text>'
        )
        svg.append("</svg>")
        return "\n".join(svg)

    list_start_y = 78
    line_height = 22
    dot_x = 30
    text_x = 44

    svg.append(
        f'<circle cx="{donut_cx}" cy="{donut_cy}" r="{donut_radius}" fill="none" '
        f'stroke="#f3f4f6" stroke-width="{ring_width}"/>'
    )

    offset = 0.0
    for item in items:
        percent = item["percent"]
        if percent <= 0:
            continue
        length = circumference * (percent / 100)
        svg.append(
            f'<circle cx="{donut_cx}" cy="{donut_cy}" r="{donut_radius}" fill="none" '
            f'stroke="{item["color"]}" stroke-width="{ring_width}" '
            f'stroke-dasharray="{length:.2f} {circumference - length:.2f}" '
            f'stroke-dashoffset="{-offset:.2f}" transform="rotate(-90 {donut_cx} {donut_cy})"/>'
        )
        offset += length

    for idx, item in enumerate(items):
        y = list_start_y + idx * line_height
        svg.append(f'<circle cx="{dot_x}" cy="{y - 4}" r="5" fill="{item["color"]}"/>')
        svg.append(
            f'<text x="{text_x}" y="{y}" class="label">{item["name"]} '
            f'{format_percent(item["percent"])}</text>'
        )

    svg.append("</svg>")
    return "\n".join(svg)


def main():
    parser = argparse.ArgumentParser(description="Generate a GitHub language stats card.")
    parser.add_argument("--username", required=True, help="GitHub username")
    parser.add_argument("--output", default="assets/lang-stats.svg", help="Output SVG path")
    parser.add_argument("--top", type=int, default=8, help="Number of top languages to include")
    args = parser.parse_args()

    token = os.getenv("GITHUB_TOKEN")
    totals = collect_language_totals(args.username, token)
    total_bytes = sum(totals.values())

    if total_bytes == 0:
        svg = build_svg([], total_bytes)
    else:
        palette = [
            "#2563eb",
            "#10b981",
            "#f59e0b",
            "#ef4444",
            "#8b5cf6",
            "#14b8a6",
            "#f97316",
            "#22c55e",
        ]
        sorted_langs = sorted(totals.items(), key=lambda item: item[1], reverse=True)
        top_langs = sorted_langs[: args.top]
        other_bytes = sum(value for _, value in sorted_langs[args.top :])

        items = []
        for idx, (name, value) in enumerate(top_langs):
            percent = (value / total_bytes) * 100
            items.append(
                {
                    "name": name,
                    "percent": percent,
                    "color": palette[idx % len(palette)],
                }
            )

        if other_bytes > 0:
            other_percent = (other_bytes / total_bytes) * 100
            items.append(
                {
                    "name": "Other",
                    "percent": other_percent,
                    "color": "#9ca3af",
                }
            )

        svg = build_svg(items, total_bytes)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        handle.write(svg)


if __name__ == "__main__":
    main()
