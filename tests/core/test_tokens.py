import functools
import http.server
import threading

import pytest

from fantasyhoops.core import tokens
from fantasyhoops.core.publish import site_head, write_page
from tests.core.test_roster import browser_page

EXT_NAMES = ["Nikola Jokić", "Luka Dončić", "Kristaps Porziņģis", "Bogdan Bogdanović"]


def test_the_latin_extended_file_is_a_second_font_file_with_the_license():
    """#211: the Latin Extended letters are in a second woff2 file next to the Latin file and OFL.txt."""
    assert tokens.FONT_EXT.read_bytes()[:4] == b"wOF2" and tokens.FONT_EXT.parent == tokens.FONT.parent
    assert tokens.FONTS == (tokens.FONT, tokens.FONT_EXT)
    assert tokens.LICENSE.exists()


def test_the_tokens_have_a_latin_extended_face_with_a_unicode_range_and_no_preload():
    """#211: the second @font-face has the same axes and a unicode-range. HEAD preloads only the Latin file."""
    faces = tokens.TOKENS.split("@font-face")[1:]
    assert len(faces) == 2
    latin, ext = faces
    assert f"url({tokens.FONT_HREF})" in latin and f"url({tokens.FONT_EXT_HREF})" in ext
    axes = "font-weight: 400 900; font-stretch: 62% 125%;"
    assert axes in latin and axes in ext
    assert f"unicode-range: {tokens.LATIN_EXT_RANGE};" in ext
    assert "U+0100-02BA" in tokens.LATIN_EXT_RANGE  # č (U+010D), ć, ņ, ģ, š, ž and đ (U+0111)
    assert tokens.FONT_EXT_HREF not in tokens.HEAD.split("<style>")[0]


def test_copy_font_copies_both_font_files_and_the_license(tmp_path):
    target = tokens.copy_font(tmp_path)
    assert target == tmp_path / tokens.FONT_HREF
    for f in (*tokens.FONTS, tokens.LICENSE):
        assert (tmp_path / "fonts" / f.name).read_bytes() == f.read_bytes()


def test_the_design_sample_has_both_font_files_and_the_license():
    """#211: docs/design/players-sample.html loads the files from docs/design/fonts/ (#195)."""
    sample = tokens.FONT.parents[4] / "docs" / "design" / "players-sample.html"
    text = sample.read_text(encoding="utf-8")
    assert f"url({tokens.FONT_EXT_HREF})" in text and f"unicode-range: {tokens.LATIN_EXT_RANGE};" in text
    for f in (*tokens.FONTS, tokens.LICENSE):
        assert (sample.parent / "fonts" / f.name).read_bytes() == f.read_bytes()


@pytest.fixture
def served(tmp_path):
    """A local web server for tmp_path/site. Give the base URL. A page that loads fonts/ needs a server."""
    root = tmp_path / "site"
    root.mkdir()
    handler = type("Quiet", (http.server.SimpleHTTPRequestHandler,), {"log_message": lambda *a: None})
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(handler, directory=str(root)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield root, f"http://127.0.0.1:{server.server_address[1]}/"
    server.shutdown()
    server.server_close()


def open_page(pg, root, url, names):
    """Write a page with site_head() and one <p> for each name with write_page(). Open it. Give the font file requests."""
    body = "".join(f'<p style="font: 900 30px/1 var(--lab-face); font-stretch: 66%">{n}</p>' for n in names)
    write_page(
        root / "t" / "index.html",
        f'<!doctype html><html><head><meta charset="utf-8">{site_head()}</head><body>{body}</body></html>',
    )
    asked = []
    pg.on("request", lambda r: asked.append(r.url.rsplit("/", 1)[-1]) if r.url.endswith(".woff2") else None)
    pg.goto(f"{url}t/", wait_until="networkidle")  # the layout asks for the Latin Extended file after the load event
    pg.evaluate("document.fonts.ready")
    return asked


def archivo(font):
    """True for a font of the Archivo files. Chromium names each instance, for example "Archivo SemiBold"."""
    return font["isCustomFont"] and font["postScriptName"].startswith("Archivo-")


def platform_fonts(pg):
    """For each <p> of the page, the fonts that render its glyphs, from Chromium (CSS.getPlatformFontsForNode)."""
    cdp = pg.context.new_cdp_session(pg)
    cdp.send("DOM.enable")
    cdp.send("CSS.enable")
    doc = cdp.send("DOM.getDocument")["root"]["nodeId"]
    nodes = cdp.send("DOM.querySelectorAll", {"nodeId": doc, "selector": "p"})["nodeIds"]
    return [cdp.send("CSS.getPlatformFontsForNode", {"nodeId": n})["fonts"] for n in nodes]


def test_names_with_latin_extended_letters_render_each_glyph_in_archivo(served):
    """#211: no glyph of "Nikola Jokić" or "Luka Dončić" falls back to Arial Narrow. The page loads both files."""
    root, url = served
    with browser_page(1280) as pg:
        asked = open_page(pg, root, url, EXT_NAMES)
        assert pg.evaluate("document.fonts.check('900 30px Archivo', 'Jokić Dončić Porziņģis')")
        for name, fonts in zip(EXT_NAMES, platform_fonts(pg)):
            assert fonts and all(archivo(f) for f in fonts), (name, fonts)
        assert tokens.FONT_EXT.name in asked and tokens.FONT.name in asked


def test_a_page_with_no_latin_extended_letter_does_not_load_the_second_file(served):
    """#211: the unicode-range keeps the Latin Extended file off a page that does not need it."""
    root, url = served
    with browser_page(1280) as pg:
        asked = open_page(pg, root, url, ["Tyrese Maxey", "Joel Embiid", "Kristaps Porzingis"])
        assert all(archivo(f) for fonts in platform_fonts(pg) for f in fonts)
        assert tokens.FONT.name in asked and tokens.FONT_EXT.name not in asked
