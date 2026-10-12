# IBX PEL track map images

Images of curves on the Interborough Express (IBX) light rail alignment,
cropped from the track plan sheets in the MTA's IBX
[Planning and Environmental Linkages (PEL) study](https://www.mta.info/document/114891)
(`IBX PEL Final April 2023 v.5.pdf`, with its appendices, 1077 pages).

On each sheet, the curve table (radius, speed, etc.)
sits below the track map, past the profile.
So a screenshot that includes both is mostly wasted space.
`ibx-pel-track-map-images` instead crops the track map
and moves the sheet's curve table into a bottom corner of it.

| Image | PDF page | Table goes in |
| --- | --- | --- |
| BAT Curve: `IBX1 LRT-18`, the 2 Av option into the Brooklyn Army Terminal | 992 | bottom right |
| BAT Curves: `IBX1 LRT-12` and `LRT-18`, the same 2 Av option, drawn rotated, with its reverse curve out to the end of track | 993 | inside the red box |
| Street Running Curves: `LRT-641` through `LRT-664`, around Metropolitan Av and 69 St | 1014 | bottom left |

Each is cropped to its curves:
the BAT one ends just right of the `IBX2 LRT-19` label, so the table doesn't cover it,
and the street-running one starts at the Metropolitan Av IBX platforms.
To fit the street-running table there without covering the track,
it keeps only the LRT rows and the `CURVE #`, `RADIUS (FT)`, and `V (MPH)` columns;
the LRT rows are blank in the other columns,
and the `BAY-631` and `BAY-643` rows are freight curves.

Each also has a tracks-only image of the same map,
with just the aerial photo and the IBX tracks in blue,
without the freight tracks, any labels or linework, or the curve table.
The BAT ones also leave out the main line's `LRT-19` curves,
so only the tracks curving to 2 Av are left.

The street-running one also has a tunnel image,
with the IBX tracks, the freight tracks in black,
and a possible tunnel alignment in pink.
The PEL study doesn't have a tunnel, so it's only a guess:
parallel to the freight tracks the whole way,
as far from them as the IBX tracks are at the right edge,
without the tight street curves.
The Metropolitan Av platforms are up away from the freight tracks
to widen the street curve,
so the tunnel has its own platforms, in pink, moved down to its tracks.

## Images

### BAT curve (page 992)

![BAT curve, page 992](https://github.com/kkysen/ibx-pel-track-map-images/releases/download/images/ibx-pel-study-bat-curve-ibx1-lrt-18-p992.png)

![BAT curve, page 992, tracks only](https://github.com/kkysen/ibx-pel-track-map-images/releases/download/images/ibx-pel-study-bat-curve-ibx1-lrt-18-p992-tracks-only.png)

### BAT curves, with the reverse curve (page 993)

![BAT curves with the reverse curve, page 993](https://github.com/kkysen/ibx-pel-track-map-images/releases/download/images/ibx-pel-study-bat-curves-ibx1-lrt-12-and-lrt-18-p993.png)

![BAT curves with the reverse curve, page 993, tracks only](https://github.com/kkysen/ibx-pel-track-map-images/releases/download/images/ibx-pel-study-bat-curves-ibx1-lrt-12-and-lrt-18-p993-tracks-only.png)

### Street-running curves (page 1014)

![Street-running curves, page 1014](https://github.com/kkysen/ibx-pel-track-map-images/releases/download/images/ibx-pel-study-street-running-curves-p1014.png)

![Street-running curves, page 1014, with a possible tunnel](https://github.com/kkysen/ibx-pel-track-map-images/releases/download/images/ibx-pel-study-street-running-curves-p1014-tunnel.png)

![Street-running curves, page 1014, tracks only](https://github.com/kkysen/ibx-pel-track-map-images/releases/download/images/ibx-pel-study-street-running-curves-p1014-tracks-only.png)

## Usage

```sh
uv run ibx-pel-track-map-images
```

This needs only [`uv`](https://docs.astral.sh/uv/),
which installs the dependencies from `pyproject.toml`.
It:

1. Downloads the PEL study into `cache/`, once,
   and checks its SHA-256.
   It tries `mta.info` first,
   which returns 403 to clients that don't look like a browser,
   so this uses `curl_cffi` to impersonate Chrome.
   If that fails or the hash differs, as if the MTA moved or changed the PDF,
   it falls back to the Wayback Machine's copy, which is identical but much slower.
2. Renders each page at 200 DPI with `pypdfium2`.
3. Crops the map and the table, pastes the table into the map's corner,
   and writes a PNG to `out/`.
4. Removes everything from the page but the aerial photos and the IBX track lines,
   renders it again, and writes the same crop as a `-tracks-only` PNG.
   The aerial photos are images and everything over them is vector paths and text,
   so the track lines are the paths stroked in `IBX_TRACK_COLOR`.
   Each track is a run of consecutive dash paths,
   so a sheet's `other_tracks` leaves out tracks by their page object indices.

`cache/` and `out/` aren't committed.

## Uploading the images

On every push to `main`,
the [CI workflow](.github/workflows/ci.yml) runs

```sh
uv run ibx-pel-track-map-images --upload
```

On PRs, it makes the images without uploading them,
and attaches them to the run as an `images` artifact to preview.
It caches `cache/` keyed by the PEL study's hash,
so it only downloads the PDF once.
It can also be run by hand, from the Actions tab or locally.

The images above aren't in git,
so that regenerating them doesn't grow the repo's history.
They're assets of the [`images` release](https://github.com/kkysen/ibx-pel-track-map-images/releases/tag/images) instead,
which `--upload` creates if needed
and then replaces each image in with `gh release upload --clobber`.
Their URLs stay the same, so this README needn't change.
Old versions of the images aren't kept.

Locally, this needs [`gh`](https://cli.github.com/), logged in with write access to the repo,
and the release needs at least one commit pushed to tag.

## Crop boxes

The boxes in `SHEETS` are in PDF points from the top left of the page as displayed (landscape),
measured from the rendered pages:
the map frame from where the aerial photo's color starts and stops,
and each table from its outer border lines.
To add a sheet, measure the same way and add a `Sheet` to `SHEETS`.
