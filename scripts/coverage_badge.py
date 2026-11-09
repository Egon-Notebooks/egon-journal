"""Write a small SVG coverage badge from coverage.xml: coverage_badge.py coverage.xml out.svg"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

percent = round(float(ET.parse(sys.argv[1]).getroot().attrib["line-rate"]) * 100)
color = "#2f9a7e" if percent >= 80 else "#b8860b" if percent >= 60 else "#a83232"
Path(sys.argv[2]).write_text(
    f'<svg xmlns="http://www.w3.org/2000/svg" width="104" height="20" role="img" '
    f'aria-label="coverage: {percent}%"><rect width="64" height="20" fill="#555"/>'
    f'<rect x="64" width="40" height="20" fill="{color}"/>'
    '<g fill="#fff" font-family="Verdana,sans-serif" font-size="11" text-anchor="middle">'
    f'<text x="32" y="14">coverage</text><text x="84" y="14">{percent}%</text></g></svg>\n'
)
