# IBX PEL track map images

Images of curves on the Interborough Express (IBX) light rail alignment,
cropped from the track plan sheets in the MTA's IBX
[Planning and Environmental Linkages (PEL) study](https://www.mta.info/document/114891)
(`IBX PEL Final April 2023 v.5.pdf`, with its appendices, 1077 pages).

On each sheet, the curve table (radius, speed, etc.)
sits below the track map, past the profile.
So a screenshot that includes both is mostly wasted space.
`make_images.py` instead crops the track map
and moves the sheet's curve table into a bottom corner of it.

| Image | PDF page | Table goes in |
| --- | --- | --- |
| BAT Curve: `IBX1 LRT-18`, the 2 Av option into the Brooklyn Army Terminal | 992 | bottom right |
| Street Running Curves: `LRT-641` through `LRT-664`, around Metropolitan Av and 69 St | 1014 | bottom left |

## Usage

```sh
./make_images.py
```

This needs only [`uv`](https://docs.astral.sh/uv/),
which installs the script's dependencies from its inline metadata.
It:

1. Downloads the PEL study into `cache/`, once.
   `mta.info` returns 403 to clients that don't look like a browser,
   so this uses `curl_cffi` to impersonate Chrome.
2. Renders each page at 200 DPI with `pypdfium2`.
3. Crops the map and the table, pastes the table into the map's corner,
   and writes a PNG to `out/`.

`cache/` and `out/` aren't committed.

## Crop boxes

The boxes in `SHEETS` are in PDF points from the top left of the page as displayed (landscape),
measured from the rendered pages:
the map frame from where the aerial photo's color starts and stops,
and each table from its outer border lines.
To add a sheet, measure the same way and add a `Sheet` to `SHEETS`.
