#!/usr/bin/env python3
"""
Build sing-box .srs rule-set files from Russia mobile internet whitelist.

Source: https://github.com/hxehex/russia-mobile-internet-whitelist

Outputs (in ./output/):
  russia-mobile-whitelist-domains.json  – sing-box rule-set source (domains)
  russia-mobile-whitelist-cidr.json     – sing-box rule-set source (CIDRs + IPs)
  russia-mobile-whitelist-domains.srs   – compiled binary rule set (domains)
  russia-mobile-whitelist-cidr.srs      – compiled binary rule set (CIDRs + IPs)

Usage:
  python build.py [--no-download]

  --no-download   Do not try to download sing-box; fail if not found in PATH.
"""

import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Source data
# ---------------------------------------------------------------------------

_REPO_RAW = "https://raw.githubusercontent.com/hxehex/russia-mobile-internet-whitelist/main"

SOURCE_URLS = {
    "domains": f"{_REPO_RAW}/whitelist.txt",
    "ips":     f"{_REPO_RAW}/ipwhitelist.txt",
    "cidrs":   f"{_REPO_RAW}/cidrwhitelist.txt",
}

# ---------------------------------------------------------------------------
# sing-box release to download when it is not found in PATH
# ---------------------------------------------------------------------------

SING_BOX_VERSION = "1.9.0"

_SING_BOX_RELEASE_BASE = (
    "https://github.com/SagerNet/sing-box/releases/download"
    f"/v{SING_BOX_VERSION}"
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path("output")
SING_BOX_CACHE = Path(".sing-box-bin")   # local cache dir for downloaded binary


# ===========================================================================
# Helpers
# ===========================================================================

def _fetch_lines(url: str) -> list[str]:
    """Download *url* and return its non-blank, non-comment lines."""
    print(f"    GET {url}")
    with urllib.request.urlopen(url, timeout=60) as resp:
        text = resp.read().decode("utf-8")
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.startswith("#")
    ]


