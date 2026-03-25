#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess
import sys

from utils import console_log


def _normalize_existing_path(path):
    """标准化并确认路径存在。"""
    if not path:
        return None
    normalized = dedup_repeated_dir(os.path.abspath(str(path).strip().strip('"')))
    return normalized if os.path.exists(normalized) else None


def _resolve_explicit_binary_path(path, candidates):
    """解析用户显式指定的文件或目录。"""
    normalized = _normalize_existing_path(path)
    if not normalized:
        return None
    if os.path.isfile(normalized):
        return normalized
    if os.path.isdir(normalized):
        return find_binary_shallow(normalized, candidates)
    return None


def _set_scrcpy_server_path(server_path):
    normalized = _normalize_existing_path(server_path)
    if normalized and os.path.isfile(normalized):
        os.environ["SCRCPY_SERVER_PATH"] = normalized
        return normalized
    return None


def dedup_repeated_dir(path):
    """Collapse duplicated parent folders like foo/foo/file.ext."""
    norm = os.path.normpath(path)
    if os.path.exists(norm):
        return norm
    parts = norm.split(os.sep)
    if len(parts) >= 4 and parts[-2].lower() == parts[-3].lower():
        parts.pop(-3)
        collapsed = os.sep.join(parts)
        if os.path.exists(collapsed):
            return collapsed
    return norm


def find_binary_shallow(base_dir, candidates, max_depth=2):
    """Search for executable candidates under base_dir with shallow depth."""
    if not base_dir or not os.path.isdir(base_dir):
        return None

    for name in candidates:
        root_candidate = os.path.join(base_dir, name)
        if os.path.isfile(root_candidate):
            return dedup_repeated_dir(root_candidate)

    for root, dirs, _files in os.walk(base_dir):
        depth = os.path.relpath(root, base_dir).count(os.sep)
        if depth > max_depth:
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in (".git", ".venv", "__pycache__")]
        for name in candidates:
            candidate = os.path.join(root, name)
            if os.path.isfile(candidate):
                return dedup_repeated_dir(candidate)
    return None


def _search_roots():
    roots = []
    cwd = os.getcwd()
    if os.path.isdir(cwd):
        roots.append(cwd)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.isdir(script_dir) and script_dir not in roots:
        roots.append(script_dir)
    exe_dir = os.path.dirname(sys.executable) if sys.executable else ""
    if exe_dir and os.path.isdir(exe_dir) and exe_dir not in roots:
        roots.append(exe_dir)
    return roots


def find_adb_path(preferred_path=None, return_details=False):
    """Locate adb executable, preferring configured/bundled/local binaries."""
    try:
        configured_adb = _resolve_explicit_binary_path(preferred_path, ("adb.exe", "adb"))
        if configured_adb:
            details = {"path": configured_adb, "source": "config"}
            return details if return_details else details["path"]
        if preferred_path:
            console_log(f"配置的 adb 路径无效，将继续自动检测: {preferred_path}", "WARN")

        if getattr(sys, "frozen", False):
            base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
            bundled_adb = find_binary_shallow(base_path, ("adb.exe", "adb"))
            if bundled_adb:
                details = {"path": bundled_adb, "source": "bundled"}
                return details if return_details else details["path"]

        for root in _search_roots():
            local_adb = find_binary_shallow(root, ("adb.exe", "adb"))
            if local_adb:
                details = {"path": local_adb, "source": "local"}
                return details if return_details else details["path"]

        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            result = subprocess.run(
                ["where", "adb"],
                capture_output=True,
                text=True,
                check=False,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout:
                for line in result.stdout.splitlines():
                    adb_candidate = line.strip()
                    if adb_candidate:
                        details = {"path": adb_candidate, "source": "path"}
                        return details if return_details else details["path"]
        else:
            result = subprocess.run(["which", "adb"], capture_output=True, text=True, check=False)
            if result.returncode == 0 and result.stdout.strip():
                details = {"path": result.stdout.strip(), "source": "path"}
                return details if return_details else details["path"]

        common_paths = [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "sdk", "platform-tools", "adb.exe"),
            os.path.join(os.environ.get("ProgramFiles", ""), "Android", "sdk", "platform-tools", "adb.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Android", "sdk", "platform-tools", "adb.exe"),
            "/usr/bin/adb",
            "/usr/local/bin/adb",
        ]
        for path in common_paths:
            if os.path.isfile(path):
                details = {"path": path, "source": "common"}
                return details if return_details else details["path"]
        details = {"path": "adb", "source": "fallback"}
        return details if return_details else details["path"]
    except Exception as e:
        console_log(f"查找 adb 路径时出错，回退到默认值: {e}", "WARN")
        details = {"path": "adb", "source": "fallback"}
        return details if return_details else details["path"]


