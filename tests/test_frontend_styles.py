from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.parse import urlsplit


STATIC_DIR = Path(__file__).resolve().parents[1] / "backend" / "static"


class StylesheetParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.style_blocks = 0
        self.inline_style_attributes = 0
        self.stylesheet_links = []
        self.utility_classes = set()

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "style":
            self.style_blocks += 1
        if "style" in attributes:
            self.inline_style_attributes += 1
        self.utility_classes.update(
            name for name in attributes.get("class", "").split() if name.startswith("u-")
        )
        if tag == "link" and "stylesheet" in attributes.get("rel", "").lower().split():
            self.stylesheet_links.append(attributes.get("href", ""))


def parse_styles(path):
    parser = StylesheetParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


def test_static_html_has_no_embedded_style_blocks_and_css_links_resolve():
    pages = sorted(STATIC_DIR.rglob("*.html"))
    assert pages
    defined_utilities = set(
        re.findall(
            r"\.([a-z0-9-]+)\s*\{",
            (STATIC_DIR / "css" / "utilities.css").read_text(encoding="utf-8"),
        )
    )

    for page in pages:
        parser = parse_styles(page)
        assert parser.style_blocks == 0, f"Embedded <style> block in {page}"
        assert parser.inline_style_attributes == 0, f"Inline style attribute in {page}"
        assert any(
            urlsplit(href).path == "/static/css/utilities.css"
            for href in parser.stylesheet_links
        ), f"Missing utility stylesheet in {page}"
        assert parser.utility_classes <= defined_utilities, (
            f"Undefined utility class in {page}: "
            f"{parser.utility_classes - defined_utilities}"
        )
        for href in parser.stylesheet_links:
            path = urlsplit(href).path
            if path.startswith("/static/css/"):
                stylesheet = STATIC_DIR / path.removeprefix("/static/")
                assert stylesheet.is_file(), f"Missing stylesheet {href} in {page}"


def test_employee_login_has_no_inline_styles():
    parser = parse_styles(STATIC_DIR / "login.html")

    assert parser.inline_style_attributes == 0
    assert any(urlsplit(href).path == "/static/css/login.css" for href in parser.stylesheet_links)
