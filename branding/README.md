# Branding

The mark shows a crop's greenness curve. A cloud hides its peak, and radar (amber) fills the gap.

| File | Use |
|---|---|
| `mark.svg`, `mark-512.png` | Avatar and icon (organization profile picture) |
| `mark-64.png` | Small icon / favicon |
| `banner.svg`, `banner.png` | Dark banner: README header, social preview (1280×640) |
| `banner-light.svg`, `banner-light.png` | Light banner for white backgrounds |

Colours: field green `#0A231C`–`#143F33`, leaf green `#8FD14F`, radar amber `#F2A33A`, cloud `#EAF2EE`.
Wordmark font: Inter (800 / 500 / 600).

Re-render the PNGs after editing an SVG (needs `cairosvg`, not part of the main requirements):

```bash
uv pip install --python .venv/bin/python cairosvg
.venv/bin/python -c "import cairosvg; cairosvg.svg2png(url='branding/mark.svg', write_to='branding/mark-512.png', output_width=512, output_height=512)"
```