def _resolve_scrcpy_with_server(scrcpy_path, preferred_server_path=None):
    if not scrcpy_path:
        return None
    configured_server = _set_scrcpy_server_path(preferred_server_path)
    if configured_server:
        return {"path": scrcpy_path, "server_path": configured_server, "server_source": "config"}
    server_dir = os.path.dirname(scrcpy_path)
    for name in ("scrcpy-server", "scrcpy-server.jar"):
        server_path = os.path.join(server_dir, name)
        if os.path.isfile(server_path):
            normalized = _set_scrcpy_server_path(server_path)
            return {"path": scrcpy_path, "server_path": normalized, "server_source": "co-located"}
    return {"path": scrcpy_path, "server_path": None, "server_source": None}


def _find_scrcpy_in_path():
    path_env = os.environ.get("PATH", "")
    if not path_env:
        return []
    candidates = []
    exe_name = "scrcpy.exe" if os.name == "nt" else "scrcpy"
    for entry in path_env.split(os.pathsep):
        entry = entry.strip('"')
        if not entry:
            continue
        candidate = os.path.join(entry, exe_name)
        if os.path.isfile(candidate):
            candidates.append(candidate)
    return candidates


def find_scrcpy_path(preferred_path=None, preferred_server_path=None, return_details=False):
    """Locate scrcpy executable and prefer configured/bundled/local binaries."""
    try:
        configured_scrcpy = _resolve_explicit_binary_path(preferred_path, ("scrcpy.exe", "scrcpy"))
        if configured_scrcpy:
            resolved = _resolve_scrcpy_with_server(configured_scrcpy, preferred_server_path=preferred_server_path)
            resolved["source"] = "config"
            return resolved if return_details else resolved["path"]
        if preferred_path:
            console_log(f"配置的 scrcpy 路径无效，将继续自动检测: {preferred_path}", "WARN")
        if preferred_server_path and not _normalize_existing_path(preferred_server_path):
            console_log(f"配置的 scrcpy-server 路径无效，将尝试自动定位: {preferred_server_path}", "WARN")

        if getattr(sys, "frozen", False):
            base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
            bundled_scrcpy = find_binary_shallow(base_path, ("scrcpy.exe", "scrcpy"))
            resolved = _resolve_scrcpy_with_server(bundled_scrcpy, preferred_server_path=preferred_server_path)
            if resolved:
                resolved["source"] = "bundled"
                return resolved if return_details else resolved["path"]

        for root in _search_roots():
            local_scrcpy = find_binary_shallow(root, ("scrcpy.exe", "scrcpy"))
            resolved = _resolve_scrcpy_with_server(local_scrcpy, preferred_server_path=preferred_server_path)
            if resolved:
                resolved["source"] = "local"
                return resolved if return_details else resolved["path"]

        path_candidates = _find_scrcpy_in_path()
        if os.name == "nt" and not path_candidates:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            result = subprocess.run(
                ["where", "scrcpy"],
                capture_output=True,
                text=True,
                check=False,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout:
                path_candidates = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        elif os.name != "nt" and not path_candidates:
            result = subprocess.run(["which", "scrcpy"], capture_output=True, text=True, check=False)
            if result.returncode == 0 and result.stdout.strip():
                path_candidates = [result.stdout.strip()]

        fallback = None
        for scrcpy_candidate in path_candidates:
            fallback = fallback or scrcpy_candidate
            resolved = _resolve_scrcpy_with_server(scrcpy_candidate, preferred_server_path=preferred_server_path)
            if resolved:
                resolved["source"] = "path"
                return resolved if return_details else resolved["path"]
        if fallback:
            resolved = {"path": fallback, "server_path": None, "server_source": None, "source": "path"}
            return resolved if return_details else resolved["path"]

        common_paths = [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "scrcpy", "scrcpy.exe"),
            os.path.join(os.environ.get("ProgramFiles", ""), "scrcpy", "scrcpy.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", ""), "scrcpy", "scrcpy.exe"),
            "/usr/bin/scrcpy",
            "/usr/local/bin/scrcpy",
        ]
        fallback = None
        for path in common_paths:
            if os.path.isfile(path):
                fallback = fallback or path
                resolved = _resolve_scrcpy_with_server(path, preferred_server_path=preferred_server_path)
                if resolved:
                    resolved["source"] = "common"
                    return resolved if return_details else resolved["path"]
        resolved = {"path": fallback or "scrcpy", "server_path": None, "server_source": None, "source": "fallback"}
        return resolved if return_details else resolved["path"]
    except Exception as e:
        console_log(f"查找 scrcpy 路径时出错，回退到默认值: {e}", "WARN")
        resolved = {"path": "scrcpy", "server_path": None, "server_source": None, "source": "fallback"}
        return resolved if return_details else resolved["path"]


