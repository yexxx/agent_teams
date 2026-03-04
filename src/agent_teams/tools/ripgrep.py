from __future__ import annotations

import io
import os
import shutil
import subprocess
import zipfile
import tarfile
from pathlib import Path
import httpx

from agent_teams.tools.ripgrep_errors import (
    UnsupportedPlatformError,
    DownloadFailedError,
    ExtractionFailedError,
)
from agent_teams.tools.ripgrep_types import GrepMatch, GrepResult

VERSION = "14.1.1"
BIN_DIR = Path.home() / ".agent-teams" / "bin"
_rg_path_cache: Path | None = None

PLATFORM_MAP = {
    "arm64-darwin": {"platform": "aarch64-apple-darwin", "extension": "tar.gz"},
    "arm64-linux": {"platform": "aarch64-unknown-linux-gnu", "extension": "tar.gz"},
    "x64-darwin": {"platform": "x86_64-apple-darwin", "extension": "tar.gz"},
    "x64-linux": {"platform": "x86_64-unknown-linux-musl", "extension": "tar.gz"},
    "x64-windows": {"platform": "x86_64-pc-windows-msvc", "extension": "zip"},
}


_ARCH_ALIASES = {
    "x86_64": "x64",
    "amd64": "x64",
    "x64": "x64",
    "aarch64": "arm64",
    "arm64": "arm64",
}

_SYSTEM_ALIASES = {
    "darwin": "darwin",
    "linux": "linux",
    "windows": "windows",
}



def _get_platform_key() -> str:
    import platform

    raw_arch = platform.machine().strip().lower()
    raw_system = platform.system().strip().lower()

    arch = _ARCH_ALIASES.get(raw_arch, raw_arch)
    system = _SYSTEM_ALIASES.get(raw_system, raw_system)
    if system.startswith("mingw") or system.startswith("msys") or system.startswith("cygwin"):
        system = "windows"

    return f"{arch}-{system}"


async def get_rg_path() -> Path:
    """鑾峰彇 ripgrep 鍙墽琛屾枃浠惰矾寰?(甯︾紦瀛?

    浼樺厛绾?
    1. 绯荤粺 ripgrep (shutil.which)
    2. 鏈湴缂撳瓨 (~/.agent-teams/bin/rg)
    3. 鑷姩涓嬭浇

    Returns:
        Path: ripgrep 鍙墽琛屾枃浠惰矾寰?

    Raises:
        UnsupportedPlatformError: 涓嶆敮鎸佺殑骞冲彴
        DownloadFailedError: 涓嬭浇澶辫触
        ExtractionFailedError: 瑙ｅ帇澶辫触
    """
    # 1. 绯荤粺 ripgrep
    global _rg_path_cache

    if _rg_path_cache and _rg_path_cache.is_file():
        return _rg_path_cache

    system_rg = shutil.which("rg")
    if system_rg:
        p = Path(system_rg)
        if p.is_file():
            _rg_path_cache = p
            return p

    # 2. 鏈湴缂撳瓨
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    ext = ".exe" if os.name == "nt" else ""
    local_path = BIN_DIR / f"rg{ext}"

    if local_path.exists() and local_path.is_file():
        _rg_path_cache = local_path
        return local_path

    # 3. 涓嬭浇
    await _download_rg(local_path)
    _rg_path_cache = local_path
    return local_path


def clear_rg_path_cache() -> None:
    global _rg_path_cache
    _rg_path_cache = None


async def _download_rg(target: Path) -> None:
    """涓嬭浇骞惰В鍘?ripgrep"""
    key = _get_platform_key()
    config = PLATFORM_MAP.get(key)
    if not config:
        raise UnsupportedPlatformError(key)

    filename = f"ripgrep-{VERSION}-{config['platform']}.{config['extension']}"
    url = (
        f"https://github.com/BurntSushi/ripgrep/releases/download/{VERSION}/{filename}"
    )

    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(url)
        if response.status_code != 200:
            raise DownloadFailedError(url, response.status_code)
        content = response.content

    if config["extension"] == "tar.gz":
        _extract_tarball(content, target)
    else:
        _extract_zip(content, target)

    if os.name != "nt":
        os.chmod(target, 0o755)


