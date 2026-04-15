from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parent
ICON_PATH = ROOT / "cyber-hax-store-icon.png"

WIDTH = 1024
HEIGHT = 500

BG = "#061018"
PANEL = "#0F1A24"
LINE = "#1F5164"
CYAN = "#49F0CF"
WHITE = "#F2FCFF"
TEXT = "#CDE7EF"
MUTED = "#8CAEBB"
DEEP = "#0D1C28"
MID = "#173147"


def font(size: int, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = []
    if mono:
      candidates.extend(
          [
              "C:/Windows/Fonts/consolab.ttf" if bold else "C:/Windows/Fonts/consola.ttf",
              "C:/Windows/Fonts/cascadiacode.ttf",
          ]
      )
    else:
      candidates.extend(
          [
              "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
              "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
              "C:/Windows/Fonts/bahnschrift.ttf",
          ]
      )
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def glow(draw_target: Image.Image, box: tuple[int, int, int, int], radius: int, fill: str, blur: int) -> None:
    layer = Image.new("RGBA", draw_target.size, (0, 0, 0, 0))
    layer_draw = ImageDraw.Draw(layer)
    layer_draw.rounded_rectangle(box, radius=radius, fill=fill)
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    draw_target.alpha_composite(layer)


def circle_glow(draw_target: Image.Image, center: tuple[int, int], radius: int, fill: str, blur: int) -> None:
    layer = Image.new("RGBA", draw_target.size, (0, 0, 0, 0))
    layer_draw = ImageDraw.Draw(layer)
    x, y = center
    layer_draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    draw_target.alpha_composite(layer)


def network_background(base: Image.Image, variant_shift: int = 0) -> None:
    draw = ImageDraw.Draw(base)
    circle_glow(base, (870, 120), 210, (20, 60, 86, 120), 24)
    circle_glow(base, (170, 430), 230, (12, 32, 47, 150), 24)

    for y in (110, 390):
        draw.line((96, y, 928, y), fill=LINE, width=2)

    path_y = HEIGHT // 2 + variant_shift
    draw.line((176, path_y, 848, path_y), fill=(73, 240, 207, 145), width=3)
    for offset in range(176, 848, 32):
        draw.line((offset, path_y, offset + 12, path_y), fill=(31, 81, 100, 255), width=3)

    nodes = [
        (236, path_y, CYAN),
        (408, path_y, WHITE),
        (588, path_y, CYAN),
        (760, path_y, WHITE),
    ]
    for x, y, color in nodes:
        circle_glow(base, (x, y), 22, (73, 240, 207, 80) if color == CYAN else (242, 252, 255, 64), 12)
        draw.ellipse((x - 16, y - 16, x + 16, y + 16), fill=color)


def pill(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, fill: str, stroke: str, text_fill: str) -> None:
    padding_x = 18
    padding_y = 10
    label_font = font(21, bold=True, mono=True)
    bbox = draw.textbbox((0, 0), text, font=label_font)
    width = bbox[2] - bbox[0] + padding_x * 2
    height = bbox[3] - bbox[1] + padding_y * 2
    draw.rounded_rectangle((x, y, x + width, y + height), radius=height // 2, fill=fill, outline=stroke, width=2)
    draw.text((x + padding_x, y + padding_y - 2), text, fill=text_fill, font=label_font)


def place_icon(base: Image.Image, x: int, y: int, size: int, halo: tuple[int, int, int, int]) -> None:
    icon = Image.open(ICON_PATH).convert("RGBA").resize((size, size), Image.LANCZOS)
    circle_glow(base, (x + size // 2, y + size // 2), size // 2 - 8, halo, 18)
    base.alpha_composite(icon, (x, y))


def add_footer(draw: ImageDraw.ImageDraw, text: str) -> None:
    footer_font = font(23)
    draw.text((98, 434), text, fill=MUTED, font=footer_font)


def draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
    text_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: str,
    *,
    line_gap: int = 10,
) -> int:
    left, top, right, bottom = box
    words = text.split()
    lines: list[str] = []
    current = ""
    max_width = right - left

    for word in words:
        candidate = f"{current} {word}".strip()
        width = draw.textbbox((0, 0), candidate, font=text_font)[2]
        if current and width > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)

    y = top
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=text_font)
        line_height = bbox[3] - bbox[1]
        if y + line_height > bottom:
            break
        draw.text((left, y), line, fill=fill, font=text_font)
        y += line_height + line_gap
    return y


def option_one() -> Image.Image:
    base = Image.new("RGBA", (WIDTH, HEIGHT), BG)
    network_background(base)
    draw = ImageDraw.Draw(base)

    glow(base, (74, 72, 586, 426), radius=38, fill=(10, 20, 31, 214), blur=10)
    draw.rounded_rectangle((74, 72, 586, 426), radius=38, fill=PANEL, outline=LINE, width=3)
    draw.text((114, 112), "CYBER HAX", fill=CYAN, font=font(26, bold=True, mono=True))
    draw.text((114, 156), "Hack the network.", fill=WHITE, font=font(56, bold=True))
    draw_wrapped_text(
        draw,
        "Two-player live cyber duels with instant public matchmaking and private room invites.",
        (114, 238, 526, 322),
        font(28),
        TEXT,
        line_gap=8,
    )
    pill(draw, 114, 348, "LIVE MATCHMAKING", (14, 28, 40, 232), "#49F0CF", CYAN)
    pill(draw, 384, 348, "PRIVATE ROOMS", (14, 28, 40, 232), "#1F5164", WHITE)

    place_icon(base, 688, 112, 224, (73, 240, 207, 76))
    draw.rounded_rectangle((648, 360, 928, 418), radius=26, fill=(12, 24, 36, 220), outline=(31, 81, 100, 144), width=2)
    draw.text((676, 378), "Fast browser battles. Clear cyber visuals.", fill=MUTED, font=font(22))
    return base.convert("RGB")


def option_two() -> Image.Image:
    base = Image.new("RGBA", (WIDTH, HEIGHT), BG)
    network_background(base, variant_shift=12)
    draw = ImageDraw.Draw(base)

    glow(base, (62, 64, 962, 436), radius=44, fill=(8, 18, 28, 168), blur=18)
    draw.rounded_rectangle((62, 64, 962, 436), radius=44, outline=(31, 81, 100, 188), width=2)

    draw.text((96, 98), "CYBER HAX v5", fill=CYAN, font=font(24, bold=True, mono=True))
    draw.text((96, 144), "Trace. Exploit. Breach first.", fill=WHITE, font=font(54, bold=True))
    draw_wrapped_text(
        draw,
        "Public matchmaking and private room duels in one lightweight cyber battleground.",
        (96, 226, 540, 314),
        font(27),
        TEXT,
        line_gap=8,
    )

    pill(draw, 96, 336, "PUBLIC MATCHES", (12, 24, 36, 225), "#49F0CF", CYAN)
    pill(draw, 336, 336, "MOBILE READY", (12, 24, 36, 225), "#1F5164", WHITE)

    place_icon(base, 736, 94, 178, (73, 240, 207, 66))

    draw.rounded_rectangle((624, 286, 930, 392), radius=28, fill=(15, 26, 36, 228), outline=(31, 81, 100, 140), width=2)
    draw.text((652, 316), "Private room links", fill=WHITE, font=font(24, bold=True))
    draw.text((652, 350), "Reconnect-safe live sessions", fill=MUTED, font=font(22))
    return base.convert("RGB")


def option_three() -> Image.Image:
    base = Image.new("RGBA", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(base)

    circle_glow(base, (844, 92), 160, (73, 240, 207, 62), 28)
    circle_glow(base, (188, 420), 220, (14, 28, 40, 190), 26)

    for x in range(74, 970, 70):
        draw.line((x, 118, x + 42, 118), fill=(31, 81, 100, 115), width=2)
        draw.line((x, 382, x + 42, 382), fill=(31, 81, 100, 115), width=2)

    draw.rounded_rectangle((82, 86, 566, 414), radius=38, fill=(10, 20, 31, 230), outline=(31, 81, 100, 185), width=3)
    draw.text((116, 124), "CYBER HAX", fill=CYAN, font=font(24, bold=True, mono=True))
    draw.text((116, 166), "Live cyber duels", fill=WHITE, font=font(54, bold=True))
    draw_wrapped_text(
        draw,
        "Pair with a stranger or challenge a friend. Own the graph before they own you.",
        (116, 244, 508, 320),
        font(27),
        TEXT,
        line_gap=8,
    )

    pill(draw, 116, 344, "ANDROID FEATURED", (14, 28, 40, 225), "#49F0CF", CYAN)
    pill(draw, 350, 344, "QUICK MATCH", (14, 28, 40, 225), "#1F5164", WHITE)

    place_icon(base, 690, 98, 216, (73, 240, 207, 72))

    draw.line((610, 250, 940, 250), fill=(73, 240, 207, 150), width=4)
    for x, color in ((656, CYAN), (742, WHITE), (834, CYAN), (920, WHITE)):
        circle_glow(base, (x, 250), 20, (73, 240, 207, 72) if color == CYAN else (242, 252, 255, 50), 10)
        draw.ellipse((x - 14, 236, x + 14, 264), fill=color)

    draw.rounded_rectangle((610, 368, 942, 420), radius=24, fill=(12, 24, 36, 220), outline=(31, 81, 100, 140), width=2)
    draw.text((636, 384), "Quick matchmaking and clean mobile controls.", fill=MUTED, font=font(22))
    return base.convert("RGB")


def main() -> None:
    outputs = {
        "cyber-hax-feature-graphic-option-1.png": option_one(),
        "cyber-hax-feature-graphic-option-2.png": option_two(),
        "cyber-hax-feature-graphic-option-3.png": option_three(),
    }
    for filename, image in outputs.items():
        path = ROOT / filename
        image.save(path, format="PNG", optimize=True)
        print(path)


if __name__ == "__main__":
    main()