def check_command_available(command_path, version_arg):
    """Check whether a command can be executed successfully."""
    try:
        kwargs = {}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        subprocess.run([command_path, version_arg], capture_output=True, check=False, **kwargs)
        return True
    except Exception as e:
        console_log(f"检查命令可用性失败 ({command_path} {version_arg}): {e}", "WARN")
        return False


def build_scrcpy_command(
    scrcpy_path,
    device_id,
    *,
    bit_rate=None,
    max_size=None,
    max_fps=None,
    record_path=None,
    fullscreen=False,
    always_on_top=False,
    show_touches=False,
    no_control=False,
    disable_clipboard=False,
    rotation="不限制",
    turn_screen_off=False,
    stay_awake=False,
    video_codec=None,
    display_id=None,
    crop=None,
    no_window=False,
    window_title=None,
    no_audio=True,
    window_x=None,
    window_y=None,
):
    """Build a scrcpy command from normalized UI options."""
    cmd = [scrcpy_path, "-s", device_id]

    if bit_rate not in (None, ""):
        cmd.extend(["--video-bit-rate", f"{bit_rate}M"])
    if max_size not in (None, ""):
        cmd.extend(["--max-size", str(max_size)])
    if max_fps not in (None, ""):
        cmd.extend(["--max-fps", str(max_fps)])
    if record_path:
        cmd.extend(["--record", record_path])
    if fullscreen:
        cmd.append("--fullscreen")
    if always_on_top:
        cmd.append("--always-on-top")
    if show_touches:
        cmd.append("--show-touches")
    if no_control:
        cmd.append("--no-control")
    if disable_clipboard:
        cmd.append("--no-clipboard-autosync")
    if rotation == "横屏":
        cmd.append("--lock-video-orientation=0")
    elif rotation == "竖屏":
        cmd.append("--lock-video-orientation=1")
    if turn_screen_off:
        cmd.append("--turn-screen-off")
    if stay_awake:
        cmd.append("--stay-awake")
    if video_codec:
        cmd.extend(["--video-codec", str(video_codec)])
    if display_id not in (None, ""):
        cmd.extend(["--display-id", str(display_id)])
    if crop:
        cmd.extend(["--crop", str(crop)])
    if no_window:
        cmd.append("--no-window")
    if window_title:
        cmd.extend(["--window-title", window_title])
    if no_audio:
        cmd.append("--no-audio")
    if window_x is not None:
        cmd.extend(["--window-x", str(window_x)])
    if window_y is not None:
        cmd.extend(["--window-y", str(window_y)])

    return cmd