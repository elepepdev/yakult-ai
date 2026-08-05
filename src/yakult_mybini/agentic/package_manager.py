import asyncio
import json
import os
import re
import shutil
from typing import AsyncGenerator, Tuple, Optional
from loguru import logger


def detect_package_manager() -> str:
    for pm in ["apt", "dnf", "pacman", "zypper", "yum"]:
        if shutil.which(pm):
            return pm
        for path in [f"/usr/bin/{pm}", f"/bin/{pm}"]:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return pm
    return "unknown"


def detect_aur_helper() -> Optional[str]:
    for helper in ["paru", "yay"]:
        if shutil.which(helper):
            return helper
    return None


def _parse_pacman_progress(line: str) -> Optional[int]:
    m = re.search(r"\((\d+)/(\d+)\)", line)
    if m:
        return int(int(m.group(1)) / int(m.group(2)) * 100)
    m = re.search(r"Packages\s*\([^)]+\):\s*([\d.]+)%", line)
    if m:
        return int(float(m.group(1)))
    m = re.search(r"^\S+\s+([\d.]+)%\s+", line)
    if m:
        return int(float(m.group(1)))
    return None


def _parse_apt_progress(line: str) -> Optional[int]:
    m = re.search(r"Progress:\s*\[?\s*(\d+)%", line)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)%\s*\[", line)
    if m:
        return int(m.group(1))
    return None


def _parse_dnf_progress(line: str) -> Optional[int]:
    m = re.search(r"\((\d+)/(\d+)\)", line)
    if m:
        return int(int(m.group(1)) / int(m.group(2)) * 100)
    return None


def _parse_progress(line: str, pkg_manager: str) -> Optional[int]:
    if pkg_manager == "pacman":
        return _parse_pacman_progress(line)
    elif pkg_manager == "apt":
        return _parse_apt_progress(line)
    elif pkg_manager in ("dnf", "yum", "zypper"):
        return _parse_dnf_progress(line)
    return None


async def run_package_operation(
    operation: str,
    sudo_password: str,
    package_name: str = "",
    mode: str = "cascade",
    use_aur: bool = False,
) -> AsyncGenerator[Tuple[int, str, bool], None]:
    pkg_manager = detect_package_manager()
    if pkg_manager == "unknown":
        yield 100, json.dumps({"success": False, "error": "No supported package manager found"}), True
        return

    sudo_pw = sudo_password
    if not sudo_pw:
        yield 100, json.dumps({"success": False, "error": "SUDO_PASSWORD not configured"}), True
        return

    if operation == "update_system":
        commands = {
            "apt": "apt update && apt upgrade -y && apt autoremove -y && apt clean",
            "dnf": "dnf upgrade -y && dnf clean packages",
            "pacman": "pacman -Syu --noconfirm && pacman -Sc --noconfirm",
            "zypper": "zypper refresh && zypper update -y && zypper clean --all",
            "yum": "yum update -y && yum clean all",
        }
        if pkg_manager not in commands:
            yield 100, json.dumps({
                "success": False,
                "error": f"Unsupported package manager: {pkg_manager}"
            }), True
            return
        shell_cmd = f"echo '{sudo_pw}' | sudo -S bash -c '{commands[pkg_manager]}'"

    elif operation == "install_package":
        if not re.match(r"^[a-zA-Z0-9\-_+\.@/:]+$", package_name):
            yield 100, json.dumps({"success": False, "error": "Invalid package name format"}), True
            return

        helper = None
        if use_aur:
            helper = detect_aur_helper()
            if not helper:
                yield 100, json.dumps({"success": False, "error": "No AUR helper (paru or yay) found"}), True
                return
        else:
            helper = detect_aur_helper() or pkg_manager

        if helper == pkg_manager:
            shell_cmd = f"echo '{sudo_pw}' | sudo -S pacman -S --noconfirm {package_name}"
        else:
            shell_cmd = f"echo '{sudo_pw}' | sudo -S -v && {helper} -S --noconfirm {package_name}"

    elif operation == "remove_package":
        if not re.match(r"^[a-zA-Z0-9\-_+\.@/:]+$", package_name):
            yield 100, json.dumps({"success": False, "error": "Invalid package name format"}), True
            return

        flags_map = {"standard": "-R", "cascade": "-Rs", "complete": "-Rns"}
        flags = flags_map.get(mode, "-Rs")
        shell_cmd = f"echo '{sudo_pw}' | sudo -S pacman {flags} --noconfirm {package_name}"

    else:
        yield 100, json.dumps({"success": False, "error": f"Unknown operation: {operation}"}), True
        return

    logger.info(f"Running package operation: {operation} {package_name}")

    process = await asyncio.create_subprocess_shell(
        shell_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout_lines = []
    stderr_lines = []
    last_progress = 0

    async def read_stream(stream, lines_list, is_error: bool):
        nonlocal last_progress
        while True:
            line = await stream.readline()
            if not line:
                break
            decoded = line.decode("utf-8", errors="replace").rstrip()
            lines_list.append(decoded)
            if decoded:
                prog = _parse_progress(decoded, pkg_manager)
                if prog is not None and prog > last_progress:
                    last_progress = prog
                    yield (prog, decoded, is_error)

    stdout_gen = read_stream(process.stdout, stdout_lines, False)
    stderr_gen = read_stream(process.stderr, stderr_lines, True)

    while True:
        done = process.returncode is not None
        next_stdout = await anext(stdout_gen, None)
        next_stderr = await anext(stderr_gen, None)

        if next_stdout:
            yield next_stdout
        if next_stderr:
            yield next_stderr

        if done:
            break
        await asyncio.sleep(0.05)

    await process.wait()

    returncode = process.returncode
    is_error = returncode != 0
    result_content = json.dumps({
        "success": returncode == 0,
        "package_manager": pkg_manager,
        "output": "\n".join(stdout_lines[-50:]),
        "error": "\n".join(stderr_lines[-50:]) if is_error else None,
        "returncode": returncode,
    })
    yield (100, result_content, is_error)
