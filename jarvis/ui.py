"""Startup splash animation for Jarvis."""

from __future__ import annotations

import math
from pathlib import Path
import tkinter as tk

from PIL import Image, ImageTk


class JarvisSplash:
    """Blue radar-style startup animation inspired by the JARVIS UI."""

    def __init__(self, duration_ms: int = 3500) -> None:
        self.duration_ms = duration_ms
        self.root = tk.Tk()
        self.root.title("JARVIS")
        self.root.configure(bg="#030b12")
        self.root.geometry("1024x1024")
        self.root.resizable(False, False)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-fullscreen", True)
        self.canvas = tk.Canvas(self.root, width=1024, height=1024, bg="#030b12", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.frame = 0
        self.center_x = 512
        self.center_y = 485
        self.rings = [110, 170, 245]
        self.ring_items: list[int] = []
        self.scan_marks: list[int] = []
        self.base_image = None
        self.logo_frame = None
        self._build_background()

    def _load_image(self) -> None:
        """Load the supplied JARVIS image if available."""
        candidates = [
            Path("/Users/mac/Downloads/jarvis.png"),
            Path.cwd() / "jarvis.png",
            Path(__file__).resolve().parent / "assets" / "jarvis.png",
        ]
        for candidate in candidates:
            if candidate.exists():
                image = Image.open(candidate).convert("RGBA")
                image = image.resize((680, 644), Image.LANCZOS)
                self.base_image = ImageTk.PhotoImage(image, master=self.root)
                self.logo_frame = self.canvas.create_image(
                    self.center_x,
                    self.center_y - 8,
                    image=self.base_image,
                )
                return

    def _build_background(self) -> None:
        self.canvas.create_rectangle(0, 0, 1024, 1024, fill="#020810", outline="")
        self._load_image()
        self.canvas.create_oval(80, 70, 944, 930, outline="#173040", width=1)
        if self.base_image is None:
            self.canvas.create_oval(
                self.center_x - 340,
                self.center_y - 320,
                self.center_x + 340,
                self.center_y + 320,
                outline="#1f90bf",
                width=3,
            )
        self.canvas.create_text(
            512,
            70,
            text="J.A.R.V.I.S.",
            fill="#8df7ff",
            font=("Menlo", 34, "bold"),
        )
        self.canvas.create_text(
            512,
            910,
            text="Initializing voice interface...",
            fill="#2fb7d8",
            font=("Menlo", 16),
        )
        self.canvas.create_text(
            512,
            946,
            text="Tony Stark inspired local assistant",
            fill="#1f6f85",
            font=("Menlo", 12),
        )
        for r in self.rings:
            ring = self.canvas.create_oval(
                self.center_x - r,
                self.center_y - r,
                self.center_x + r,
                self.center_y + r,
                outline="#214c60",
                width=2,
            )
            self.ring_items.append(ring)
        for i in range(60):
            angle = math.radians(i * 7.5)
            inner = 360 if i % 4 else 340
            outer = 382
            x1 = self.center_x + math.cos(angle) * inner
            y1 = self.center_y + math.sin(angle) * inner
            x2 = self.center_x + math.cos(angle) * outer
            y2 = self.center_y + math.sin(angle) * outer
            color = "#58e6ff" if i % 4 == 0 else "#0f3446"
            width = 3 if i % 4 == 0 else 1
            self.canvas.create_line(x1, y1, x2, y2, fill=color, width=width)
        for i in range(20):
            x = 145 + i * 37
            mark = self.canvas.create_line(x, 820, x + 20, 820, fill="#27c6ff", width=2)
            self.scan_marks.append(mark)
        self.sweep = self.canvas.create_arc(
            self.center_x - 310,
            self.center_y - 310,
            self.center_x + 310,
            self.center_y + 310,
            start=0,
            extent=45,
            style="arc",
            outline="#52f2ff",
            width=6,
        )
        self.glow = self.canvas.create_oval(
            self.center_x - 55,
            self.center_y - 55,
            self.center_x + 55,
            self.center_y + 55,
            outline="#76f7ff",
            width=2,
        )
        self.core = self.canvas.create_text(
            self.center_x,
            self.center_y,
            text="JARVIS",
            fill="#e9fbff",
            font=("Menlo", 46, "bold"),
        )
        self.status = self.canvas.create_text(
            self.center_x,
            self.center_y + 185,
            text="BOOT SEQUENCE ACTIVE",
            fill="#4fe8ff",
            font=("Menlo", 16, "bold"),
        )
        if self.base_image is None:
            self.canvas.create_text(
                self.center_x,
                self.center_y - 10,
                text="JARVIS",
                fill="#ecfbff",
                font=("Menlo", 64, "bold"),
            )

    def _animate(self) -> None:
        self.frame += 1
        angle = (self.frame * 6) % 360
        self.canvas.itemconfigure(self.sweep, start=angle)

        pulse = 55 + int(8 * math.sin(self.frame / 4))
        self.canvas.coords(
            self.glow,
            self.center_x - pulse,
            self.center_y - pulse,
            self.center_x + pulse,
            self.center_y + pulse,
        )

        for idx, radius in enumerate(self.rings):
            wobble = int(2 * math.sin((self.frame + idx * 12) / 7))
            r = radius + wobble
            ring = self.ring_items[idx]
            self.canvas.coords(
                ring,
                self.center_x - r,
                self.center_y - r,
                self.center_x + r,
                self.center_y + r,
            )

        for idx, mark in enumerate(self.scan_marks):
            offset = (self.frame * 5 + idx * 20) % 80
            self.canvas.coords(mark, 110 + idx * 42 + offset, 745, 134 + idx * 42 + offset, 745)

        if self.logo_frame is not None:
            wiggle = 2 * math.sin(self.frame / 8)
            self.canvas.coords(self.logo_frame, self.center_x, self.center_y - 8 + wiggle)

        self.root.after(40, self._animate)

    def show(self) -> None:
        """Show the splash animation and close it after the duration."""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.root.attributes("-topmost", True)
        self.root.after(0, self._animate)
        self.root.after(self.duration_ms, self.root.destroy)
        self.root.mainloop()
