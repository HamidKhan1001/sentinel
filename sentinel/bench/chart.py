"""Dependency-free SVG bar chart of benchmark results (committed to docs/ and shown in the README)."""

COLORS = {"naive": "#8b949e", "rules": "#d29922", "graph": "#3fb950", "claude": "#58a6ff", "multi": "#bc8cff"}


def render(summaries: list[dict]) -> str:
    metrics = [("root_service", "Root service"), ("fixed", "Incident fixed"), ("fixed_silent", "Fixed (silent root)")]
    w, h, gw = 720, 330, 210
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" font-family="system-ui,sans-serif">',
           f'<rect width="{w}" height="{h}" fill="#0d1117" rx="10"/>',
           '<text x="24" y="34" fill="#e6edf3" font-size="16" font-weight="600">Sentinel benchmark: higher is better (%)</text>']
    bw = min(34, (gw - 30) / max(1, len(summaries)))
    for gi, (key, label) in enumerate(metrics):
        x0 = 30 + gi * (gw + 10)
        for si, s in enumerate(summaries):
            v = s[key]
            bh = v * 1.8
            x = x0 + si * (bw + 4)
            out.append(f'<rect x="{x:.0f}" y="{270 - bh:.0f}" width="{bw:.0f}" height="{bh:.0f}" rx="3" fill="{COLORS.get(s["agent"], "#58a6ff")}"/>')
            out.append(f'<text x="{x + bw / 2:.0f}" y="{264 - bh:.0f}" fill="#e6edf3" font-size="11" text-anchor="middle">{v:.0f}</text>')
        out.append(f'<text x="{x0}" y="292" fill="#8b949e" font-size="12">{label}</text>')
    for i, s in enumerate(summaries):
        out.append(f'<rect x="{24 + i * 90}" y="306" width="10" height="10" fill="{COLORS.get(s["agent"], "#58a6ff")}"/>'
                   f'<text x="{40 + i * 90}" y="315" fill="#8b949e" font-size="12">{s["agent"]}</text>')
    out.append("</svg>")
    return "\n".join(out)
