"""Convert the downloaded Noto Sans KR variable font to a static Regular TTF."""
from __future__ import annotations

import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont


def main() -> None:
    source = Path(sys.argv[1] if len(sys.argv) > 1 else "assets/fonts/NotoSansKR[wght].ttf")
    output = Path(sys.argv[2] if len(sys.argv) > 2 else "assets/fonts/NotoSansKR-Regular.ttf")
    if not source.is_file() or source.stat().st_size < 10_000:
        raise SystemExit(f"Source Korean font is missing or incomplete: {source}")
    font = TTFont(str(source))
    axes = {
        axis.axisTag: axis.defaultValue for axis in font["fvar"].axes
    } if "fvar" in font else {}
    if "wght" in axes:
        axes["wght"] = 400
    if axes:
        font = instantiateVariableFont(font, axes, inplace=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    font.save(str(output))
    if output.stat().st_size < 10_000:
        raise SystemExit(f"Generated Korean font is unexpectedly small: {output}")
    print(f"Prepared static Korean font: {output} ({output.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
