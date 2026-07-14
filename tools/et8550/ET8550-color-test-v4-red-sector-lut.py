#!/usr/bin/env python3
"""ET-8550 Color Test v4 — fuldt farvekort med lokal red-sector 3D-LUT."""
from __future__ import annotations

import colorsys
import math
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageFilter, ImageFont

APP_NAME = "ET-8550 Color Test v4 — Red Sector LUT"
DEFAULT_IP = "10.32.200.7"
DEFAULT_PORT = 9100
DEFAULT_PPD = Path.home() / "et8550-ppd" / "Epson-ET-8550-Gutenprint-5.3.5.ppd"
IMAGE_TO_RASTER = Path("/usr/lib/cups/filter/imagetoraster")
RASTER_TO_GUTENPRINT = Path("/usr/lib/cups/filter/rastertogutenprint.5.3")

PAGE_W_MM = 106.0
PAGE_H_MM = 152.0
LABEL_W_MM = 102.0
LABEL_H_MM = 152.0

# Kilden skal altid have kvadratiske pixels. Printermoden vælges separat nedenfor.
SOURCE_DPI = 720

# PPD-valgene genereret fra model_139.xml.
# Kun 1440x720dpi er fysisk valideret indtil videre.
RESOLUTIONS = [
    ("1440 × 1440 DPI HighPhoto — VALIDERET", "1440x1440dpi"),
]
RESOLUTION_BY_LABEL = dict(RESOLUTIONS)
DEFAULT_RESOLUTION_LABEL = "1440 × 1440 DPI HighPhoto — VALIDERET"


def mmpt(mm: float) -> float:
    return mm * 72.0 / 25.4


def px(mm: float) -> int:
    return round(mm / 25.4 * SOURCE_DPI)


def page_size() -> str:
    return f"Custom.{mmpt(PAGE_W_MM):.3f}x{mmpt(PAGE_H_MM):.3f}"


def get_font(size: int):
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ):
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()



# Fysisk kalibreringspunkt:
# sRGB (255, 0, 36) blev valgt som den reneste fysiske røde.
RED_SHIFT_DEGREES = -8.470588235294116
RED_SECTOR_HALF_WIDTH_DEGREES = 30.0
RED_LUT_SIZE = 65


def red_sector_transform(r: float, g: float, b: float) -> tuple[float, float, float]:
    """Lokal hue-rotation omkring ren rød.

    Color3DLUT giver r, g og b i intervallet 0..1.
    Maksimal rotation sker ved hue 0°. Den fader glat til nul ved ±30°.
    Neutrale og svagt mættede farver røres praktisk talt ikke.
    """
    h, s, v = colorsys.rgb_to_hsv(r, g, b)

    # Korteste signed hue-afstand fra rød i omdrejninger: -0.5..+0.5.
    distance = ((h + 0.5) % 1.0) - 0.5
    half_width = RED_SECTOR_HALF_WIDTH_DEGREES / 360.0

    if abs(distance) >= half_width or s <= 0.05 or v <= 0.02:
        return r, g, b

    # Cosine taper: 1.0 ved ren rød, 0.0 ved sektorens kanter.
    position = abs(distance) / half_width
    hue_weight = 0.5 * (1.0 + math.cos(math.pi * position))

    # Mættede farver får fuld korrektion; pasteller påvirkes blødere.
    weight = hue_weight * (s ** 1.35)

    shifted_h = (h + (RED_SHIFT_DEGREES / 360.0) * weight) % 1.0
    return colorsys.hsv_to_rgb(shifted_h, s, v)


RED_SECTOR_LUT = ImageFilter.Color3DLUT.generate(
    RED_LUT_SIZE,
    red_sector_transform,
    channels=3,
)


def apply_red_sector_lut(image: Image.Image) -> Image.Image:
    if image.mode != "RGB":
        image = image.convert("RGB")
    return image.filter(RED_SECTOR_LUT)


def validate_red_sector_lut() -> None:
    red = red_sector_transform(1.0, 0.0, 0.0)
    red_u8 = tuple(round(channel * 255) for channel in red)

    orange = red_sector_transform(1.0, 128 / 255.0, 0.0)
    orange_u8 = tuple(round(channel * 255) for channel in orange)

    magenta = red_sector_transform(1.0, 0.0, 1.0)
    magenta_u8 = tuple(round(channel * 255) for channel in magenta)

    if red_u8 != (255, 0, 36):
        raise RuntimeError(f"Red LUT-validering fejlede: {red_u8} != (255, 0, 36)")
    if orange_u8 != (255, 128, 0):
        raise RuntimeError(f"Orange blev utilsigtet ændret: {orange_u8}")
    if magenta_u8 != (255, 0, 255):
        raise RuntimeError(f"Magenta blev utilsigtet ændret: {magenta_u8}")


