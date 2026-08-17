"""System diagnostics tools."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from typing import Literal


def _get_battery_status() -> str:
    try:
        res = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, check=False)
        if res.returncode != 0:
            return f"TOOL_ERROR: Battery command failed: {(res.stderr or '').strip() or f'exit code {res.returncode}'}."
        lines = res.stdout.strip().splitlines()
        if len(lines) > 1:
            return lines[1].strip()
        return res.stdout.strip() or "TOOL_ERROR: Battery status was unavailable."
    except (OSError, subprocess.SubprocessError) as exc:
        return f"TOOL_ERROR: Battery status failed: {exc}."


def _get_cpu_temp() -> str:
    try:
        helper_path = "/Users/mac/.gemini/antigravity/scratch/get_temp"
        if os.path.exists(helper_path) and os.access(helper_path, os.X_OK):
            res = subprocess.run([helper_path], capture_output=True, text=True, check=False)
            if res.returncode != 0:
                return f"TOOL_ERROR: CPU temperature helper failed: {(res.stderr or '').strip() or f'exit code {res.returncode}'}."
            output = res.stdout.strip()
            if "Summary" in output:
                return output.split("--- Summary ---")[-1].strip()
            if output:
                return output.splitlines()[-1]

        res = subprocess.run(["pmset", "-g", "therm"], capture_output=True, text=True, check=False)
        if res.returncode != 0:
            return f"TOOL_ERROR: Thermal status command failed: {(res.stderr or '').strip() or f'exit code {res.returncode}'}."
        return res.stdout.strip() or "TOOL_ERROR: Thermal status was unavailable."
    except (OSError, subprocess.SubprocessError) as exc:
        return f"TOOL_ERROR: CPU temperature failed: {exc}."


def _get_ram_info() -> str:
    try:
        res = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, check=False)
        if res.returncode != 0:
            return f"TOOL_ERROR: Total-memory command failed: {(res.stderr or '').strip() or f'exit code {res.returncode}'}."
        total_bytes = int(res.stdout.strip())
        if total_bytes <= 0:
            return "TOOL_ERROR: Total memory was not reported."
        total_gb = total_bytes / (1024 ** 3)

        vm_res = subprocess.run(["vm_stat"], capture_output=True, text=True, check=False)
        if vm_res.returncode != 0:
            return f"TOOL_ERROR: VM statistics command failed: {(vm_res.stderr or '').strip() or f'exit code {vm_res.returncode}'}."
        page_size = 4096
        active_pages = 0
        wired_pages = 0
        for line in vm_res.stdout.splitlines():
            if "Pages active:" in line:
                active_pages = int(line.split(":")[-1].strip().rstrip("."))
            elif "Pages wired down:" in line:
                wired_pages = int(line.split(":")[-1].strip().rstrip("."))
        used_gb = ((active_pages + wired_pages) * page_size) / (1024 ** 3)
        return f"RAM: {used_gb:.1f} GB used of {total_gb:.1f} GB total ({((used_gb / total_gb) * 100):.0f}% used)."
    except (OSError, subprocess.SubprocessError, ValueError, ZeroDivisionError) as exc:
        return f"TOOL_ERROR: RAM information failed: {exc}."


def _get_disk_info() -> str:
    try:
        total, used, free = shutil.disk_usage("/")
        if total <= 0:
            return "TOOL_ERROR: Disk capacity was not reported."
        total_gb = total / (1024 ** 3)
        used_gb = used / (1024 ** 3)
        free_gb = free / (1024 ** 3)
        return f"Disk Space: {free_gb:.1f} GB free of {total_gb:.1f} GB total ({used_gb:.1f} GB used)."
    except OSError as exc:
        return f"TOOL_ERROR: Disk information failed: {exc}."


def get_system_info(category: Literal["all", "cpu", "ram", "battery", "disk"] = "all") -> str:
    """Return verified diagnostic details or an explicit error."""
    if platform.system().lower() != "darwin":
        return "TOOL_ERROR: System diagnostics are currently implemented for macOS only."

    category = category.lower().strip()  # type: ignore
    if category not in {"all", "cpu", "ram", "battery", "disk"}:
        return f"TOOL_ERROR: Unsupported diagnostic category '{category}'."

    results: list[str] = []
    if category in ("all", "cpu"):
        results.append(f"CPU Thermal Status: {_get_cpu_temp()}")
    if category in ("all", "ram"):
        results.append(_get_ram_info())
    if category in ("all", "battery"):
        results.append(f"Battery: {_get_battery_status()}")
    if category in ("all", "disk"):
        results.append(_get_disk_info())

    output = "\n".join(results).strip()
    if not output:
        return "TOOL_ERROR: No diagnostic data was produced."
    if "TOOL_ERROR:" in output:
        return f"TOOL_ERROR: One or more diagnostic checks failed.\n{output}"
    return f"TOOL_OK: {output}"
