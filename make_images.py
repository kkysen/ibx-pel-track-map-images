#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "curl-cffi",
#     "pillow",
#     "pypdfium2",
# ]
# ///
"""Download the IBX PEL study and make track map images from it.

Each image is a crop of a track plan sheet's map,
with that sheet's curve table moved into a corner of the map,
so the table doesn't need the rest of the sheet below the map to come along.
"""

from dataclasses import dataclass
from pathlib import Path

from curl_cffi import requests
from PIL import Image
from pypdfium2 import PdfDocument

ROOT = Path(__file__).parent
CACHE = ROOT / "cache"
OUT = ROOT / "out"

# The PEL study with its appendices, as posted on the MTA's IBX page.
PEL_URL = "https://www.mta.info/document/114891"
PEL_PDF = CACHE / "IBX PEL Final April 2023 v.5.pdf"

# The maps are vector linework over aerial photos of up to about 380 ppi.
DPI = 200


@dataclass(frozen=True)
class Box:
    """A rectangle on a page, in points from its top left, as displayed (landscape)."""

    left: float
    top: float
    right: float
    bottom: float

    def pixels(self) -> tuple[int, int, int, int]:
        scale = DPI / 72
        return (
            round(self.left * scale),
            round(self.top * scale),
            round(self.right * scale),
            round(self.bottom * scale),
        )


# Every track plan sheet has its aerial photo in the same frame.
MAP_FRAME = Box(left=108, top=141, right=2340, bottom=750)


@dataclass(frozen=True)
class Sheet:
    name: str
    # 1-based, as a PDF viewer numbers pages.
    page: int
    map: Box
    table: Box
    # Which bottom corner of the map the table goes in.
    corner: str


SHEETS = [
    Sheet(
        name="IBX PEL Study - BAT Curve - IBX1 LRT-18 - p992",
        page=992,
        # Only the curve into the Brooklyn Army Terminal, not the yard west of it.
        map=Box(left=1216, top=MAP_FRAME.top, right=2115, bottom=MAP_FRAME.bottom),
        table=Box(left=1873, top=689, right=2341, bottom=826),
        corner="right",
    ),
    Sheet(
        name="IBX PEL Study - Street Running Curves - p1014",
        page=1014,
        map=Box(left=625, top=MAP_FRAME.top, right=MAP_FRAME.right, bottom=MAP_FRAME.bottom),
        table=Box(left=1847, top=748, right=2134, bottom=1001),
        corner="left",
    ),
]


def download_pel() -> Path:
    """Download the PEL study once, reusing the cached copy after that."""
    if PEL_PDF.exists():
        return PEL_PDF
    CACHE.mkdir(exist_ok=True)
    # mta.info returns 403 to clients that don't look like a browser.
    response = requests.get(PEL_URL, impersonate="chrome", timeout=600)
    response.raise_for_status()
    partial = PEL_PDF.with_suffix(".pdf.part")
    partial.write_bytes(response.content)
    partial.rename(PEL_PDF)
    return PEL_PDF


def render_page(pdf: PdfDocument, page: int) -> Image.Image:
    return pdf[page - 1].render(scale=DPI / 72).to_pil().convert("RGB")


def make_image(pdf: PdfDocument, sheet: Sheet) -> Path:
    page = render_page(pdf, sheet.page)
    map_image = page.crop(sheet.map.pixels())
    table = page.crop(sheet.table.pixels())
    y = map_image.height - table.height
    x = 0 if sheet.corner == "left" else map_image.width - table.width
    map_image.paste(table, (x, y))
    OUT.mkdir(exist_ok=True)
    path = OUT / f"{sheet.name}.png"
    map_image.save(path, optimize=True)
    return path


def main() -> None:
    pdf = PdfDocument(download_pel())
    for sheet in SHEETS:
        print(make_image(pdf, sheet))


if __name__ == "__main__":
    main()