validate_red_sector_lut()

def make_test_png(path: Path, resolution_label: str) -> tuple[int, int]:
    width, height = px(PAGE_W_MM), px(PAGE_H_MM)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    thin = max(2, px(0.18))
    medium = max(3, px(0.30))
    x0 = px(3.0)
    x1 = px(103.0)
    content_w = x1 - x0

    title_font = get_font(max(18, px(4.0)))
    body_font = get_font(max(13, px(2.6)))
    label_font = get_font(max(13, px(2.7)))

    def centered(box, label, fill=(0, 0, 0), font=body_font):
        bx0, by0, bx1, by1 = box
        bbox = draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text(
            ((bx0 + bx1 - tw) / 2, (by0 + by1 - th) / 2 - bbox[1]),
            label,
            fill=fill,
            font=font,
        )

    def patch(box, color, label, text_fill=None):
        bx0, by0, bx1, by1 = box
        draw.rectangle(box, fill=color, outline=(0, 0, 0), width=thin)
        if text_fill is None:
            lum = 0.2126 * color[0] + 0.7152 * color[1] + 0.0722 * color[2]
            text_fill = (0, 0, 0) if lum > 145 else (255, 255, 255)
        centered((bx0, by0, bx1, by0 + px(5.5)), label, fill=text_fill, font=label_font)

    centered((x0, px(2), x1, px(8)), "ET-8550 FARVETEST v4 · RED LUT", font=title_font)
    centered(
        (x0, px(8), x1, px(13)),
        "RED→RGB 255,0,36 · ±30° TAPER · 1440 × 1440 · BIDIRECTIONAL",
        font=body_font,
    )

    # Exact 100 mm geometry reference.
    y_ref = px(15.0)
    draw.line((x0, y_ref, x1, y_ref), fill=(0, 0, 0), width=medium)
    for mm, label in ((0, "0"), (50, "50"), (100, "100 mm")):
        xx = x0 + round(content_w * mm / 100)
        draw.line((xx, y_ref - px(1.4), xx, y_ref + px(1.4)), fill=(0, 0, 0), width=medium)
        if mm == 0:
            draw.text((xx, y_ref + px(1.5)), label, fill=(0, 0, 0), font=body_font)
        elif mm == 100:
            bbox = draw.textbbox((0, 0), label, font=body_font)
            draw.text((xx - (bbox[2] - bbox[0]), y_ref + px(1.5)), label, fill=(0, 0, 0), font=body_font)
        else:
            centered((xx - px(6), y_ref + px(1.3), xx + px(6), y_ref + px(5.8)), label)

    # Large core colors.
    colors_y0 = px(23)
    colors_y1 = px(52)
    gap = px(2)
    col_w = (content_w - gap * 4) // 5
    core = [
        ((0, 0, 0), "SORT"),
        ((128, 128, 128), "GRÅ 128"),
        ((255, 0, 0), "RØD"),
        ((255, 128, 0), "ORANGE"),
        ((255, 0, 255), "MAGENTA"),
    ]
    for i, (color, label) in enumerate(core):
        bx0 = x0 + i * (col_w + gap)
        bx1 = x1 if i == 4 else bx0 + col_w
        patch((bx0, colors_y0, bx1, colors_y1), color, label)

    # Primaries and secondaries.
    sec_y0 = px(56)
    sec_y1 = px(77)
    gap2 = px(2)
    col_w2 = (content_w - gap2 * 5) // 6
    secondary = [
        ((0, 255, 255), "CYAN"),
        ((0, 0, 255), "BLÅ"),
        ((255, 255, 0), "GUL"),
        ((0, 190, 0), "GRØN"),
        ((128, 0, 180), "LILLA"),
        ((255, 255, 255), "HVID"),
    ]
    for i, (color, label) in enumerate(secondary):
        bx0 = x0 + i * (col_w2 + gap2)
        bx1 = x1 if i == 5 else bx0 + col_w2
        patch((bx0, sec_y0, bx1, sec_y1), color, label)

    # Neutral ramp: should remain neutral under validated GCR.
    draw.text((x0, px(80)), "NEUTRAL GRÅSKALA · RGB 0–255", fill=(0, 0, 0), font=body_font)
    gray_y0 = px(85)
    gray_y1 = px(98)
    gray_values = [0, 26, 51, 77, 102, 128, 153, 179, 204, 230, 255]
    for i, value in enumerate(gray_values):
        bx0 = x0 + round(content_w * i / len(gray_values))
        bx1 = x0 + round(content_w * (i + 1) / len(gray_values))
        draw.rectangle((bx0, gray_y0, bx1, gray_y1), fill=(value, value, value), outline=(0, 0, 0), width=thin)

    # Diagnostic hue ladders.
    draw.text((x0, px(101)), "RØD / ORANGE / MAGENTA DIAGNOSTIK", fill=(0, 0, 0), font=body_font)

    rows = [
        ("RØD", [
            (255, 0, 0),
            (255, 16, 0),
            (255, 32, 0),
            (255, 48, 0),
            (255, 64, 0),
            (255, 80, 0),
            (255, 96, 0),
            (255, 112, 0),
            (255, 128, 0),
            (255, 144, 0),
        ]),
        ("MAGENTA", [
            (255, 0, 255),
            (255, 0, 230),
            (255, 0, 204),
            (255, 0, 179),
            (255, 0, 153),
            (255, 0, 128),
            (255, 0, 102),
            (255, 0, 77),
            (255, 0, 51),
            (255, 0, 26),
        ]),
        ("ORANGE", [
            (255, 64, 0),
            (255, 80, 0),
            (255, 96, 0),
            (255, 112, 0),
            (255, 128, 0),
            (255, 144, 0),
            (255, 160, 0),
            (255, 176, 0),
            (255, 192, 0),
            (255, 208, 0),
        ]),
    ]

    first_y = px(107)
    row_h = px(10)
    row_gap = px(2)
    label_w = px(14)
    ramp_x0 = x0 + label_w
    ramp_w = x1 - ramp_x0

    for row_index, (label, values) in enumerate(rows):
        by0 = first_y + row_index * (row_h + row_gap)
        by1 = by0 + row_h
        centered((x0, by0, ramp_x0 - px(1), by1), label, font=body_font)
        for i, color in enumerate(values):
            bx0 = ramp_x0 + round(ramp_w * i / len(values))
            bx1 = ramp_x0 + round(ramp_w * (i + 1) / len(values))
            draw.rectangle((bx0, by0, bx1, by1), fill=color, outline=(0, 0, 0), width=thin)

    # Bottom reference line.
    bottom_y = px(148)
    draw.line((x0, bottom_y, x1, bottom_y), fill=(0, 0, 0), width=medium)
    draw.line((x0, bottom_y - px(1.4), x0, bottom_y + px(1.4)), fill=(0, 0, 0), width=medium)
    draw.line((x1, bottom_y - px(1.4), x1, bottom_y + px(1.4)), fill=(0, 0, 0), width=medium)

    # Global, reproducerbar 3D-LUT. Dette er ikke manuel labelkorrektion.
    image = apply_red_sector_lut(image)
    image.save(path, "PNG", dpi=(SOURCE_DPI, SOURCE_DPI))
    return width, height