def _write_json_ruleset(path: Path, rules: list[dict]) -> None:
    """Write a sing-box PlainRuleSet JSON source file."""
    ruleset = {"version": 1, "rules": rules}
    path.write_text(json.dumps(ruleset, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def _dedup(items: list[str]) -> list[str]:
    """Return *items* with duplicates removed, preserving first-seen order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


# ===========================================================================
# sing-box binary location / download
# ===========================================================================

def _platform_info() -> tuple[str, str]:
    """Return (os_name, arch) suitable for the sing-box release filename."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    os_map = {"darwin": "darwin", "windows": "windows"}
    os_name = os_map.get(system, "linux")

    arch_map = {
        "x86_64":  "amd64",
        "amd64":   "amd64",
        "aarch64": "arm64",
        "arm64":   "arm64",
        "armv7l":  "armv7",
        "i386":    "386",
        "i686":    "386",
    }
    arch = arch_map.get(machine, machine)

    return os_name, arch


def _download_sing_box() -> Path:
    """Download the sing-box binary for the current platform.

    The binary is cached in SING_BOX_CACHE so repeated runs do not
    re-download it.
    """
    os_name, arch = _platform_info()
    ext = "zip" if os_name == "windows" else "tar.gz"
    archive_stem = f"sing-box-{SING_BOX_VERSION}-{os_name}-{arch}"
    archive_name = f"{archive_stem}.{ext}"
    url = f"{_SING_BOX_RELEASE_BASE}/{archive_name}"
    bin_name = "sing-box.exe" if os_name == "windows" else "sing-box"

    SING_BOX_CACHE.mkdir(exist_ok=True)
    binary_path = SING_BOX_CACHE / bin_name

    if binary_path.exists():
        print(f"  Using cached sing-box: {binary_path}")
        return binary_path

    archive_path = SING_BOX_CACHE / archive_name
    print(f"  Downloading sing-box {SING_BOX_VERSION} ({os_name}/{arch})…")
    print(f"    {url}")

    try:
        urllib.request.urlretrieve(url, archive_path)
    except Exception as exc:
        sys.exit(
            f"  ERROR: could not download sing-box: {exc}\n"
            f"  Please install sing-box manually: https://github.com/SagerNet/sing-box/releases"
        )

    if ext == "tar.gz":
        with tarfile.open(archive_path) as tar:
            for member in tar.getmembers():
                if os.path.basename(member.name) == bin_name:
                    # Extract directly into SING_BOX_CACHE
                    member.name = bin_name
                    tar.extract(member, path=SING_BOX_CACHE)
                    break
            else:
                sys.exit(f"  ERROR: '{bin_name}' not found in {archive_name}")
    else:
        with zipfile.ZipFile(archive_path) as zf:
            for name in zf.namelist():
                if os.path.basename(name) == bin_name:
                    data = zf.read(name)
                    binary_path.write_bytes(data)
                    break
            else:
                sys.exit(f"  ERROR: '{bin_name}' not found in {archive_name}")

    archive_path.unlink(missing_ok=True)

    # Make executable on POSIX
    binary_path.chmod(
        binary_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH
    )
    print(f"  Extracted to {binary_path}")
    return binary_path


def locate_sing_box(allow_download: bool = True) -> str:
    """Return the path to a usable sing-box binary.

    Search order:
      1. SING_BOX environment variable
      2. PATH
      3. Previously-downloaded cache
      4. Download (unless *allow_download* is False)
    """
    # 1. Env var override
    env_path = os.environ.get("SING_BOX")
    if env_path and Path(env_path).is_file():
        print(f"  Using SING_BOX env var: {env_path}")
        return env_path

    # 2. PATH
    found = shutil.which("sing-box")
    if found:
        print(f"  Found in PATH: {found}")
        return found

    # 3. Cache
    bin_name = "sing-box.exe" if platform.system().lower() == "windows" else "sing-box"
    cached = SING_BOX_CACHE / bin_name
    if cached.exists():
        print(f"  Using cached binary: {cached}")
        return str(cached)

    # 4. Download
    if not allow_download:
        sys.exit(
            "  ERROR: sing-box not found in PATH and --no-download was specified.\n"
            "  Install sing-box from: https://github.com/SagerNet/sing-box/releases"
        )

    return str(_download_sing_box())


# ===========================================================================
# Compilation
# ===========================================================================

def _compile_srs(sing_box: str, source_json: Path, output_srs: Path) -> None:
    """Run 'sing-box rule-set compile' to produce a binary .srs file."""
    cmd = [sing_box, "rule-set", "compile", str(source_json),
           "--output", str(output_srs)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        sys.exit(
            f"  ERROR compiling {source_json.name}:\n"
            f"  {stderr or '(no stderr output)'}"
        )


# ===========================================================================
# Main
# ===========================================================================

def main() -> None:
    allow_download = "--no-download" not in sys.argv

    print("=" * 60)
    print("Russia Mobile Internet Whitelist — sing-box .srs Builder")
    print("=" * 60)
    print()

    OUTPUT_DIR.mkdir(exist_ok=True)

    # ------------------------------------------------------------------
    # 1. Fetch source data
    # ------------------------------------------------------------------
    print("Fetching source data…")
    domains = _fetch_lines(SOURCE_URLS["domains"])
    ips     = _fetch_lines(SOURCE_URLS["ips"])
    cidrs   = _fetch_lines(SOURCE_URLS["cidrs"])

    # Combine individual IPs and CIDR ranges; sing-box accepts bare IPs in
    # the ip_cidr field (treats them as host routes).
    all_cidrs = _dedup(cidrs + ips)

    print(
        f"  {len(domains)} domains, "
        f"{len(ips)} individual IPs, "
        f"{len(cidrs)} CIDR ranges  "
        f"({len(all_cidrs)} unique CIDRs total)"
    )
    print()

    # ------------------------------------------------------------------
    # 2. Generate JSON rule-set source files
    # ------------------------------------------------------------------
    print("Generating JSON source files…")

    domain_json = OUTPUT_DIR / "russia-mobile-whitelist-domains.json"
    cidr_json   = OUTPUT_DIR / "russia-mobile-whitelist-cidr.json"

    # domain_suffix matches both the listed hostname and all its sub-domains,
    # which is the correct semantics for a whitelist.
    _write_json_ruleset(domain_json, [{"domain_suffix": domains}])
    _write_json_ruleset(cidr_json,   [{"ip_cidr": all_cidrs}])

    print(f"  {domain_json}  ({domain_json.stat().st_size:,} bytes)")
    print(f"  {cidr_json}  ({cidr_json.stat().st_size:,} bytes)")
    print()

    # ------------------------------------------------------------------
    # 3. Locate sing-box
    # ------------------------------------------------------------------
    print("Locating sing-box…")
    sing_box = locate_sing_box(allow_download=allow_download)
    print()

    # ------------------------------------------------------------------
    # 4. Compile to .srs
    # ------------------------------------------------------------------
    print("Compiling rule sets…")

    domain_srs = OUTPUT_DIR / "russia-mobile-whitelist-domains.srs"
    cidr_srs   = OUTPUT_DIR / "russia-mobile-whitelist-cidr.srs"

    print(f"  {domain_json.name}  →  {domain_srs.name}")
    _compile_srs(sing_box, domain_json, domain_srs)

    print(f"  {cidr_json.name}  →  {cidr_srs.name}")
    _compile_srs(sing_box, cidr_json, cidr_srs)

    # ------------------------------------------------------------------
    # 5. Summary
    # ------------------------------------------------------------------
    print()
    print("Output files:")
    for f in [domain_json, cidr_json, domain_srs, cidr_srs]:
        print(f"  {f}  ({f.stat().st_size:,} bytes)")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