def _extract_tarball(content: bytes, target: Path) -> None:
    """瑙ｅ帇 tar.gz"""
    with tarfile.open(fileobj=io.BytesIO(content)) as tar:
        for member in tar.getmembers():
            name = member.name
            if name.endswith("rg") or name.endswith("rg.exe"):
                member.name = target.name
                tar.extract(member, target.parent)
                return
        raise ExtractionFailedError("rg not found in tarball")


def _extract_zip(content: bytes, target: Path) -> None:
    """瑙ｅ帇 zip"""
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        for name in zf.namelist():
            if name.endswith("rg.exe"):
                zf.extract(name, target.parent)
                extracted = target.parent / name
                extracted.rename(target)
                return
        raise ExtractionFailedError("rg.exe not found in zip")


async def grep_search(
    cwd: Path,
    pattern: str,
    *,
    glob: str | None = None,
    hidden: bool = True,
    case_sensitive: bool = True,
    limit: int = 100,
) -> GrepResult:
    """鎵ц grep 鎼滅储

    Args:
        cwd: 鎼滅储鐩綍
        pattern: 姝ｅ垯琛ㄨ揪寮忔ā寮?
        glob: 鏂囦欢鍚嶈繃婊?(濡?"*.py")
        hidden: 鏄惁鍖呭惈闅愯棌鏂囦欢
        case_sensitive: 鏄惁澶у皬鍐欐晱鎰?
        limit: 鏈€澶х粨鏋滄暟

    Returns:
        GrepResult: 鎼滅储缁撴灉
    """
    rg = await get_rg_path()

    args = [
        "-nH",
        "--hidden" if hidden else "",
        "--field-match-separator=|",
        "--max-count",
        str(limit),
        "--regexp",
        pattern,
    ]
    if glob:
        args.extend(["--glob", glob])
    if not case_sensitive:
        args.append("-i")

    args = [a for a in args if a]

    result = subprocess.run(
        [str(rg), *args, str(cwd)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    matches = []
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        parts = line.split("|")
        if len(parts) < 3:
            continue
        matches.append(
            GrepMatch(
                path=parts[0],
                line_num=int(parts[1]),
                line_text=parts[2],
            )
        )

    truncated = len(matches) >= limit
    return GrepResult(
        matches=matches,
        truncated=truncated,
        total=len(matches),
    )


async def enumerate_files(
    cwd: Path,
    pattern: str,
    *,
    hidden: bool = True,
    follow: bool = False,
    limit: int = 100,
) -> tuple[list[Path], bool]:
    """鏋氫妇鍖归厤 glob 妯″紡鐨勬枃浠?

    Args:
        cwd: 鎼滅储鐩綍
        pattern: glob 妯″紡
        hidden: 鏄惁鍖呭惈闅愯棌鏂囦欢
        follow: 鏄惁璺熼殢绗﹀彿閾炬帴
        limit: 鏈€澶ф枃浠舵暟

    Returns:
        (files, truncated): 鏂囦欢鍒楄〃鍜屾槸鍚︽埅鏂?
    """
    rg = await get_rg_path()

    args = [
        "--files",
        "--glob=!.git/*",
    ]
    if hidden:
        args.append("--hidden")
    if follow:
        args.append("--follow")
    args.extend(["--glob", pattern])

    proc = subprocess.Popen(
        [str(rg), *args, str(cwd)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    files: list[Path] = []
    truncated = False

    if proc.stdout is None:
        return files, truncated

    for line in proc.stdout:
        if len(files) >= limit:
            truncated = True
            proc.terminate()
            break
        files.append(Path(line.strip()))

    proc.wait()
    return files, truncated


