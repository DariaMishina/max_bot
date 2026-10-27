"""Export the code-native Android brand mark to RuStore PNG and a size proof.

Requires rsvg-convert (librsvg). The Android vector is the single source of truth.
Run from the repository root: python3 scripts/export_android_brand.py
"""
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/design/workshop-refinement"
ANDROID = "{http://schemas.android.com/apk/res/android}"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    vector = ET.parse(ROOT / "android/app/src/main/res/drawable/sphere_mark.xml").getroot()
    paths = []
    mapping = {"pathData": "d", "fillColor": "fill", "strokeColor": "stroke",
               "strokeWidth": "stroke-width", "strokeLineCap": "stroke-linecap"}
    for child in vector:
        attrs = {mapping[key.removeprefix(ANDROID)]: value
                 for key, value in child.attrib.items() if key.removeprefix(ANDROID) in mapping}
        if attrs.get("fill") == "#00000000":
            attrs["fill"] = "none"
        paths.append(ET.tostring(ET.Element("path", attrs), encoding="unicode"))
    mark = "".join(paths)
    # Same inset as adaptive-icon foreground. Background is opaque for RuStore.
    artwork = '<rect width="108" height="108" fill="#F6F1E8"/>' + \
              '<g transform="translate(10 10) scale(0.8148148148)">' + mark + '</g>'
    # Launcher masks expose the central 72/108 dp area of an adaptive icon.
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="18 18 72 72">' + artwork + '</svg>'
    source = OUT / "tarot-sphere-rustore-icon.svg"
    source.write_text(svg)
    subprocess.run(["rsvg-convert", str(source), "-o", str(OUT / "tarot-sphere-rustore-icon.png")], check=True)
    proof = '<svg xmlns="http://www.w3.org/2000/svg" width="860" height="400"><rect width="860" height="400" fill="#FFFDF9"/>'
    for x, y, size in [(24, 24, 320), (390, 60, 128), (560, 60, 64), (665, 60, 48), (755, 60, 32)]:
        proof += f'<svg x="{x}" y="{y}" width="{size}" height="{size}" viewBox="18 18 72 72">{artwork}</svg>'
        proof += f'<text x="{x}" y="{y + size + 24}" font-family="sans-serif" font-size="14" fill="#302824">{size} px</text>'
    proof += '</svg>'
    proof_path = OUT / "icon-size-proof.svg"
    proof_path.write_text(proof)
    subprocess.run(["rsvg-convert", str(proof_path), "-o", str(OUT / "icon-size-proof.png")], check=True)
    print(OUT)


if __name__ == "__main__":
    main()
