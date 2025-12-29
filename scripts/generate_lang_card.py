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
    return f"{value:.1f}%"


def truncate_label(value, max_len=16):
    if len(value) <= max_len:
        return value
    if max_len <= 3:
        return value[:max_len]
    return f"{value[: max_len - 3]}..."


def build_svg(items, total_bytes, width=820, height=None):
    title = "Language Mix"
    subtitle = "Auto-updated daily"
    title_x = 28
    title_y = 42

    line_height = 22
    list_start_y = 92
    list_height = list_start_y + len(items) * line_height
    height = height or max(230, list_height + 24)

    donut_cx = width - 170
    donut_cy = int(height / 2) + 4
    donut_radius = 78
    ring_width = 16
    circumference = 2 * math.pi * donut_radius

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{title} stats">',
        "<defs>",
        '  <linearGradient id="bg" x1="0" x2="0" y1="0" y2="1">',
        '    <stop offset="0%" stop-color="#0b0f16"/>',
        '    <stop offset="100%" stop-color="#111827"/>',
        "  </linearGradient>",
        '  <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">',
        '    <feDropShadow dx="0" dy="8" stdDeviation="10" flood-color="#000000" flood-opacity="0.35"/>',
        "  </filter>",
        '  <filter id="softGlow" x="-20%" y="-20%" width="140%" height="140%">',
        '    <feDropShadow dx="0" dy="0" stdDeviation="6" flood-color="#0ea5e9" flood-opacity="0.12"/>',
        "  </filter>",
        "</defs>",
        "<style>",
        '  .title { font: 600 18px "Source Sans 3", "Segoe UI", Tahoma, sans-serif; fill: #e2e8f0; }',
        '  .subtitle { font: 500 12px "Source Sans 3", "Segoe UI", Tahoma, sans-serif; fill: #94a3b8; }',
        '  .label { font: 500 13px "Source Sans 3", "Segoe UI", Tahoma, sans-serif; fill: #e5e7eb; }',
        '  .value { font: 600 22px "Source Sans 3", "Segoe UI", Tahoma, sans-serif; fill: #f8fafc; }',
        '  .muted { fill: #94a3b8; }',
        "</style>",
        f'<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="16" '
        'fill="url(#bg)" stroke="#1f2937" filter="url(#shadow)"/>',
        f'<text x="{title_x}" y="{title_y}" class="title">{title}</text>',
        f'<text x="{title_x}" y="{title_y + 18}" class="subtitle">{subtitle}</text>',
    ]

    if not items or total_bytes == 0:
        svg.append(
            f'<text x="{title_x}" y="{title_y + 32}" class="label muted">No language data</text>'
        )
        svg.append("</svg>")
        return "\n".join(svg)

    dot_x = 32
    text_x = 48
    value_x = 320

    svg.append(
        f'<circle cx="{donut_cx}" cy="{donut_cy}" r="{donut_radius}" fill="none" '
        f'stroke="#1f2937" stroke-width="{ring_width}"/>'
    )
    svg.append(
        f'<circle cx="{donut_cx}" cy="{donut_cy}" r="{donut_radius + 10}" fill="none" '
        f'stroke="#0f172a" stroke-width="1" opacity="0.6"/>'
    )
    svg.append(
        f'<line x1="{title_x}" y1="{list_start_y - 16}" x2="{width - 28}" '
        f'y2="{list_start_y - 16}" stroke="#1f2937" stroke-width="1"/>'
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
            f'stroke-dashoffset="{-offset:.2f}" transform="rotate(-90 {donut_cx} {donut_cy})" '
            f'stroke-linecap="round" filter="url(#softGlow)"/>'
        )
        offset += length

    for idx, item in enumerate(items):
        y = list_start_y + idx * line_height
        svg.append(f'<circle cx="{dot_x}" cy="{y - 4}" r="5" fill="{item["color"]}"/>')
        svg.append(
            f'<text x="{text_x}" y="{y}" class="label">{truncate_label(item["name"])}</text>'
        )
        svg.append(
            f'<text x="{value_x}" y="{y}" class="label muted" text-anchor="end">'
            f'{format_percent(item["percent"])}</text>'
        )

    top = items[0]
    center_value = format_percent(top["percent"])
    svg.append(
        f'<text x="{donut_cx}" y="{donut_cy - 4}" class="value" text-anchor="middle">{center_value}</text>'
    )
    svg.append(
        f'<text x="{donut_cx}" y="{donut_cy + 16}" class="label muted" text-anchor="middle">'
        f'{truncate_label(top["name"], 14)}</text>'
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
            "#3b82f6",
            "#22c55e",
            "#f59e0b",
            "#f43f5e",
            "#8b5cf6",
            "#38bdf8",
            "#10b981",
            "#fb923c",
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