def run_filter(command: list[str], output_path: Path, ppd: Path) -> str:
    env = os.environ.copy()
    env["PPD"] = str(ppd)
    with output_path.open("wb") as output_file:
        process = subprocess.run(
            command,
            stdout=output_file,
            stderr=subprocess.PIPE,
            env=env,
            check=False,
        )

    stderr = process.stderr.decode(errors="replace")
    if process.returncode != 0:
        output_path.unlink(missing_ok=True)
        raise RuntimeError(f"Filterfejl {process.returncode}\n{stderr[-5000:]}")
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("Tomt filter-output")
    return stderr


def build_prn(ppd: Path, output_path: Path, resolution_label: str, resolution_choice: str) -> dict:
    if not ppd.is_file():
        raise FileNotFoundError(f"PPD findes ikke:\n{ppd}")
    for filter_path in (IMAGE_TO_RASTER, RASTER_TO_GUTENPRINT):
        if not filter_path.is_file():
            raise FileNotFoundError(f"Mangler filter:\n{filter_path}")

    work_dir = Path(tempfile.mkdtemp(prefix="et8550-resolution-"))
    try:
        png_path = work_dir / "test.png"
        raster_path = work_dir / "test.raster"
        width, height = make_test_png(png_path, resolution_label)

        # 1440x1440 kræver HighPhoto; Photo tvang tidligere driveren tilbage til 1440x720.
        options = " ".join(
            [
                f"PageSize={page_size()}",
                "ColorModel=RGB",
                "MediaType=GlossyPhoto",
                "InputSlot=Rear",
                "StpQuality=HighPhoto",
                f"Resolution={resolution_choice}",
                "StpFullBleed=True",
                "StpPrintingDirection=Bidirectional",
                "StpiShrinkOutput=crop",
                "StpColorCorrection=Accurate",
                "StpDitherAlgorithm=EvenTone",
                "StpGCRLower=0",
                "StpGCRUpper=0",
                "StpBlackTrans=1000",
            ]
        )

        log_1 = run_filter(
            [
                str(IMAGE_TO_RASTER),
                "1",
                os.environ.get("USER", "user"),
                "test.png",
                "1",
                options,
                str(png_path),
            ],
            raster_path,
            ppd,
        )
        log_2 = run_filter(
            [
                str(RASTER_TO_GUTENPRINT),
                "1",
                os.environ.get("USER", "user"),
                f"color-test-v4-red-sector-lut-{resolution_choice}",
                "1",
                options,
                str(raster_path),
            ],
            output_path,
            ppd,
        )

        complete_log = log_1 + "\n" + log_2

        required_log_markers = [
            "StpGCRLower = 0",
            "StpGCRUpper = 0",
            "StpBlackTrans = 1000",
        ]
        missing = [marker for marker in required_log_markers if marker not in complete_log]
        if missing:
            raise RuntimeError(
                "GCR-indstillingerne blev ikke alle registreret i filterloggen:\n"
                + "\n".join(missing)
            )

        return {
            "bytes": output_path.stat().st_size,
            "width": width,
            "height": height,
            "log": complete_log,
            "options": options,
            "resolution_label": resolution_label,
            "resolution_choice": resolution_choice,
        }
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def send_job(ip: str, port: int, data: bytes) -> None:
    with socket.create_connection((ip, port), timeout=15) as connection:
        connection.settimeout(None)
        connection.sendall(data)
        try:
            connection.shutdown(socket.SHUT_WR)
        except OSError:
            pass


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title(APP_NAME)
        root.geometry("780x600")

        self.ip = tk.StringVar(value=DEFAULT_IP)
        self.port = tk.StringVar(value=str(DEFAULT_PORT))
        self.ppd = tk.StringVar(value=str(DEFAULT_PPD))
        self.resolution_label = tk.StringVar(value=DEFAULT_RESOLUTION_LABEL)
        self.status = tk.StringVar(value="Klar. 1440 × 1440 HighPhoto er låst.")

        self.prn: Path | None = None
        self.png: Path | None = None
        self.log = ""
        self.last_result: dict | None = None
        self.busy = False
        self.build_ui()

    def build_ui(self) -> None:
        shell = ttk.Frame(self.root)
        shell.pack(fill="both", expand=True)

        canvas = tk.Canvas(shell, highlightthickness=0)
        scrollbar = ttk.Scrollbar(shell, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        main = ttk.Frame(canvas, padding=16)
        window_id = canvas.create_window((0, 0), window=main, anchor="nw")

        main.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window_id, width=event.width))

        def on_mousewheel(event):
            if getattr(event, "num", None) == 4:
                canvas.yview_scroll(-1, "units")
            elif getattr(event, "num", None) == 5:
                canvas.yview_scroll(1, "units")
            elif getattr(event, "delta", 0):
                canvas.yview_scroll(int(-event.delta / 120), "units")

        canvas.bind_all("<MouseWheel>", on_mousewheel)
        canvas.bind_all("<Button-4>", on_mousewheel)
        canvas.bind_all("<Button-5>", on_mousewheel)

        ttk.Label(main, text="ET-8550 Farvetest v4 · Red Sector LUT", font=("Arial", 18, "bold")).pack(anchor="w")
        ttk.Label(
            main,
            text=(
                "Samme validerede printerkæde som før. En lokal 3D-LUT drejer kun den mættede røde sektor, "
                "så ren RGB-rød bliver RGB(255,0,36). Orange og magenta er låst uændret ved sektorens kanter."
            ),
            wraplength=720,
        ).pack(anchor="w", pady=(4, 14))

        printer_box = ttk.LabelFrame(main, text="Printer", padding=10)
        printer_box.pack(fill="x")

        row = ttk.Frame(printer_box)
        row.pack(fill="x", pady=3)
        ttk.Label(row, text="IP:", width=10).pack(side="left")
        ttk.Entry(row, textvariable=self.ip, width=18).pack(side="left")
        ttk.Label(row, text="Port:", padding=(14, 0, 4, 0)).pack(side="left")
        ttk.Entry(row, textvariable=self.port, width=8).pack(side="left")

        row = ttk.Frame(printer_box)
        row.pack(fill="x", pady=3)
        ttk.Label(row, text="PPD:", width=10).pack(side="left")
        ttk.Entry(row, textvariable=self.ppd).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Vælg", command=self.choose_ppd).pack(side="left", padx=(6, 0))

        mode_box = ttk.LabelFrame(main, text="Printermode", padding=10)
        mode_box.pack(fill="x", pady=(12, 0))
        ttk.Label(mode_box, text="Opløsning:").pack(anchor="w")
        self.resolution_combo = ttk.Combobox(
            mode_box,
            textvariable=self.resolution_label,
            values=[label for label, _choice in RESOLUTIONS],
            state="readonly",
            width=42,
        )
        self.resolution_combo.pack(anchor="w", pady=(4, 6))
        ttk.Label(
            mode_box,
            text="Test én mode ad gangen. Alt andet er låst, så resultatet kan sammenlignes direkte.",
            wraplength=700,
        ).pack(anchor="w")

        actions = ttk.LabelFrame(main, text="Handlinger", padding=10)
        actions.pack(fill="x", pady=(12, 0))
        self.build_button = ttk.Button(actions, text="1. BYG FARVETEST v4 · RED LUT", command=self.build)
        self.build_button.pack(fill="x", pady=3)
        self.send_button = ttk.Button(
            actions,
            text="2. SEND KOMPLET PRN TIL PRINTER",
            command=self.send,
            state="disabled",
        )
        self.send_button.pack(fill="x", pady=3)
        self.save_png_button = ttk.Button(actions, text="GEM TESTARK SOM PNG", command=self.save_png, state="disabled")
        self.save_png_button.pack(fill="x", pady=3)
        self.save_prn_button = ttk.Button(actions, text="GEM PRN", command=self.save_prn, state="disabled")
        self.save_prn_button.pack(fill="x", pady=3)
        self.show_log_button = ttk.Button(actions, text="VIS FILTERLOG", command=self.show_log, state="disabled")
        self.show_log_button.pack(fill="x", pady=3)
        self.save_log_button = ttk.Button(actions, text="GEM FILTERLOG SOM TXT", command=self.save_log, state="disabled")
        self.save_log_button.pack(fill="x", pady=3)

        ttk.Label(
            main,
            text=(
                "Efter print: vurder kun om RØD nu er rigtig, og om ORANGE og MAGENTA stadig ser korrekte ud."
            ),
            wraplength=720,
        ).pack(anchor="w", pady=(14, 8))
        ttk.Label(main, textvariable=self.status, relief="sunken", padding=9, anchor="w", wraplength=720).pack(fill="x")

    def choose_ppd(self) -> None:
        path = filedialog.askopenfilename(
            title="Vælg ET-8550 PPD",
            initialdir=str(Path.home()),
            filetypes=[("PPD", "*.ppd"), ("Alle", "*.*")],
        )
        if path:
            self.ppd.set(path)

    def set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.build_button.configure(state="disabled" if busy else "normal")
        self.resolution_combo.configure(state="disabled" if busy else "readonly")
        self.send_button.configure(state="normal" if (not busy and self.prn) else "disabled")

    def build(self) -> None:
        if self.busy:
            return

        ppd = Path(self.ppd.get()).expanduser()
        resolution_label = self.resolution_label.get()
        resolution_choice = RESOLUTION_BY_LABEL.get(resolution_label)
        if not resolution_choice:
            messagebox.showerror("Fejl", "Vælg en gyldig opløsning.")
            return

        self.set_busy(True)
        self.status.set(f"Bygger komplet PRN — {resolution_label}...")

        def worker() -> None:
            prn_path = Path(tempfile.mkstemp(prefix="et8550-resolution-", suffix=".prn")[1])
            png_path = Path(tempfile.mkstemp(prefix="et8550-resolution-", suffix=".png")[1])
            try:
                result = build_prn(ppd, prn_path, resolution_label, resolution_choice)
                make_test_png(png_path, resolution_label)
            except Exception as error:
                prn_path.unlink(missing_ok=True)
                png_path.unlink(missing_ok=True)
                self.root.after(0, lambda error=error: self.fail(error))
                return
            self.root.after(0, lambda: self.done(prn_path, png_path, result))

        threading.Thread(target=worker, daemon=True).start()

    def fail(self, error: Exception) -> None:
        self.set_busy(False)
        self.status.set(f"Fejl: {error}")
        messagebox.showerror("Fejl", str(error))

    def done(self, prn_path: Path, png_path: Path, result: dict) -> None:
        if self.prn:
            self.prn.unlink(missing_ok=True)
        if self.png:
            self.png.unlink(missing_ok=True)

        self.prn = prn_path
        self.png = png_path
        self.log = result["log"]
        self.last_result = result
        self.set_busy(False)

        for button in (
            self.save_png_button,
            self.save_prn_button,
            self.show_log_button,
            self.save_log_button,
        ):
            button.configure(state="normal")

        self.status.set(
            f"PRN klar: {result['resolution_label']} | {result['bytes']:,} bytes | "
            f"{result['width']}×{result['height']} px | Borderless TIL"
        )

    def send(self) -> None:
        if not self.prn or self.busy:
            return
        try:
            ip = self.ip.get().strip()
            port = int(self.port.get())
            data = self.prn.read_bytes()
        except Exception as error:
            messagebox.showerror("Sendefejl", str(error))
            return

        self.set_busy(True)
        self.status.set(f"Sender komplet job på {len(data):,} bytes...")

        def worker() -> None:
            try:
                send_job(ip, port, data)
            except Exception as error:
                self.root.after(0, lambda error=error: self.fail(error))
                return
            self.root.after(0, self.sent)

        threading.Thread(target=worker, daemon=True).start()

    def sent(self) -> None:
        self.set_busy(False)
        label = self.last_result["resolution_label"] if self.last_result else self.resolution_label.get()
        self.status.set(f"{label} er sendt. Kontroller RØD samt at ORANGE og MAGENTA er bevaret.")

    def safe_name(self) -> str:
        if not self.last_result:
            return "unknown"
        return self.last_result["resolution_choice"].replace("dpi", "")

    def save_png(self) -> None:
        if not self.png:
            return
        path = filedialog.asksaveasfilename(
            initialdir="/mnt/c/Users/dontm/Downloads",
            initialfile=f"ET8550-color-test-v4-red-sector-lut-{self.safe_name()}.png",
            defaultextension=".png",
            filetypes=[("PNG", "*.png")],
        )
        if path:
            shutil.copyfile(self.png, path)

    def save_prn(self) -> None:
        if not self.prn:
            return
        path = filedialog.asksaveasfilename(
            initialdir="/mnt/c/Users/dontm/Downloads",
            initialfile=f"ET8550-color-test-v4-red-sector-lut-{self.safe_name()}.prn",
            defaultextension=".prn",
            filetypes=[("PRN", "*.prn")],
        )
        if path:
            shutil.copyfile(self.prn, path)

    def save_log(self) -> None:
        if not self.log:
            messagebox.showerror("Ingen log", "Byg testen først.")
            return
        path = filedialog.asksaveasfilename(
            title="Gem Gutenprint filterlog",
            initialdir="/mnt/c/Users/dontm/Downloads",
            initialfile=f"ET8550-color-test-v4-red-sector-lut-{self.safe_name()}-filterlog.txt",
            defaultextension=".txt",
            filetypes=[("Tekstfil", "*.txt"), ("Alle filer", "*.*")],
        )
        if path:
            Path(path).write_text(self.log, encoding="utf-8")
            self.status.set(f"Filterlog gemt: {path}")

    def show_log(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("Gutenprint filterlog")
        window.geometry("900x650")
        text = tk.Text(window, wrap="none")
        text.pack(fill="both", expand=True)
        text.insert("1.0", self.log)
        text.configure(state="disabled")


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
