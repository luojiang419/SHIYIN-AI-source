from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class RuntimeCapabilities:
    os: str
    arch: str
    accelerator: str
    gpu_name: str = ""
    gpu_memory_bytes: int = 0
    compute_capability: float = 0.0
    driver_version: str = ""

    def public_dict(self) -> dict[str, object]:
        return {
            "os": self.os,
            "arch": self.arch,
            "accelerator": self.accelerator,
            "gpu_name": self.gpu_name,
            "gpu_memory_bytes": self.gpu_memory_bytes,
            "compute_capability": self.compute_capability,
            "driver_version": self.driver_version,
        }


def _normalized_arch(value: str) -> str:
    value = value.strip().lower()
    if value in {"amd64", "x64", "x86_64"}:
        return "x86_64"
    if value in {"arm64", "aarch64"}:
        return "arm64"
    return value


def probe_runtime_capabilities() -> RuntimeCapabilities:
    system = platform.system().strip().lower()
    capabilities = RuntimeCapabilities(system, _normalized_arch(platform.machine()), "cpu")
    if system != "windows":
        return capabilities
    executable = shutil.which("nvidia-smi")
    if not executable:
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        candidate = os.path.join(system_root, "System32", "nvidia-smi.exe")
        executable = candidate if os.path.isfile(candidate) else None
    if not executable:
        return capabilities
    try:
        result = subprocess.run(
            [
                executable,
                "--query-gpu=name,memory.total,compute_cap,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        row = next((line.strip() for line in result.stdout.splitlines() if line.strip()), "")
        fields = [part.strip() for part in row.split(",")]
        if result.returncode != 0 or len(fields) < 4:
            return capabilities
        memory_mib = int(float(fields[1]))
        compute = float(fields[2]) if re.fullmatch(r"\d+(?:\.\d+)?", fields[2]) else 0.0
        return RuntimeCapabilities(
            system,
            capabilities.arch,
            "cuda",
            gpu_name=fields[0],
            gpu_memory_bytes=memory_mib * 1024 * 1024,
            compute_capability=compute,
            driver_version=fields[3],
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return capabilities


def compatible_variants(
    variants: Sequence[Mapping[str, object]], capabilities: RuntimeCapabilities
) -> list[dict[str, object]]:
    matches: list[dict[str, object]] = []
    for raw in variants:
        variant = dict(raw)
        constraints = variant.get("constraints")
        constraints = dict(constraints) if isinstance(constraints, Mapping) else {}
        expected_os = str(constraints.get("os") or "").lower()
        expected_arch = _normalized_arch(str(constraints.get("arch") or ""))
        accelerator = str(constraints.get("accelerator") or "cpu").lower()
        if expected_os and expected_os != capabilities.os:
            continue
        if expected_arch and expected_arch != capabilities.arch:
            continue
        if accelerator != capabilities.accelerator and accelerator != "cpu":
            continue
        if accelerator == "cuda":
            if capabilities.compute_capability < float(constraints.get("min_compute_capability") or 0):
                continue
            maximum_compute = float(constraints.get("max_compute_capability") or 0)
            if maximum_compute and capabilities.compute_capability > maximum_compute:
                continue
            if capabilities.gpu_memory_bytes < int(constraints.get("min_gpu_memory_bytes") or 0):
                continue
            minimum_driver = str(constraints.get("min_driver_version") or "").strip()
            if minimum_driver and _version_tuple(capabilities.driver_version) < _version_tuple(minimum_driver):
                continue
        matches.append(variant)
    return sorted(matches, key=lambda item: int(item.get("priority") or 0), reverse=True)


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = [int(part) for part in re.findall(r"\d+", value)]
    return tuple(parts or [0])


def select_variant(
    variants: Sequence[Mapping[str, object]], capabilities: RuntimeCapabilities
) -> dict[str, object]:
    matches = compatible_variants(variants, capabilities)
    if not matches:
        raise ValueError(
            f"没有适用于 {capabilities.os}/{capabilities.arch}/{capabilities.accelerator} 的运行时"
        )
    return matches[0]
