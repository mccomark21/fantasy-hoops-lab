"""The design tokens of the site: the Card Back colors and the Archivo font (#117).

This module is the one source of the site colors. Each page of the site puts HEAD in its <head>.
Each color token has a light value (white stock) and a dark value (navy card back).
The dark values follow prefers-color-scheme. The attribute data-theme="light" or "dark" on <html> overrides
the system theme. A script in HEAD sets that attribute from localStorage before the first paint.
Each page loads the font from fonts/archivo-latin.woff2 next to the page. copy_font() writes that file.
The font is Archivo (Omnibus-Type), under the SIL Open Font License 1.1. Each copy of the font has OFL.txt next to it.
"""

import shutil
from pathlib import Path

FONT = Path(__file__).parent / "fonts" / "archivo-latin.woff2"
LICENSE = FONT.with_name("OFL.txt")  # the OFL text with the Archivo copyright. It goes with each copy of the font.
FONT_HREF = "fonts/archivo-latin.woff2"  # the font file, relative to each page
THEME_KEY = "lab-theme"  # the localStorage key of the theme choice: "light" or "dark". No key: the system theme.

# Light: white coated stock with royal-blue and card-red ink.
LIGHT = {
    "lab-stock": "#ffffff",  # the page ground
    "lab-ink": "#14171c",  # the text
    "lab-mute": "#5b6270",  # the secondary text
    "lab-rule": "#e7e9ee",  # the row rules
    "lab-blue": "#1d4f91",  # the menu ground and the solid blocks
    "lab-blue-deep": "#163f75",  # the hover of a menu item
    "lab-on-blue": "#ffffff",  # text on lab-blue
    "lab-red": "#c8102e",  # alerts, IL and lost starts
    "lab-on-red": "#ffffff",  # text on lab-red
    "mark": "#1d4f91",  # the rules, the headings, the selected or sorted state and the links
    "zebra": "#eff3f8",  # every second table row, and table heads
    "qcol": "#e0e8f4",  # a shaded cell: a started game or a quality day
    "qcol-z": "#d6e0ef",  # a shaded cell on a zebra row
    "vrule": "#d2d9e4",  # the vertical rules between table sections
    "lamp-off": "#6f7889",  # a mark that is off
    "lab-scrim": "rgb(8 16 32 / .5)",  # the shade behind the open menu on a phone
}

# Dark: a deep navy card back with white ink.
DARK = {
    "lab-stock": "#0e1a2e",
    "lab-ink": "#eef2f8",
    "lab-mute": "#a7b2c4",
    "lab-rule": "#23334d",
    "lab-blue": "#16305a",
    "lab-blue-deep": "#1f3f73",
    "lab-on-blue": "#ffffff",
    "lab-red": "#ff6b7d",
    "lab-on-red": "#0e1a2e",
    "mark": "#8fb3ff",
    "zebra": "#142540",
    "qcol": "#1c3254",
    "qcol-z": "#223a60",
    "vrule": "#2e4264",
    "lamp-off": "#7d8eab",
    "lab-scrim": "rgb(8 16 32 / .5)",
}


def _declarations(colors, scheme):
    return " ".join(f"--{name}: {value};" for name, value in colors.items()) + f" color-scheme: {scheme};"


TOKENS = f"""@font-face {{
  font-family: Archivo; font-style: normal; font-weight: 400 900; font-stretch: 62% 125%; font-display: swap;
  src: url({FONT_HREF}) format("woff2");
}}
:root {{
  {_declarations(LIGHT, "light")}
  --lab-face: Archivo, "Arial Narrow", system-ui, sans-serif;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{ {_declarations(DARK, "dark")} }}
}}
:root[data-theme="dark"] {{ {_declarations(DARK, "dark")} }}
::selection {{ background: var(--lab-blue); color: var(--lab-on-blue); }}"""

# The saved theme goes on <html> before the first paint, so that the page does not show the wrong theme.
THEME_SCRIPT = (
    f'try {{ const t = localStorage.getItem("{THEME_KEY}"); '
    'if (t === "light" || t === "dark") document.documentElement.dataset.theme = t; } catch (e) {}'
)

HEAD = (
    f"<script>{THEME_SCRIPT}</script>\n"
    f'<link rel="preload" href="{FONT_HREF}" as="font" type="font/woff2" crossorigin>\n'
    f"<style>\n{TOKENS}\n</style>"
)


def copy_font(folder):
    """Copy the font file and its license (OFL.txt) to folder/fonts/, where the pages in folder load the font.

    Return the path of the font copy.
    """
    target = Path(folder) / FONT_HREF
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FONT, target)
    shutil.copyfile(LICENSE, target.with_name(LICENSE.name))
    return target
