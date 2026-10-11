"""Download the IBX PEL study and make track map images from it.

Each image is a crop of a track plan sheet's map,
with that sheet's curve table moved into a corner of the map,
so the table doesn't need the rest of the sheet below the map to come along.
"""

import hashlib
import subprocess
import sys
from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path

from curl_cffi import requests
from PIL.Image import Image
from pypdfium2 import PdfDocument

ROOT = Path(__file__).parent.parent
CACHE = ROOT / "cache"
OUT = ROOT / "out"

# The PEL study with its appendices, as posted on the MTA's IBX page.
PEL_URL = "https://www.mta.info/document/114891"
# The Wayback Machine's copy, in case the MTA moves or changes it.
# It's much slower, so it's only the backup.
PEL_ARCHIVE_URL = f"https://web.archive.org/web/20260518002024id_/{PEL_URL}"
PEL_SHA256 = "6d0ae17e061fa15185d038c62aae99f8d71c315063ad200d8160c6bfc1cf3230"
PEL_PDF = CACHE / "IBX PEL Final April 2023 v.5.pdf"

# The GitHub release whose assets are the images, so they stay out of git.
RELEASE_TAG = "images"

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
        name="IBX PEL Study - BAT Curves - IBX1 LRT-12 and LRT-18 - p993",
        page=993,
        # The same 2 Av option, drawn rotated, with the reverse curve,
        # from the end of track to the junction with the main line.
        map=Box(left=220, top=MAP_FRAME.top, right=1530, bottom=MAP_FRAME.bottom),
        table=Box(left=1873, top=747, right=2341, bottom=846),
        corner="left",
    ),
    Sheet(
        name="IBX PEL Study - Street Running Curves - p1014",
        page=1014,
        map=Box(
            left=625, top=MAP_FRAME.top, right=MAP_FRAME.right, bottom=MAP_FRAME.bottom
        ),
        table=Box(left=1847, top=748, right=2134, bottom=1001),
        corner="left",
    ),
]


def download_pel() -> Path:
    """Download the PEL study once, reusing the cached copy after that."""
    if PEL_PDF.exists():
        return PEL_PDF
    CACHE.mkdir(exist_ok=True)
    content = None
    for url in [PEL_URL, PEL_ARCHIVE_URL]:
        try:
            # mta.info returns 403 to clients that don't look like a browser.
            response = requests.get(url, impersonate="chrome", timeout=1800)
            response.raise_for_status()
        except requests.RequestsError as e:
            print(f"couldn't download {url}: {e}", file=sys.stderr)
            continue
        sha256 = hashlib.sha256(response.content).hexdigest()
        if sha256 == PEL_SHA256:
            content = response.content
            break
        print(f"{url} has SHA-256 {sha256}, not {PEL_SHA256}", file=sys.stderr)
    if content is None:
        raise RuntimeError("couldn't download the PEL study")
    partial = PEL_PDF.with_suffix(".pdf.part")
    partial.write_bytes(content)
    partial.rename(PEL_PDF)
    return PEL_PDF


def render_page(pdf: PdfDocument, page: int) -> Image:
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


def upload(paths: list[Path]) -> None:
    """Upload the images to the GitHub release, replacing any of the same name."""
    exists = (
        subprocess.run(
            ["gh", "release", "view", RELEASE_TAG],
            check=False,
            capture_output=True,
        ).returncode
        == 0
    )
    if not exists:
        subprocess.run(
            [
                "gh",
                "release",
                "create",
                RELEASE_TAG,
                "--title",
                "Track map images",
                "--notes",
                "Generated by `ibx-pel-track-map-images`, and replaced in place by `ibx-pel-track-map-images --upload`.",
            ],
            check=True,
        )
    subprocess.run(
        ["gh", "release", "upload", RELEASE_TAG, *map(str, paths), "--clobber"],
        check=True,
    )


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--upload",
        action="store_true",
        help=f"upload the images to the `{RELEASE_TAG}` GitHub release",
    )
    parser.add_argument(
        "--print-pel-sha256",
        action="store_true",
        help="only print the PEL study's expected SHA-256, such as for a cache key",
    )
    args = parser.parse_args()
    if args.print_pel_sha256:
        print(PEL_SHA256)
        return
    pdf = PdfDocument(download_pel())
    paths = [make_image(pdf, sheet) for sheet in SHEETS]
    for path in paths:
        print(path)
    if args.upload:
        upload(paths)


if __name__ == "__main__":
    main()
