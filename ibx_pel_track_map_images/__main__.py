"""Download the IBX PEL study and make track map images from it.

Each image is a crop of a track plan sheet's map,
with that sheet's curve table moved into a corner of the map,
so the table doesn't need the rest of the sheet below the map to come along.
Each sheet also gets a tracks-only image of the same map,
with just the aerial photo and the blue track lines.
"""

import ctypes
import hashlib
import subprocess
import sys
from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path

from curl_cffi import requests
from PIL import ImageDraw, ImageEnhance
from PIL.Image import Image
import pypdfium2.raw as pdfium_c
from pypdfium2 import PdfDocument, PdfObject, PdfPage

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

# The aerial photos in the PEL study are heavily washed out against white.
# A modest contrast boost makes them easier to read in the generated maps.
AERIAL_CONTRAST = 2.0


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


# The stroke color of the IBX light rail track lines.
# The freight tracks, in `FREIGHT_TRACK_COLOR`, are left out.
IBX_TRACK_COLOR = (0, 127, 255)
FREIGHT_TRACK_COLOR = (0, 46, 184)

# A possible tunnel alignment, which the PEL study doesn't have, is drawn in pink.
TUNNEL_COLOR = (255, 20, 147)
# Between the two tunnel tracks' centerlines, the same as the IBX tracks' spacing.
TUNNEL_TRACK_SPACING = 9.7
TUNNEL_LINE_WIDTH = 3
# The freight tracks are kept next to the tunnel, but in black,
# since their dark blue is hard to tell from the IBX tracks' blue.
TUNNEL_FREIGHT_TRACK_COLOR = (0, 0, 0)
# The tunnel's station platforms, like the PEL study's Metropolitan Av ones:
# to either side of the tracks' centerline, and as thick.
TUNNEL_PLATFORM_OFFSET = 12.1
TUNNEL_PLATFORM_WIDTH = 4

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
    # Instead of a corner, where the table's top left goes,
    # in points from the map's top left.
    table_at: tuple[float, float] | None = None
    # Indices of page objects to leave out of the tracks-only image,
    # for tracks other than the ones the image is of.
    # Each track line is drawn as a run of consecutive dash paths.
    other_tracks: tuple[range, ...] = ()
    # For a possible tunnel instead of the street running,
    # the centerline between the freight tracks it's parallel to,
    # in points from the map's top left.
    # It also gets an image of the tracks with the freight tracks and the tunnel.
    freight_centerline: tuple[tuple[float, float], ...] | None = None
    # How far the tunnel's centerline is to the left of the freight centerline.
    tunnel_offset: float = 0
    # Where the tunnel's station platforms start and end, left to right, in points.
    tunnel_station: tuple[float, float] | None = None

    @property
    def file_stem(self) -> str:
        """The name, without spaces, which GitHub turns into dots in release asset names."""
        return "-".join(self.name.lower().replace(" - ", " ").split())

    @property
    def tracks_only_file_stem(self) -> str:
        return f"{self.file_stem}-tracks-only"

    @property
    def tunnel_file_stem(self) -> str:
        return f"{self.file_stem}-tunnel"


