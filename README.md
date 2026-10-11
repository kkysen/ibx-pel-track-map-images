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
| BAT Curves: `IBX1 LRT-12` and `LRT-18`, the same 2 Av option, drawn rotated, with its reverse curve out to the end of track | 993 | bottom left |
| Street Running Curves: `LRT-641` through `LRT-664`, around Metropolitan Av and 69 St | 1014 | bottom left |

The images are meant to sit side by side on a web page,
so each is cropped as narrow as its curves allow:
the BAT one ends just right of the `IBX2 LRT-19` label, so the table doesn't cover it,
and the street-running one starts at the Metropolitan Av IBX platforms.
To fit the street-running table there without covering the track,
it keeps only the LRT rows and the `CURVE #`, `RADIUS (FT)`, and `V (MPH)` columns;
the LRT rows are blank in the other columns,
and the `BAY-631` and `BAY-643` rows are freight curves.

## Images

![BAT curve, page 992](https://github.com/kkysen/ibx-pel-track-map-images/releases/download/images/ibx-pel-study-bat-curve-ibx1-lrt-18-p992.png)

![BAT curves with the reverse curve, page 993](https://github.com/kkysen/ibx-pel-track-map-images/releases/download/images/ibx-pel-study-bat-curves-ibx1-lrt-12-and-lrt-18-p993.png)

![Street-running curves, page 1014](https://github.com/kkysen/ibx-pel-track-map-images/releases/download/images/ibx-pel-study-street-running-curves-p1014.png)

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
