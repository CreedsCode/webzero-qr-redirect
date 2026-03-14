"""
Generate QR codes for WebZero event activation redirect URLs.

The QR code encodes the full server URL, e.g.:
    https://YOUR_DOMAIN/get/luma
    https://YOUR_DOMAIN/get/zodl-android

Anyone can scan the QR with any reader and see exactly which URL
it points to before visiting it. The /destinations endpoint on that
server then publicly confirms where the redirect leads.

Usage:
    python generate_qr.py --base-url https://your-domain.com

    # Generate only specific slugs:
    python generate_qr.py --base-url https://your-domain.com --slugs luma zodl-android

Output (one PNG + SVG per slug):
    qr/luma.png           qr/luma.svg
    qr/zodl-android.png   qr/zodl-android.svg
    ...
"""

import argparse
from pathlib import Path

try:
    import qrcode
    import qrcode.image.svg
    from PIL import Image
except ImportError:
    raise SystemExit("Missing dependencies. Run:  pip install qrcode[pil] Pillow")

# Default slugs — mirrors DESTINATIONS in server.py.
# Override at runtime with --slugs to generate a subset.
DEFAULT_SLUGS = [
    "luma",
    "intern",
    "zodl-ios",
    "zodl-android",
    "zodl-fdroid",
    "cake-ios",
    "cake-android",
    "cake-apk",
]

# WebZero brand colors
FILL_COLOR = "#04CC04"
BACK_COLOR = "#252525"


def make_qr_png(url: str, out_path: Path) -> None:
    qr = qrcode.QRCode(
        version=None,  # auto-size
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # 30% recovery
        box_size=12,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color=FILL_COLOR, back_color=BACK_COLOR)
    img.save(out_path)
    print(f"  PNG -> {out_path}  ({url})")


def make_qr_svg(url: str, out_path: Path) -> None:
    factory = qrcode.image.svg.SvgPathImage
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        image_factory=factory,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image()
    img.save(out_path)
    print(f"  SVG -> {out_path}  ({url})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate WebZero event QR codes")
    parser.add_argument(
        "--base-url",
        required=True,
        help="Base URL of your deployed server, e.g. https://qr.joinwebzero.com",
    )
    parser.add_argument(
        "--slugs",
        nargs="+",
        default=DEFAULT_SLUGS,
        help="Slugs to generate (default: all). e.g. --slugs luma zodl-android",
    )
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    out_dir = Path("qr")
    out_dir.mkdir(exist_ok=True)

    print(f"\nGenerating QR codes pointing to {base}/get/<slug>\n")
    for slug in args.slugs:
        url = f"{base}/get/{slug}"
        make_qr_png(url, out_dir / f"{slug}.png")
        make_qr_svg(url, out_dir / f"{slug}.svg")

    print(f"\nDone. Files in ./{out_dir}/")
    print("\nAnyone can verify destinations at:")
    print(f"  {base}/destinations")
    print("\nLive counts at:")
    print(f"  {base}/stats")


if __name__ == "__main__":
    main()
