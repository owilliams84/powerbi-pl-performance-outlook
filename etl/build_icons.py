"""
Draw the five KPI icons as SVG files in etl/assets/.

Outline icons in the house palette: navy line work, gold for the one part of each icon that
carries the meaning (the arrow, the arc, the bullseye). Drawn on a 48-unit grid with a 2.6 stroke
so they hold up at the 30px the KPI strip shows them at.

Run:  python etl/build_icons.py            (then etl/build_report.py registers them)
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")

NAVY = "#111F38"
GOLD = "#C9A227"

# A dollar sign centred on (0, 0), about 11 units tall; placed with a translate.
DOLLAR = ('<path d="M3.4 -2.6c-.6-1.2-1.8-1.9-3.4-1.9-2 0-3.4 1-3.4 2.4 0 3.3 6.8 1.5 6.8 4.9'
          ' 0 1.5-1.4 2.5-3.4 2.5-1.7 0-3-.8-3.6-2"/><path d="M0 -6.4v12.8"/>')


def dollar(x, y, scale=1):
    return f'<g transform="translate({x} {y}) scale({scale})">{DOLLAR}</g>'


def arrow_up(x, top, bottom, head=4):
    return (f'<path d="M{x} {bottom}V{top}"/>'
            f'<path d="M{x - head} {top + head}l{head}-{head} {head} {head}"/>')


ICONS = {
    # Revenue: money coming in - a coin over an open hand.
    "kpi-revenue.svg": (
        f'<circle cx="24" cy="13" r="9.5"/>{dollar(24, 13, 0.95)}'
        '<path d="M4 31h6v12H4z"/>'
        '<path d="M10 33h8c2.2 0 3.6 1.6 6 1.6h5.5a2.4 2.4 0 0 1 0 4.8H22"/>'
        '<path d="M10 41l11.5 2.6c1.6.4 3.2.2 4.7-.5L43 35.6a2.3 2.3 0 0 0-2.1-4.1L32.5 35.3"/>',
        f'{arrow_up(6, 8, 22)}{arrow_up(42, 8, 22)}',
    ),
    # EBITDA: operating earnings - a money bag, growing.
    "kpi-ebitda.svg": (
        '<path d="M15 6h14l-3.5 6.5h-7z"/>'
        '<path d="M18.5 12.5C11.5 17 7 24 7 31.5 7 38.5 12 43 22 43s15-4.5 15-11.5c0-7.5-4.5-14.5-11.5-19"/>'
        f'{dollar(22, 29.5, 1.05)}',
        f'{arrow_up(42.5, 10, 26)}',
    ),
    # EBITDA %: a share of revenue - a ring with part of it picked out.
    "kpi-margin.svg": (
        '<circle cx="24" cy="24" r="18"/>'
        '<path d="M18 30L30 18"/><circle cx="18.5" cy="18.5" r="2.6"/><circle cx="29.5" cy="29.5" r="2.6"/>',
        '<path d="M24 6a18 18 0 0 1 18 18" stroke-width="4.4"/>',
    ),
    # vs budget: against the target.
    "kpi-budget.svg": (
        '<circle cx="21" cy="27" r="17"/><circle cx="21" cy="27" r="10"/>'
        '<path d="M21 27L40 8"/><path d="M35 5.5v7.5h7.5"/>',
        '<circle cx="21" cy="27" r="3.2" fill="#C9A227"/>',
    ),
    # Net income: what is left to keep - stacked coins.
    "kpi-net-income.svg": (
        '<ellipse cx="16" cy="18" rx="11" ry="4.5"/>'
        '<path d="M5 18v8c0 2.5 4.9 4.5 11 4.5s11-2 11-4.5v-8"/>'
        '<path d="M5 26v8c0 2.5 4.9 4.5 11 4.5s11-2 11-4.5v-8"/>'
        '<path d="M5 34v6c0 2.5 4.9 4.5 11 4.5s11-2 11-4.5v-6"/>',
        f'{arrow_up(38, 8, 30, head=5)}',
    ),
}


def svg(navy, gold):
    return ('<svg viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg" fill="none" '
            'stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">'
            f'<g stroke="{NAVY}">{navy}</g><g stroke="{GOLD}">{gold}</g></svg>\n')


def main():
    for name, (navy, gold) in ICONS.items():
        with open(os.path.join(ASSETS, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(svg(navy, gold))
    print(f"Wrote {len(ICONS)} icons to {ASSETS}")


if __name__ == "__main__":
    main()
