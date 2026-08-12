import json
import os
import sys
import shutil
import time
import traceback
import uuid
from datetime import datetime, timezone
from typing import Annotated
from pydantic import Field

def _detect_package_manager() -> str:
    for pm in ["apt", "dnf", "pacman", "zypper", "yum"]:
        # First, try standard PATH lookup
        if shutil.which(pm):
            return pm
        # Fallback to common absolute locations
        for path in [f"/usr/bin/{pm}", f"/bin/{pm}"]:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return pm
    return "unknown"

_this_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_this_dir)
_grandparent_dir = os.path.dirname(_parent_dir)
for p in [_this_dir, _parent_dir, _grandparent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from mcp.server.fastmcp import FastMCP

if sys.platform == "linux" and "DISPLAY" not in os.environ:
    os.environ["DISPLAY"] = ":0"

from yakult_mybini.agentic.desktop_controller import DesktopController
from yakult_mybini.agentic.web_searcher import WebSearcher
from yakult_mybini.agentic.web_fetcher import WebFetcher
from yakult_mybini.agentic.ocr import ocr_image, ocr_screen

mcp = FastMCP("desktop-controller")
controller = DesktopController(safety_level=os.environ.get("AGENTIC_SAFETY", "medium"))
searcher = WebSearcher()
fetcher = WebFetcher()


@mcp.tool(name="open_app", description="Open or focus an application by name (e.g. 'firefox', 'vscode', 'terminal', 'discord'). If already running, focuses the existing window. Optionally pass a url to navigate to. The user's default browser is Firefox — use 'firefox' as the target name when opening the browser.")
def open_app(target: str, url: str = None) -> str:
    params = {}
    if url:
        params["url"] = url
    result = controller.execute_action({"type": "open_app", "target": target, "params": params})
    return json.dumps(result)


@mcp.tool(name="focus_app", description="Focus an already-running application window (e.g. 'terminal', 'chrome') without opening a new instance. Use this when the app is already open and you just need to switch to it before typing.")
def focus_app(target: str) -> str:
    result = controller.execute_action({"type": "focus_app", "target": target})
    return json.dumps(result)


@mcp.tool(name="close_app", description="Close an application gracefully by name (e.g. 'firefox', 'vscode', 'discord'). Sends a close request to the application's window(s) — equivalent to clicking the X button. The app can clean up and save work before closing. ALWAYS use this instead of run_command with pkill.")
def close_app(target: str) -> str:
    result = controller.execute_action({"type": "close_app", "target": target})
    return json.dumps(result)


@mcp.tool(name="open_url", description="Open a URL in the system's default browser (Firefox). Uses xdg-open to respect the system default.")
def open_url(url: str) -> str:
    try:
        import subprocess
        subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return json.dumps({"success": True, "message": f"Opened {url} in the default browser"})
    except FileNotFoundError:
        return json.dumps({"success": False, "error": "No default browser found (xdg-open not available)"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool(name="type_text", description="Click at (click_x, click_y) or a grid_cell (e.g. 'E5') then type text. ALWAYS set image_width and image_height from the [Shared screen image dimensions...] note (NOT guesses) so coordinates are mapped correctly to your physical screen. Use cell_x/cell_y (0-1) for sub-cell positioning when target is not exactly at center. Never type without clicking first, otherwise text goes to the wrong place.")
def type_text(text: str, click_x: int = None, click_y: int = None, image_width: int = None, image_height: int = None, grid_cell: str = None, grid_rows: int = 6, grid_cols: int = 8, cell_x: float = 0.5, cell_y: float = 0.5) -> str:
    params = {"text": text, "click_x": click_x, "click_y": click_y, "grid_cell": grid_cell, "grid_rows": grid_rows, "grid_cols": grid_cols, "cell_x": cell_x, "cell_y": cell_y}
    if image_width is not None:
        params["image_width"] = image_width
    if image_height is not None:
        params["image_height"] = image_height
    result = controller.execute_action({"type": "type_text", "params": params})
    return json.dumps(result)


@mcp.tool(name="press_key", description="Press a single keyboard key like 'enter', 'escape', 'tab', 'a', 'ctrl'. Use this for pressing individual special keys or single characters. Parameter 'target': the key name to press (NOT the same as 'text' in type_text).")
def press_key(target: str) -> str:
    result = controller.execute_action({"type": "press_key", "target": target})
    return json.dumps(result)


@mcp.tool(name="hotkey", description="Press a keyboard shortcut combination (e.g. ['ctrl', 'c'], ['alt', 'tab'])")
def hotkey(keys: list[str]) -> str:
    result = controller.execute_action({"type": "hotkey", "params": {"keys": keys}})
    return json.dumps(result)


@mcp.tool(name="click", description="Click mouse at (x,y) coordinates, or at a grid_cell (e.g. 'E5') if using the grid overlay system. Use cell_x/cell_y (0-1, default 0.5) for sub-cell positioning when the target is not exactly centered. ALWAYS pass image_width and image_height from the [Shared screen image dimensions...] note for accurate clicking on a shared screen. If omitted, coordinates are assumed to already be in screen pixels. Use this BEFORE type_text when you need to focus a specific text input field.")
def click(x: int = None, y: int = None, image_width: int = None, image_height: int = None, grid_cell: str = None, grid_rows: int = 6, grid_cols: int = 8, cell_x: float = 0.5, cell_y: float = 0.5) -> str:
    params = {}
    if x is not None:
        params["x"] = x
    if y is not None:
        params["y"] = y
    if image_width is not None:
        params["image_width"] = image_width
    if image_height is not None:
        params["image_height"] = image_height
    if grid_cell is not None:
        params["grid_cell"] = grid_cell
    params["grid_rows"] = grid_rows
    params["grid_cols"] = grid_cols
    params["cell_x"] = cell_x
    params["cell_y"] = cell_y
    result = controller.execute_action({"type": "click", "params": params})
    return json.dumps(result)


@mcp.tool(name="screen_size", description="Return the physical screen resolution in pixels. Use this together with the screen share's image_width/image_height to compute a coordinate scale factor before calling click/x11_click/type_text on a shared/scaled screen.")
def screen_size() -> str:
    result = controller.execute_action({"type": "screen_size"})
    return json.dumps(result)


@mcp.tool(name="run_command", description="Run a shell/terminal command. Use this ANY TIME the user asks you to run a command, execute a script, start a program, or do anything on the terminal. Never just pretend to run a command — always use this tool. The output will be shown to the user. Blocked commands: rm, rmdir, shutdown, reboot, poweroff, mkfs, dd")
def run_command(target: str) -> str:
    result = controller.execute_action({"type": "run_command", "target": target})
    return json.dumps(result)


@mcp.tool(name="run_sudo_command", description="Run a shell command with sudo (root privileges). Requires sudo_password to be set in conf.yaml. Use this for system-level operations that need admin access. Never pretend to run a command — always use this tool if the user asks for something that needs sudo.")
def run_sudo_command(target: str) -> str:
    result = controller.execute_action({"type": "run_sudo_command", "target": target})
    return json.dumps(result)


@mcp.tool(name="detect_os", description="Detect the operating system and available package manager. Run this first before update_system to know what package manager to use (apt, dnf, pacman, zypper, etc.). Returns OS name, version, and package manager.")
def detect_os() -> str:
    try:
        import subprocess
        os_info = {}
        result = subprocess.run("cat /etc/os-release", shell=True, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if "=" in line:
                    key, val = line.split("=", 1)
                    os_info[key.strip()] = val.strip().strip('"')
        pkg_manager = _detect_package_manager()
        return json.dumps({
            "success": True,
            "os_name": os_info.get("NAME", "Unknown"),
            "os_version": os_info.get("VERSION_ID", "Unknown"),
            "os_id": os_info.get("ID", "unknown"),
            "package_manager": pkg_manager,
            "pretty_name": os_info.get("PRETTY_NAME", "Unknown"),
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool(name="update_system", description="Update the system packages. Auto-detects the Linux distro and uses the correct package manager (apt, dnf, pacman, zypper, yum). Runs: update package lists, upgrade all packages, and clean cache. Use this when the user asks to update their system.")
def update_system() -> str:
    try:
        import subprocess

        pkg_manager = _detect_package_manager()

        commands = {
            "apt": "sudo -S bash -c 'apt update && apt upgrade -y && apt autoremove -y && apt clean'",
            "dnf": "sudo -S bash -c 'dnf upgrade -y && dnf clean packages'",
            "pacman": "sudo -S bash -c 'pacman -Syu --noconfirm && pacman -Sc --noconfirm'",
            "zypper": "sudo -S bash -c 'zypper refresh && zypper update -y && zypper clean --all'",
            "yum": "sudo -S bash -c 'yum update -y && yum clean all'",
        }

        if pkg_manager not in commands:
            return json.dumps({
                "success": False,
                "error": f"Unsupported package manager: {pkg_manager}. Supported: apt, dnf, pacman, zypper, yum",
                "detectedPackageManager": pkg_manager,
            })

        sudo_pw = os.environ.get("SUDO_PASSWORD", "")
        if not sudo_pw:
            return json.dumps({"success": False, "error": "SUDO_PASSWORD not configured (set sudo_password in conf.yaml)"})

        full_cmd = f"echo '{sudo_pw}' | {commands[pkg_manager]}"
        result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True, timeout=600)
        return json.dumps({
            "success": result.returncode == 0,
            "packageManager": pkg_manager,
            "output": result.stdout[-2000:] if result.stdout else None,
            "error": result.stderr[-2000:] if result.returncode != 0 and result.stderr else None,
            "returncode": result.returncode,
        })
    except subprocess.TimeoutExpired:
        return json.dumps({"success": False, "error": "Update timeout (600s) - system update may still be running in background"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool(name="find_element", description="Find UI elements by name, role, text, or app. Use this to locate buttons, links, inputs, etc. before clicking. Returns element coordinates and metadata.")
def find_element(name: str = None, role: str = None, app_name: str = None, text: str = None, max_results: int = 10) -> str:
    result = controller.execute_action({
        "type": "find_element", 
        "params": {"name": name, "role": role, "app_name": app_name, "text": text, "max_results": max_results}
    })
    return json.dumps(result)


@mcp.tool(name="click_element", description="Click a UI element by name (and optionally role/app). Use find_element first to locate it, then click_element with the same name.")
def click_element(name: str, role: str = None, app_name: str = None) -> str:
    result = controller.execute_action({
        "type": "click_element", 
        "params": {"name": name, "role": role, "app_name": app_name}
    })
    return json.dumps(result)


@mcp.tool(name="list_clickable_elements", description="List all clickable/interactive elements (buttons, links, inputs, etc.) in an app or globally. Use this to see what's clickable before clicking.")
def list_clickable_elements(app_name: str = None, max_results: int = 20) -> str:
    result = controller.execute_action({
        "type": "list_clickable_elements", 
        "params": {"app_name": app_name, "max_results": max_results}
    })
    return json.dumps(result)


@mcp.tool(name="get_active_window", description="Get the currently focused window name")
def get_active_window() -> str:
    result = controller.execute_action({"type": "get_active_window"})
    return json.dumps(result)


@mcp.tool(name="web_search", description="Search the web using DuckDuckGo. Returns titles, URLs, and snippets. CRITICAL: For ANY query about current events, scores, weather, prices, news, dates, or time-sensitive information, you MUST use timelimit (e.g., timelimit='d' for today, 'w' for this week, 'm' for this month). The default (no timelimit) returns stale/old results. Use this FIRST to find relevant pages, then use web_fetch to read full content. Try different keywords, regions, and languages if first results are insufficient.")
def web_search(
    query: str,
    max_results: int = 15,
    region: str = None,
    timelimit: Annotated[str, Field(description="Time filter: 'd'=past day, 'w'=past week, 'm'=past month, 'y'=past year")] = None
) -> str:
    result = searcher.search(query, max_results, region, timelimit)
    return json.dumps(result)


@mcp.tool(name="search_news", description="Search news articles using DuckDuckGo. Returns results WITH DATES so you can prioritize recent articles. CRITICAL: Always use timelimit for breaking news or recent events (timelimit='d' for today, 'w' for this week). Results include 'date' field — use it to pick the newest articles.")
def search_news(
    query: str,
    max_results: int = 15,
    timelimit: Annotated[str, Field(description="Time filter: 'd'=past day, 'w'=past week, 'm'=past month, 'y'=past year")] = None
) -> str:
    result = searcher.search_news(query, max_results, timelimit)
    return json.dumps(result)


@mcp.tool(name="web_fetch", description="Fetch and read the full content of a web page. Use after web_search to read details. Extracts title, description, headings, paragraphs, and links. The content is cleaned from HTML/script/styling.")
def web_fetch(url: str, max_chars: int = 8000) -> str:
    result = fetcher.fetch(url, max_chars)
    return json.dumps(result)


MEMORIES_DIR = os.environ.get("MEMORIES_DIR", os.path.join(os.getcwd(), "memories"))
TODOS_DIR = os.environ.get("TODOS_DIR", os.path.join(os.getcwd(), "todos"))


@mcp.tool(name="store_memory", description="Store an important fact about the user into long-term memory. Call this when you learn something worth remembering: user preferences, personal info, ongoing tasks/projects, mistakes to avoid, or facts about the user. Be selective — don't store trivial chit-chat. Only store meaningful facts that will help you serve the user better in future conversations.")
def store_memory(
    fact: str,
    category: Annotated[str, Field(description="Category: 'preference' (likes/dislikes), 'personal' (name, age, work), 'task' (ongoing projects), 'fact' (general knowledge about user)")] = "fact",
) -> str:
    try:
        shared_dir = os.path.join(MEMORIES_DIR, "shared")
        os.makedirs(shared_dir, exist_ok=True)
        path = os.path.join(shared_dir, "memories.json")
        memories = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                memories = json.load(f)
        memories.append({
            "id": f"mem_{uuid.uuid4().hex[:12]}",
            "fact": fact,
            "category": category,
            "confidence": 0.9,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "accessed_count": 0,
        })
        with open(path, "w", encoding="utf-8") as f:
            json.dump(memories, f, indent=2, ensure_ascii=False)
        return json.dumps({"success": True, "message": f"Memorized: {fact}"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool(name="add_todo", description="Add a to-do item with optional reminder time. Use this when the user tells you to remember something, a task, or a reminder. CRITICAL: Parse the time from the user's words (e.g. 'jam 3' = 15:00, 'jam 8 pagi' = 08:00, 'besok jam 10' = tomorrow 10:00). The datetime_str must be in ISO format like '2026-07-18T15:00:00+07:00'. If no time specified, pass empty string.")
def add_todo(text: str, datetime_str: str = "") -> str:
    try:
        path = os.path.join(TODOS_DIR, "todos.json")
        os.makedirs(TODOS_DIR, exist_ok=True)
        todos = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                todos = json.load(f)
        todo_id = f"todo_{uuid.uuid4().hex[:12]}"
        todos.append({
            "id": todo_id,
            "text": text,
            "datetime": datetime_str,
            "completed": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        if len(todos) > 100:
            todos = todos[-100:]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(todos, f, indent=2, ensure_ascii=False)
        return json.dumps({"success": True, "id": todo_id, "message": f"Todo added: {text}"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool(name="list_todos", description="List all to-do items. Returns id, text, datetime, completed status for each.")
def list_todos() -> str:
    try:
        path = os.path.join(TODOS_DIR, "todos.json")
        if not os.path.exists(path):
            return json.dumps({"success": True, "todos": []})
        with open(path, encoding="utf-8") as f:
            todos = json.load(f)
        return json.dumps({"success": True, "todos": todos})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool(name="delete_todo", description="Delete a to-do item by its ID.")
def delete_todo(todo_id: str) -> str:
    try:
        path = os.path.join(TODOS_DIR, "todos.json")
        if not os.path.exists(path):
            return json.dumps({"success": False, "error": "No todos file"})
        with open(path, encoding="utf-8") as f:
            todos = json.load(f)
        filtered = [t for t in todos if t["id"] != todo_id]
        if len(filtered) == len(todos):
            return json.dumps({"success": False, "error": "Todo not found"})
        with open(path, "w", encoding="utf-8") as f:
            json.dump(filtered, f, indent=2, ensure_ascii=False)
        return json.dumps({"success": True})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool(name="update_todo", description="Update a to-do item: mark completed/unfinished, change text, or change reminder time.")
def update_todo(todo_id: str, text: str = None, datetime_str: str = None, completed: bool = None) -> str:
    try:
        path = os.path.join(TODOS_DIR, "todos.json")
        if not os.path.exists(path):
            return json.dumps({"success": False, "error": "No todos file"})
        with open(path, encoding="utf-8") as f:
            todos = json.load(f)
        for t in todos:
            if t["id"] == todo_id:
                if text is not None:
                    t["text"] = text
                if datetime_str is not None:
                    t["datetime"] = datetime_str
                if completed is not None:
                    t["completed"] = completed
                break
        else:
            return json.dumps({"success": False, "error": "Todo not found"})
        with open(path, "w", encoding="utf-8") as f:
            json.dump(todos, f, indent=2, ensure_ascii=False)
        return json.dumps({"success": True})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool(name="find_window", description="Find windows by name or class. Returns window IDs, names, classes, and geometry. Use this to locate browser windows, terminals, etc.")
def find_window(name: str = None, class_name: str = None) -> str:
    result = controller.execute_action({"type": "find_window", "params": {"name": name, "class": class_name}})
    return json.dumps(result)


@mcp.tool(name="click_window", description="Click on a window by ID. Use find_window first to get the window_id. click_type: 'center' (default) or 'relative' with rel_x, rel_y (0.0-1.0)")
def click_window(window_id: int, click_type: str = "center", rel_x: float = 0.5, rel_y: float = 0.5) -> str:
    result = controller.execute_action({
        "type": "click_window", 
        "params": {"window_id": window_id, "click_type": click_type, "rel_x": rel_x, "rel_y": rel_y}
    })
    return json.dumps(result)


@mcp.tool(name="x11_click", description="Click at absolute screen coordinates (x, y) using X11, or at a grid_cell (e.g. 'E5') if using the grid overlay system. Use cell_x/cell_y (0-1, default 0.5) for sub-cell positioning. ALWAYS pass image_width and image_height from the [Shared screen image dimensions...] note when the shared screen is scaled so coordinates are mapped correctly to the physical screen.")
def x11_click(x: int = None, y: int = None, image_width: int = None, image_height: int = None, grid_cell: str = None, grid_rows: int = 6, grid_cols: int = 8, cell_x: float = 0.5, cell_y: float = 0.5) -> str:
    params = {"x": x, "y": y, "grid_cell": grid_cell, "grid_rows": grid_rows, "grid_cols": grid_cols, "cell_x": cell_x, "cell_y": cell_y}
    if image_width is not None:
        params["image_width"] = image_width
    if image_height is not None:
        params["image_height"] = image_height
    result = controller.execute_action({"type": "x11_click", "params": params})
    return json.dumps(result)


@mcp.tool(name="x11_type", description="Type text at current cursor position using X11")
def x11_type(text: str) -> str:
    result = controller.execute_action({"type": "x11_type", "params": {"text": text}})
    return json.dumps(result)


@mcp.tool(name="x11_key", description="Press a single key using X11 (e.g., 'Return', 'Escape', 'Tab', 'a', 'ctrl+c')")
def x11_key(key: str) -> str:
    result = controller.execute_action({"type": "x11_key", "target": key})
    return json.dumps(result)


@mcp.tool(name="x11_hotkey", description="Press key combination using X11 (e.g., ['ctrl', 'c'], ['alt', 'tab'])")
def x11_hotkey(keys: list[str]) -> str:
    result = controller.execute_action({"type": "x11_hotkey", "params": {"keys": keys}})
    return json.dumps(result)


@mcp.tool(name="x11_active_window", description="Get the currently active/focused window info using X11")
def x11_active_window() -> str:
    result = controller.execute_action({"type": "x11_active_window"})
    return json.dumps(result)


@mcp.tool(name="focus_window", description="Focus/raise a window by ID. Use find_window first to get the window_id.")
def focus_window(window_id: int) -> str:
    result = controller.execute_action({"type": "focus_window", "params": {"window_id": window_id}})
    return json.dumps(result)


@mcp.tool(name="list_windows", description="List all visible windows, optionally filtered by name or class")
def list_windows(name: str = None, class_name: str = None) -> str:
    result = controller.execute_action({"type": "list_windows", "params": {"name": name, "class": class_name}})
    return json.dumps(result)


@mcp.tool(name="delete_file", description="Delete a file or empty directory. Use force=True to delete non-empty directories. For file/folder operations prefer this over run_command('rm ...').")
def delete_file(path: str, force: bool = False) -> str:
    result = controller.execute_action({"type": "delete_file", "params": {"path": path, "force": force}})
    return json.dumps(result)


def parse_search_output(output: str) -> list:
    packages = []
    lines = output.strip().split("\n")
    current_pkg = None
    
    for line in lines:
        if not line:
            continue
        if line.startswith("    "):
            if current_pkg:
                current_pkg["description"] = (current_pkg["description"] + " " + line.strip()).strip()
        else:
            parts = line.strip().split(" ", 1)
            if len(parts) >= 1:
                repo_name = parts[0]
                version_info = parts[1] if len(parts) > 1 else ""
                
                if "/" in repo_name:
                    repo, name = repo_name.split("/", 1)
                else:
                    repo = "unknown"
                    name = repo_name
                
                installed = "[installed]" in line or "(installed)" in line or repo == "local"
                
                current_pkg = {
                    "name": name,
                    "repo": repo,
                    "version": version_info,
                    "description": "",
                    "installed": installed
                }
                packages.append(current_pkg)
    return packages


@mcp.tool(name="search_packages", description="Search for packages in repositories and the AUR, or locally. Set local_only=True to search only installed packages. Returns a JSON list of matches.")
def search_packages(query: str, local_only: bool = False) -> str:
    try:
        import subprocess
        import shutil
        import re
        
        # Sanitize query to prevent any argument injection/weird characters
        if not re.match(r"^[a-zA-Z0-9\-_+\.@/:\s*?]+$", query):
            return json.dumps({"success": False, "error": "Invalid search query format."})
            
        helper = None
        if local_only:
            helper = "pacman"
        else:
            if shutil.which("paru"):
                helper = "paru"
            elif shutil.which("yay"):
                helper = "yay"
            elif shutil.which("pacman"):
                helper = "pacman"
                
        if not helper:
            return json.dumps({"success": False, "error": "No package manager/helper found."})
            
        # Run search command: -Qs for local search, -Ss for database search
        flag = "-Qs" if local_only else "-Ss"
        cmd = [helper, flag, query]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        
        if result.returncode != 0 and not result.stdout:
            return json.dumps({
                "success": False, 
                "error": f"Search command failed or no results found for '{query}'.",
                "details": result.stderr
            })
            
        packages = parse_search_output(result.stdout)
        return json.dumps({
            "success": True,
            "package_manager": helper,
            "packages": packages
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool(name="get_pkgbuild", description="Retrieve the PKGBUILD file contents for an AUR package. Run this to allow the AI to review the package's recipe before installing to check if it is safe or malicious.")
def get_pkgbuild(package_name: str) -> str:
    try:
        import subprocess
        import shutil
        import re
        
        # Sanitize package name
        if not re.match(r"^[a-zA-Z0-9\-_+\.@/:]+$", package_name):
            return json.dumps({"success": False, "error": "Invalid package name format."})
            
        helper = None
        if shutil.which("paru"):
            helper = "paru"
        elif shutil.which("yay"):
            helper = "yay"
            
        if not helper:
            return json.dumps({"success": False, "error": "No AUR helper (paru or yay) found to fetch PKGBUILD."})
            
        result = subprocess.run([helper, "-Gp", package_name], capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            return json.dumps({
                "success": False, 
                "error": f"Failed to retrieve PKGBUILD for {package_name}. It might be an official repository package (which do not use the AUR) or the package name is invalid.",
                "details": result.stderr
            })
            
        return json.dumps({
            "success": True,
            "package_name": package_name,
            "helper": helper,
            "pkgbuild": result.stdout
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool(name="install_package", description="Install a package. Automatically detects the correct package manager (pacman, paru, yay) based on system and package source (repo or AUR). Uses the configured sudo password.")
def install_package(package_name: str, use_aur: bool = False) -> str:
    try:
        import subprocess
        import shutil
        import re
        
        # Sanitize package name
        if not re.match(r"^[a-zA-Z0-9\-_+\.@/:]+$", package_name):
            return json.dumps({"success": False, "error": "Invalid package name format."})
            
        # Detect package manager
        helper = None
        if use_aur:
            if shutil.which("paru"):
                helper = "paru"
            elif shutil.which("yay"):
                helper = "yay"
            else:
                return json.dumps({"success": False, "error": "No AUR helper (paru or yay) found to install AUR package."})
        else:
            if shutil.which("paru"):
                helper = "paru"
            elif shutil.which("yay"):
                helper = "yay"
            elif shutil.which("pacman"):
                helper = "pacman"
            else:
                return json.dumps({"success": False, "error": "No supported package manager (pacman, paru, yay) found."})
                
        sudo_pw = os.environ.get("SUDO_PASSWORD", "")
        if not sudo_pw:
            return json.dumps({"success": False, "error": "SUDO_PASSWORD not configured (set sudo_password in conf.yaml)"})
            
        if helper == "pacman":
            full_cmd = f"echo '{sudo_pw}' | sudo -S pacman -S --noconfirm {package_name}"
        else:
            # For AUR helpers, we validate sudo first so they don't prompt for password when invoking sudo to install the package
            full_cmd = f"echo '{sudo_pw}' | sudo -S -v && {helper} -S --noconfirm {package_name}"
            
        result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True, timeout=600)
        
        return json.dumps({
            "success": result.returncode == 0,
            "package_manager": helper,
            "output": result.stdout[-2000:] if result.stdout else None,
            "error": result.stderr[-2000:] if result.returncode != 0 and result.stderr else None,
            "returncode": result.returncode,
        })
    except subprocess.TimeoutExpired:
        return json.dumps({"success": False, "error": "Installation timeout (600s)"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool(name="remove_package", description="Remove an installed package from the system. Modes: 'standard' (removes only the package, equivalent to pacman -R), 'cascade' (removes package and its unused dependencies, equivalent to pacman -Rs), 'complete' (removes package, config files, and unused dependencies, equivalent to pacman -Rns).")
def remove_package(package_name: str, mode: str = "cascade") -> str:
    try:
        import subprocess
        import re
        
        # Sanitize package name
        if not re.match(r"^[a-zA-Z0-9\-_+\.@/:]+$", package_name):
            return json.dumps({"success": False, "error": "Invalid package name format."})
            
        if mode not in ["standard", "cascade", "complete"]:
            return json.dumps({"success": False, "error": "Invalid removal mode. Choose from: 'standard', 'cascade', 'complete'."})
            
        sudo_pw = os.environ.get("SUDO_PASSWORD", "")
        if not sudo_pw:
            return json.dumps({"success": False, "error": "SUDO_PASSWORD not configured (set sudo_password in conf.yaml)"})
            
        # Determine pacman flags
        flags = "-R"
        if mode == "cascade":
            flags = "-Rs"
        elif mode == "complete":
            flags = "-Rns"
            
        full_cmd = f"echo '{sudo_pw}' | sudo -S pacman {flags} --noconfirm {package_name}"
        result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True, timeout=120)
        
        return json.dumps({
            "success": result.returncode == 0,
            "output": result.stdout[-2000:] if result.stdout else None,
            "error": result.stderr[-2000:] if result.returncode != 0 and result.stderr else None,
            "returncode": result.returncode,
        })
    except subprocess.TimeoutExpired:
        return json.dumps({"success": False, "error": "Removal timeout (120s)"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool(name="set_grid_spec", description="Change the grid density. Grid overlay is ALREADY active by default on all screen-shared images. Use this to switch between '8x6' (48 cells, default), '10x10' (100 cells, more precision), or '6x4' (24 cells, coarse). The grid is always on — call disable_grid_overlay() if you need a clean image without grid lines.")
def set_grid_spec(grid_spec: str = "8x6") -> str:
    from .grid_state import set_grid_spec
    return set_grid_spec(grid_spec)


@mcp.tool(name="disable_grid_overlay", description="Temporarily disable the grid overlay. Screen images will be sent WITHOUT grid after this. Call this only when you need a clean image. Grid re-activates automatically on next server restart.")
def disable_grid_overlay() -> str:
    from .grid_state import disable
    return disable()


@mcp.tool(name="ocr_screen", description="Capture the screen and read (OCR) all text currently visible on it. Optionally pass a region [left, top, width, height] to read text from only part of the screen. Use this to read what is on the user's screen when they ask 'what does this screen say', 'read this error', 'what text is on screen', or to extract text from an app, terminal, website, or document.")
def ocr_screen_tool(region: list[int] = None, detail: bool = False) -> str:
    return ocr_screen(tuple(region) if region else None, detail)


@mcp.tool(name="ocr_image", description="Read (OCR) text from an image file. Pass the full path to the image. Use this when the user shares a screenshot, photo, scan, or document image and asks what it says or to extract the text from it.")
def ocr_image_tool(path: str, detail: bool = False) -> str:
    return ocr_image(path, detail)


@mcp.tool(name="search_youtube", description="Search YouTube for videos matching the query. Returns JSON array of results with title, url, duration, and thumbnail.")
def search_youtube(query: str, max_results: int = 5) -> str:
    try:
        import yt_dlp
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "force_generic_extractor": False,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            results = []
            for entry in info.get("entries", []):
                results.append({
                    "title": entry.get("title", ""),
                    "url": f"https://youtube.com/watch?v={entry.get('id', '')}",
                    "duration": entry.get("duration", 0),
                    "thumbnail": entry.get("thumbnail", ""),
                })
            return json.dumps({"success": True, "results": results})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool(name="play_youtube", description="Get direct audio stream URL for a YouTube video. Returns the stream URL and title for playback.")
def play_youtube(video_url: str, title: str = "") -> str:
    try:
        import yt_dlp
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestaudio/best",
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            stream_url = info.get("url", "")
            if not stream_url:
                return json.dumps({"success": False, "error": "No audio stream found"})
            return json.dumps({
                "success": True,
                "stream_url": stream_url,
                "title": title or info.get("title", ""),
                "video_url": video_url,
                "duration": info.get("duration", 0),
            })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool(name="list_playlists", description="List all music playlists. Returns id and name for each playlist.")
def list_playlists() -> str:
    try:
        from yakult_mybini.memory.playlist_manager import playlist_manager
        items = playlist_manager.list()
        return json.dumps({"success": True, "playlists": [p.to_dict() for p in items]})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool(name="create_playlist", description="Create a new music playlist with the given name.")
def create_playlist(name: str) -> str:
    try:
        from yakult_mybini.memory.playlist_manager import playlist_manager
        playlist = playlist_manager.create(name)
        if not playlist:
            return json.dumps({"success": False, "error": "Name is empty or invalid"})
        return json.dumps({"success": True, "id": playlist.id, "name": playlist.name})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool(name="delete_playlist", description="Delete a music playlist by its id.")
def delete_playlist(playlist_id: str) -> str:
    try:
        from yakult_mybini.memory.playlist_manager import playlist_manager
        ok = playlist_manager.delete(playlist_id)
        return json.dumps({"success": ok})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool(name="rename_playlist", description="Rename a music playlist by its id.")
def rename_playlist(playlist_id: str, name: str) -> str:
    try:
        from yakult_mybini.memory.playlist_manager import playlist_manager
        playlist = playlist_manager.rename(playlist_id, name)
        if not playlist:
            return json.dumps({"success": False, "error": "Playlist not found or invalid name"})
        return json.dumps({"success": True, "playlist": playlist.to_dict()})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool(name="add_to_playlist", description="Add a song to a playlist. Pass the playlist_id, the YouTube video_url, and optionally a title. Returns the added song.")
def add_to_playlist(playlist_id: str, video_url: str, title: str = "") -> str:
    try:
        from yakult_mybini.memory.playlist_manager import playlist_manager, PlaylistSong
        playlist = playlist_manager.get(playlist_id)
        if not playlist:
            return json.dumps({"success": False, "error": "Playlist not found"})
        if not title:
            import yt_dlp
            ydl_opts = {"quiet": True, "no_warnings": True, "extract_flat": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                title = info.get("title", "")
                duration = info.get("duration", 0)
                thumbnail = info.get("thumbnail", "")
        else:
            duration = 0
            thumbnail = ""
        song = PlaylistSong(title=title, video_url=video_url, duration=duration, thumbnail=thumbnail)
        added = playlist_manager.add_song(playlist_id, song)
        return json.dumps({"success": True, "song": added.to_dict() if added else None})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool(name="remove_from_playlist", description="Remove a song from a playlist by its song id.")
def remove_from_playlist(playlist_id: str, song_id: str) -> str:
    try:
        from yakult_mybini.memory.playlist_manager import playlist_manager
        ok = playlist_manager.remove_song(playlist_id, song_id)
        return json.dumps({"success": ok})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool(name="download_to_playlist", description="Download a YouTube video's audio locally and add it to a playlist. Pass playlist_id, video_url, and optionally title. Returns the added song with a local file path.")
def download_to_playlist(playlist_id: str, video_url: str, title: str = "") -> str:
    try:
        from yakult_mybini.memory.playlist_manager import playlist_manager, PlaylistSong
        from yakult_mybini.agentic.downloader import download_audio
        playlist = playlist_manager.get(playlist_id)
        if not playlist:
            return json.dumps({"success": False, "error": "Playlist not found"})
        if not title:
            import yt_dlp
            ydl_opts = {"quiet": True, "no_warnings": True, "extract_flat": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                title = info.get("title", "")
        file_path = download_audio(video_url, title)
        song = PlaylistSong(title=title, video_url=video_url, file_path=file_path)
        added = playlist_manager.add_song(playlist_id, song)
        return json.dumps({"success": True, "song": added.to_dict() if added else None})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool(name="play_playlist", description="Play a playlist. Pass playlist_id, optionally shuffle=True for random order, and optionally song_title to start from a specific song. Returns the song being played.")
def play_playlist(playlist_id: str, shuffle: bool = False, song_title: str = "") -> str:
    try:
        from yakult_mybini.memory.playlist_manager import playlist_manager
        from yakult_mybini.mcpp.music_player_manager import music_player_manager
        from yakult_mybini.agentic.downloader import to_http_url
        from yakult_mybini.config_manager.utils import read_yaml
        playlist = playlist_manager.get(playlist_id)
        if not playlist or not playlist.songs:
            return json.dumps({"success": False, "error": "Playlist empty or not found"})
        songs = [s.to_dict() for s in playlist.songs]
        music_player_manager.set_queue(songs, shuffle=shuffle)
        if song_title:
            idx = next(
                (i for i, s in enumerate(songs) if song_title.lower() in s["title"].lower()),
                None,
            )
            if idx is not None:
                music_player_manager.seek_queue(idx)
        first = music_player_manager.next_queued() or songs[0]
        try:
            cfg = read_yaml("conf.yaml")
            sc = cfg.get("system_config", {}) or {}
            base = f"http://{sc.get('host') or '127.0.0.1'}:{sc.get('port') or 12393}"
        except Exception:
            base = "http://127.0.0.1:12393"
        stream_url = to_http_url(music_player_manager.resolve_stream_url(first) or "", base)
        return json.dumps({
            "success": True,
            "playlist_id": playlist.id,
            "title": first.get("title", ""),
            "stream_url": stream_url,
            "video_url": first.get("video_url", ""),
            "shuffle": shuffle,
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool(name="play_mv", description="Play the Music Video (MV) of a YouTube video in a separate window. Pass the video_url. Returns the video stream URL and title.")
def play_mv(video_url: str, title: str = "") -> str:
    try:
        import yt_dlp
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "best[ext=mp4]/best",
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
        stream_url = info.get("url", "")
        if not stream_url:
            return json.dumps({"success": False, "error": "No video stream found"})
        return json.dumps({
            "success": True,
            "stream_url": stream_url,
            "title": title or info.get("title", "Unknown"),
            "video_url": video_url,
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool(name="weather", description="Get current weather (temperature, feels like, humidity, wind, description) for a city or your current location. Pass an optional city name (e.g. 'Jakarta'); if omitted, geolocates from your IP. Uses free open-meteo, no API key needed.")
def weather_tool(city: str = "") -> str:
    try:
        import httpx

        with httpx.Client(timeout=15.0) as client:
            if city:
                geo = client.get(
                    "https://geocoding-api.open-meteo.com/v1/search",
                    params={"name": city, "count": 1},
                ).json()
                results = geo.get("results") or []
                if not results:
                    return json.dumps({"success": False, "error": f"City not found: {city}"})
                lat, lon, name = results[0]["latitude"], results[0]["longitude"], results[0]["name"]
            else:
                loc = client.get("http://ip-api.com/json/").json()
                lat, lon = loc.get("lat"), loc.get("lon")
                name = f"{loc.get('city', '')}, {loc.get('country', '')}".strip(" ,") or "your location"

            data = client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
                },
            ).json()["current"]

        weather_codes = {
            0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Fog", 48: "Depositing rime fog",
            51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle",
            61: "Slight rain", 63: "Rain", 65: "Heavy rain",
            71: "Slight snow", 73: "Snow", 75: "Heavy snow",
            80: "Slight showers", 81: "Showers", 82: "Violent showers",
            95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
        }
        return json.dumps({
            "success": True,
            "location": name,
            "temperature_c": data.get("temperature_2m"),
            "feels_like_c": data.get("apparent_temperature"),
            "humidity_pct": data.get("relative_humidity_2m"),
            "wind_speed_kmh": round(data.get("wind_speed_10m", 0), 1),
            "condition": weather_codes.get(data.get("weather_code"), "Unknown"),
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool(name="system_status", description="Report system health: CPU usage %, RAM used/total, disk used/total, and battery level/plugged status if present. Use when the user asks about battery, CPU, RAM, disk, or system performance.")
def system_status() -> str:
    try:
        import psutil

        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        battery_info = {}
        try:
            battery = psutil.sensors_battery()
            if battery:
                battery_info = {
                    "percent": battery.percent,
                    "plugged_in": battery.power_plugged,
                }
        except Exception:
            battery_info = {}

        return json.dumps({
            "success": True,
            "cpu_percent": cpu,
            "ram_used_gb": round(mem.used / (1024 ** 3), 2),
            "ram_total_gb": round(mem.total / (1024 ** 3), 2),
            "ram_percent": mem.percent,
            "disk_used_gb": round(disk.used / (1024 ** 3), 2),
            "disk_total_gb": round(disk.total / (1024 ** 3), 2),
            "disk_percent": disk.percent,
            "battery": battery_info,
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool(name="take_screenshot", description="Capture the full screen (or an optional region [left, top, width, height]) and save it as a PNG file. Returns the absolute path to the saved image. Use this when the user asks you to take/save a screenshot.")
def take_screenshot(region: list[int] = None, path: str = "") -> str:
    try:
        import mss
        from PIL import Image

        save_dir = os.environ.get("SCREENSHOT_DIR", os.path.join(os.getcwd(), "screenshots"))
        os.makedirs(save_dir, exist_ok=True)
        if not path:
            path = os.path.join(save_dir, f"screenshot_{int(time.time())}.png")

        with mss.mss() as sct:
            if region:
                left, top, width, height = region
                box = {"left": left, "top": top, "width": width, "height": height}
            else:
                mon = sct.monitors[1]
                box = {"left": mon["left"], "top": mon["top"],
                       "width": mon["width"], "height": mon["height"]}
            shot = sct.grab(box)

        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        img.save(path)
        return json.dumps({"success": True, "path": os.path.abspath(path)})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool(name="wikipedia_search", description="Fetch a concise summary of a topic from Wikipedia. Returns the page title, summary text, and a link. Use for factual questions about known topics, history, science, people, places.")
def wikipedia_search(query: str, sentences: int = 3) -> str:
    try:
        import httpx

        with httpx.Client(timeout=15.0, headers={"User-Agent": "yakult-mybini/1.0"}) as client:
            from urllib.parse import quote
            resp = client.get("https://en.wikipedia.org/api/rest_v1/page/summary/" + quote(query.replace(" ", "_")))
            if resp.status_code == 404:
                search = client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={"action": "query", "list": "search", "srsearch": query, "format": "json", "srlimit": 1},
                ).json()
                hits = search.get("query", {}).get("search", [])
                if not hits:
                    return json.dumps({"success": False, "error": f"No Wikipedia article found for: {query}"})
                return json.dumps({
                    "success": True,
                    "suggested_title": hits[0]["title"],
                    "snippet": hits[0].get("snippet", "").replace("<span class=\"searchmatch\">", "").replace("</span>", ""),
                    "url": "https://en.wikipedia.org/wiki/" + hits[0]["title"].replace(" ", "_"),
                })
            data = resp.json()
            extract = data.get("extract", "")
            summary = " ".join(extract.split(". ")[:sentences]) + ("." if extract and not extract.endswith(".") else "")
            return json.dumps({
                "success": True,
                "title": data.get("title", query),
                "summary": summary,
                "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
            })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def main():
    mcp.run()


@mcp.tool(name="template_tool", description="Template tool description.")
def template_tool(arg: str) -> str:
    """
    Template tool implementation.
    """
    return f"Hasil dari {arg}"


if __name__ == "__main__":
    main()
