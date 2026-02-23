#!/usr/bin/env python3
"""PlantUML diagram renderer.

Renders any PlantUML markup to SVG or PNG via the public PlantUML server.
No third-party dependencies — uses only the Python standard library.

Usage:
    python gen_diagram.py input.puml [output.svg]
    python gen_diagram.py input.puml output.png --format png
    cat diagram.puml | python gen_diagram.py - output.svg
"""

import argparse
import os
import sys
import urllib.request
import zlib


def encode_plantuml(text: str) -> str:
    """Encode PlantUML text using the server's custom base64 encoding."""
    compressed = zlib.compress(text.encode("utf-8"))[2:-4]
    mapping = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"
    res = ""
    for i in range(0, len(compressed), 3):
        if i + 2 < len(compressed):
            b1, b2, b3 = compressed[i], compressed[i + 1], compressed[i + 2]
        elif i + 1 < len(compressed):
            b1, b2, b3 = compressed[i], compressed[i + 1], 0
        else:
            b1, b2, b3 = compressed[i], 0, 0
        res += mapping[b1 >> 2]
        res += mapping[((b1 & 0x3) << 4) | (b2 >> 4)]
        res += mapping[((b2 & 0xF) << 2) | (b3 >> 6)]
        res += mapping[b3 & 0x3F]
    return res


def render_diagram(plantuml_text: str, output_path: str, fmt: str = "svg") -> str:
    """Render PlantUML markup and save to output_path. Returns the output path."""
    encoded = encode_plantuml(plantuml_text)
    url = f"https://www.plantuml.com/plantuml/{fmt}/{encoded}"
    print(f"Rendering {fmt.upper()} via PlantUML server...")
    print(f"URL: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "gen_diagram/1.0"})
    with urllib.request.urlopen(req) as response:
        data = response.read()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(data)
    print(f"Saved: {output_path} ({len(data):,} bytes)")
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Render PlantUML diagrams to SVG or PNG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python gen_diagram.py schema.puml
  python gen_diagram.py schema.puml output.svg
  python gen_diagram.py schema.puml output.png --format png
  cat schema.puml | python gen_diagram.py - output.svg
        """,
    )
    parser.add_argument("input", help="Input .puml file path, or - for stdin")
    parser.add_argument(
        "output",
        nargs="?",
        help="Output path (default: input basename with .svg or .png extension)",
    )
    parser.add_argument(
        "--format",
        choices=["svg", "png"],
        default="svg",
        help="Output format (default: svg)",
    )
    args = parser.parse_args()

    if args.input == "-":
        plantuml_text = sys.stdin.read()
    else:
        with open(args.input, "r", encoding="utf-8") as f:
            plantuml_text = f.read()

    if args.output:
        output_path = args.output
    elif args.input != "-":
        base = os.path.splitext(os.path.abspath(args.input))[0]
        output_path = f"{base}.{args.format}"
    else:
        output_path = f"diagram.{args.format}"

    render_diagram(plantuml_text, output_path, args.format)


if __name__ == "__main__":
    main()
