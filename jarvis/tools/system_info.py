"""System diagnostics tools for Jarvis (CPU temp, RAM, Battery, Disk)."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from typing import Literal


def _get_battery_status() -> str:
    """Retrieve macOS battery percentage and charging state via pmset."""
    try:
        res = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, check=False)
        stdout = res.stdout.strip()
        lines = stdout.splitlines()
        if len(lines) > 1:
            return lines[1].strip()
        return stdout or "Battery status unavailable."
    except Exception as exc:
        return f"Battery error: {exc}"


def _get_cpu_temp() -> str:
    """Retrieve CPU/SOC temperature on Apple Silicon macOS using swift/clang or sysctl fallback."""
    try:
        # Check if our compiled helper exists
        helper_path = "/Users/mac/.gemini/antigravity/scratch/get_temp"
        if os.path.exists(helper_path) and os.access(helper_path, os.X_OK):
            res = subprocess.run([helper_path], capture_output=True, text=True, check=False)
            output = res.stdout.strip()
            if "Summary" in output:
                summary_part = output.split("--- Summary ---")[-1].strip()
                return summary_part
            if output:
                return output.splitlines()[-1]

        # Fallback to thermal state check
        res = subprocess.run(["pmset", "-g", "therm"], capture_output=True, text=True, check=False)
        return res.stdout.strip() or "Thermal status normal."
    except Exception as exc:
        return f"CPU temperature error: {exc}"


def _get_ram_info() -> str:
    """Retrieve system memory usage on macOS."""
    try:
        res = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, check=False)
        total_bytes = int(res.stdout.strip())
        total_gb = total_bytes / (1024 ** 3)
        
        vm_res = subprocess.run(["vm_stat"], capture_output=True, text=True, check=False)
        lines = vm_res.stdout.splitlines()
        page_size = 4096
        free_pages = 0
        active_pages = 0
        inactive_pages = 0
        wired_pages = 0
        for line in lines:
            if "Pages free:" in line:
                free_pages = int(line.split(":")[-1].strip().rstrip("."))
            elif "Pages active:" in line:
                active_pages = int(line.split(":")[-1].strip().rstrip("."))
            elif "Pages inactive:" in line:
                inactive_pages = int(line.split(":")[-1].strip().rstrip("."))
            elif "Pages wired down:" in line:
                wired_pages = int(line.split(":")[-1].strip().rstrip("."))
        
        used_gb = ((active_pages + wired_pages) * page_size) / (1024 ** 3)
        return f"RAM: {used_gb:.1f} GB used of {total_gb:.1f} GB total ({((used_gb / total_gb) * 100):.0f}% used)."
    except Exception as exc:
        return f"RAM info error: {exc}"


def _get_disk_info() -> str:
    """Retrieve main disk space usage."""
    try:
        total, used, free = shutil.disk_usage("/")
        total_gb = total / (1024 ** 3)
        used_gb = used / (1024 ** 3)
        free_gb = free / (1024 ** 3)
        return f"Disk Space: {free_gb:.1f} GB free of {total_gb:.1f} GB total ({used_gb:.1f} GB used)."
    except Exception as exc:
        return f"Disk info error: {exc}"


def get_system_info(category: Literal["all", "cpu", "ram", "battery", "disk"] = "all") -> str:
    """Return diagnostic details about the computer's CPU temperature, RAM, battery, and disk."""
    if platform.system().lower() != "darwin":
        return "System diagnostics are currently implemented for macOS."

    category = category.lower().strip() # type: ignore
    results = []

    if category in ("all", "cpu"):
        results.append(f"CPU Thermal Status: {_get_cpu_temp()}")
    if category in ("all", "ram"):
        results.append(_get_ram_info())
    if category in ("all", "battery"):
        results.append(f"Battery: {_get_battery_status()}")
    if category in ("all", "disk"):
        results.append(_get_disk_info())

    return "\n".join(results)