SHEETS = [
    Sheet(
        name="IBX PEL Study - BAT Curve - IBX1 LRT-18 - p992",
        page=992,
        # Only the curve into the Brooklyn Army Terminal, not the yard west of it.
        map=Box(left=1216, top=MAP_FRAME.top, right=2115, bottom=MAP_FRAME.bottom),
        table=Box(left=1873, top=689, right=2341, bottom=826),
        corner="right",
        # The main line's IBX1 and IBX2 LRT-19 curves, from the west.
        other_tracks=(range(1418, 1511), range(1524, 1617)),
    ),
    Sheet(
        name="IBX PEL Study - BAT Curves - IBX1 LRT-12 and LRT-18 - p993",
        page=993,
        # The same 2 Av option, drawn rotated, with the reverse curve,
        # from the end of track to the junction with the main line.
        # Down to the lower "Brooklyn Army Terminal" label.
        map=Box(left=220, top=MAP_FRAME.top, right=1530, bottom=632),
        table=Box(left=1873, top=747, right=2341, bottom=846),
        corner="left",
        # Inside the red box, between the BP and TS station labels.
        table_at=(26, 349),
        # The main line's IBX1 and IBX2 LRT-19 curves, from the south.
        other_tracks=(range(2039, 2073), range(2079, 2113)),
    ),
    Sheet(
        name="IBX PEL Study - Street Running Curves - p1014",
        page=1014,
        map=Box(
            left=625, top=MAP_FRAME.top, right=MAP_FRAME.right, bottom=MAP_FRAME.bottom
        ),
        table=Box(left=1847, top=748, right=2134, bottom=1001),
        corner="left",
        # Parallel to the freight tracks, without the tight street curves,
        # from where the IBX tracks leave the Metropolitan Av platforms
        # to the right edge of the map, where they're back by the freight tracks.
        freight_centerline=(
            (0, 155.3),
            (72, 154.3),
            (144, 153.7),
            (216, 152.8),
            (288, 152.3),
            (360, 151.7),
            (432, 151.2),
            (504, 151.2),
            (576, 151.9),
            (648, 153.7),
            (720, 155.3),
            (792, 157),
            (864, 158.4),
            (936, 160.2),
            (1008, 161.8),
            (1080, 163.4),
            (1152, 165.2),
            (1224, 166.9),
            (1296, 168.5),
            (1368, 170.1),
            (1440, 171.7),
            (1512, 173.5),
            (1584, 175),
            (1656, 176.8),
            (1715, 178.2),
        ),
        # As far as the IBX tracks are from the freight tracks at the right edge.
        tunnel_offset=19.8,
        # The Metropolitan Av platforms, moved to the tunnel,
        # since they're up away from the freight tracks to widen the street curve.
        tunnel_station=(24.8, 256.3),
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


def render_page(page: PdfPage) -> Image:
    return page.render(scale=DPI / 72).to_pil().convert("RGB")


def stroke_color(obj: PdfObject) -> tuple[int, int, int]:
    r, g, b, a = (ctypes.c_uint() for _ in range(4))
    pdfium_c.FPDFPageObj_GetStrokeColor(
        obj, ctypes.byref(r), ctypes.byref(g), ctypes.byref(b), ctypes.byref(a)
    )
    return (r.value, g.value, b.value)


def strip_to_tracks(
    page: PdfPage,
    other_tracks: tuple[range, ...],
    colors: tuple[tuple[int, int, int], ...] = (IBX_TRACK_COLOR,),
) -> None:
    """Remove everything but the aerial photos and the track lines.

    The aerial photos are images, and everything drawn over them is vector paths and text,
    so the track lines are just the paths stroked in one of `colors`,
    except for the `other_tracks`.
    """
    for i, obj in enumerate(list(page.get_objects())):
        if obj.type == pdfium_c.FPDF_PAGEOBJ_IMAGE:
            continue
        if (
            obj.type == pdfium_c.FPDF_PAGEOBJ_PATH
            and stroke_color(obj) in colors
            and not any(i in track for track in other_tracks)
        ):
            continue
        page.remove_obj(obj)
    page.gen_content()


def recolor(
    page: PdfPage, old: tuple[int, int, int], new: tuple[int, int, int]
) -> None:
    for obj in page.get_objects():
        if obj.type == pdfium_c.FPDF_PAGEOBJ_PATH and stroke_color(obj) == old:
            pdfium_c.FPDFPageObj_SetStrokeColor(obj, *new, 255)
    page.gen_content()


def offset_line(
    points: list[tuple[float, float]], distance: float
) -> list[tuple[float, float]]:
    """The line `distance` to the left of `points`, in pixels."""
    scale = DPI / 72
    line = []
    for i, (x, y) in enumerate(points):
        # Offset along the normal, from the direction between the neighboring points.
        (x0, y0) = points[max(i - 1, 0)]
        (x1, y1) = points[min(i + 1, len(points) - 1)]
        dx = x1 - x0
        dy = y1 - y0
        length = (dx**2 + dy**2) ** 0.5
        line.append(
            (
                (x + dy / length * distance) * scale,
                (y - dx / length * distance) * scale,
            )
        )
    return line


def between(
    points: tuple[tuple[float, float], ...], start: float, end: float
) -> list[tuple[float, float]]:
    """The part of `points` from `start` to `end`, interpolated every point."""
    result = []
    x = start
    while x <= end:
        i = next(i for i in range(1, len(points)) if points[i][0] >= x)
        (x0, y0), (x1, y1) = points[i - 1], points[i]
        result.append((x, y0 + (y1 - y0) * (x - x0) / (x1 - x0)))
        x += 1
    return result


def draw_tunnel(image: Image, sheet: Sheet) -> None:
    """Draw the tunnel's two tracks, parallel to the freight centerline, and its station."""
    assert sheet.freight_centerline is not None
    scale = DPI / 72
    draw = ImageDraw.Draw(image)
    centerline = list(sheet.freight_centerline)
    for side in (-1, 1):
        draw.line(
            offset_line(
                centerline, sheet.tunnel_offset + side * TUNNEL_TRACK_SPACING / 2
            ),
            fill=TUNNEL_COLOR,
            width=round(TUNNEL_LINE_WIDTH * scale),
            joint="curve",
        )
    if sheet.tunnel_station is not None:
        station = between(sheet.freight_centerline, *sheet.tunnel_station)
        for side in (-1, 1):
            draw.line(
                offset_line(
                    station, sheet.tunnel_offset + side * TUNNEL_PLATFORM_OFFSET
                ),
                fill=TUNNEL_COLOR,
                width=round(TUNNEL_PLATFORM_WIDTH * scale),
            )


def save(image: Image, file_stem: str) -> Path:
    OUT.mkdir(exist_ok=True)
    path = OUT / f"{file_stem}.png"
    image.save(path, optimize=True)
    return path


def make_images(pdf: PdfDocument, sheet: Sheet) -> list[Path]:
    """Make the image with the curve table, the tracks-only one, and any tunnel one."""
    pdf_page = pdf[sheet.page - 1]
    page = render_page(pdf_page)
    map_image = ImageEnhance.Contrast(page.crop(sheet.map.pixels())).enhance(
        AERIAL_CONTRAST
    )
    table = page.crop(sheet.table.pixels())
    if sheet.table_at is not None:
        x, y = (round(v * DPI / 72) for v in sheet.table_at)
    else:
        y = map_image.height - table.height
        x = 0 if sheet.corner == "left" else map_image.width - table.width
    map_image.paste(table, (x, y))
    path = save(map_image, sheet.file_stem)
    paths = [path]
    # These modify the page in `pdf`, so they go after rendering it as is.
    if sheet.freight_centerline is not None:
        strip_to_tracks(
            pdf_page, sheet.other_tracks, (IBX_TRACK_COLOR, FREIGHT_TRACK_COLOR)
        )
        recolor(pdf_page, FREIGHT_TRACK_COLOR, TUNNEL_FREIGHT_TRACK_COLOR)
        tunnel = ImageEnhance.Contrast(
            render_page(pdf_page).crop(sheet.map.pixels())
        ).enhance(AERIAL_CONTRAST)
        draw_tunnel(tunnel, sheet)
        tunnel_path = save(tunnel, sheet.tunnel_file_stem)
        # The `other_tracks` are gone, and the indices of what's left have changed.
        strip_to_tracks(pdf_page, ())
    else:
        strip_to_tracks(pdf_page, sheet.other_tracks)
    tracks_only = ImageEnhance.Contrast(
        render_page(pdf_page).crop(sheet.map.pixels())
    ).enhance(AERIAL_CONTRAST)
    paths.append(save(tracks_only, sheet.tracks_only_file_stem))
    if sheet.freight_centerline is not None:
        paths.append(tunnel_path)
    return paths


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
    paths = [path for sheet in SHEETS for path in make_images(pdf, sheet)]
    for path in paths:
        print(path)
    if args.upload:
        upload(paths)


if __name__ == "__main__":
    main()
