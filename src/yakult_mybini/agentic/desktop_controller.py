import os
import subprocess
import sys
import psutil
import time
from typing import Optional, Dict, Any
from pathlib import Path
from loguru import logger

from .accessibility import get_accessibility_controller
from .grid_overlay import cell_to_pixel


def _get_pyautogui():
    import pyautogui
    return pyautogui


class ApplicationLauncher:
    SPECIAL_APPS = {}

    COMMON_APPS = {
        # Browsers
        "firefox": ["firefox", "firefox-esr", "mozilla-firefox"],
        "chrome": ["google-chrome", "google-chrome-stable", "chromium"],
        "brave": ["brave", "brave-browser"],
        "edge": ["microsoft-edge", "microsoft-edge-stable"],

        # Editors
        "vscode": ["code"],
        "vim": ["vim", "gvim", "nvim"],
        "nano": ["nano"],
        "notepad": ["notepad", "notepadqq", "gedit", "kate", "mousepad"],
        "sublime": ["subl", "sublime_text", "sublime-text"],
        "intellij": ["idea", "intellij-idea-ultimate", "intellij-idea-ce"],
        "pycharm": ["pycharm", "pycharm-professional", "pycharm-community"],

        # Terminals
        "terminal": ["gnome-terminal", "konsole", "xterm", "alacritty", "kitty", "terminator", "tilix", "urxvt", "st"],
        "alacritty": ["alacritty"],
        "kitty": ["kitty"],
        "terminator": ["terminator"],
        "konsole": ["konsole"],

        # Media & Entertainment
        "vlc": ["vlc"],
        "mpv": ["mpv"],
        "spotify": ["spotify"],
        "rhythmbox": ["rhythmbox"],
        "clementine": ["clementine"],

        # Games
        "steam": ["steam"],
        "lutris": ["lutris"],
        "heroic": ["heroic", "heroic-games-launcher"],
        "minecraft": ["minecraft-launcher", "prismlauncher"],
        "prism": ["prismlauncher"],
        "itch": ["itch"],
        "bottles": ["bottles"],
        "gamescope": ["gamescope"],
        "tlauncher": ["tlauncher", "TLauncher"],

        # Communication
        "slack": ["slack"],
        "discord": ["discord", "discord-ptb", "discord-canary"],
        "telegram": ["telegram-desktop"],
        "whatsapp": ["whatsapp-nativefier", "whatsapp-for-linux"],
        "zoom": ["zoom"],
        "teams": ["teams", "teams-for-linux"],

        # File managers
        "filemanager": ["nautilus", "nemo", "thunar", "dolphin", "pcmanfm", "caja"],
        "nautilus": ["nautilus"],
        "dolphin": ["dolphin"],
        "thunar": ["thunar"],

        # Development
        "docker": ["docker", "docker-desktop"],
        "postman": ["postman"],
        "insomnia": ["insomnia"],
        "gitkraken": ["gitkraken"],
        "sourcetree": ["sourcetree"],
        "obsidian": ["obsidian"],
        "notion": ["notion", "notion-snap"],

        # Graphics & Design
        "gimp": ["gimp"],
        "inkscape": ["inkscape"],
        "blender": ["blender"],
        "krita": ["krita"],
        "figma": ["figma-linux"],

        # System
        "calculator": ["gnome-calculator", "kcalc", "qalculate-gtk"],
        "calendar": ["gnome-calendar", "korganizer", "evolution"],
        "settings": ["gnome-control-center", "systemsettings", "xfce4-settings-manager"],
        "system monitor": ["gnome-system-monitor", "ksysguard", "htop", "btop"],
    }

    def _get_commands_for(self, app_name: str) -> list[str]:
        app_name = app_name.lower()
        if app_name in self.COMMON_APPS:
            return self.COMMON_APPS[app_name]
        return [app_name]

    def is_app_running(self, app_name: str) -> bool:
        app_name = app_name.lower()
        commands = self._get_commands_for(app_name)
        for proc in psutil.process_iter(['name']):
            try:
                pname = proc.info['name'].lower()
                for cmd in commands:
                    if cmd.lower() in pname or pname in cmd.lower():
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def _focus_window(self, app_name: str) -> bool:
        if sys.platform != "linux":
            return False
        try:
            import shutil
            if not shutil.which("xdotool"):
                return False
            time.sleep(0.5)
            commands = self._get_commands_for(app_name)
            for cmd in commands:
                for flag in ["--name", "--class"]:
                    try:
                        result = subprocess.run(
                            ["xdotool", "search", flag, cmd, "windowactivate"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            timeout=3,
                        )
                        if result.returncode == 0:
                            return True
                    except Exception:
                        continue
        except Exception:
            pass
        return False

    def open_app(self, app_name: str, params: Optional[Dict[str, Any]] = None) -> bool:
        app_name = app_name.lower()
        params = params or {}
        if self.is_app_running(app_name):
            if self._focus_window(app_name):
                return True
            # Process exists but no visible window — launch a new instance
        if app_name in self.SPECIAL_APPS:
            return self._try_launch_custom(self.SPECIAL_APPS[app_name], params)
        if app_name in self.COMMON_APPS:
            for cmd in self.COMMON_APPS[app_name]:
                if self._try_launch(cmd, params):
                    return True
            return False
        else:
            return self._try_launch(app_name, params)

    def focus_app(self, app_name: str) -> bool:
        return self._focus_window(app_name.lower())

    def _try_launch(self, command: str, params: Dict[str, Any]) -> bool:
        try:
            cmd_list = [command]
            if "url" in params:
                cmd_list.append(params["url"])
            if "args" in params:
                if isinstance(params["args"], list):
                    cmd_list.extend(params["args"])
                else:
                    cmd_list.append(str(params["args"]))

            env = os.environ.copy()
            if sys.platform == "linux" and "DISPLAY" not in env:
                env["DISPLAY"] = ":0"
                print(f"Warning: DISPLAY not set, defaulting to :0 for {command}")

            proc = subprocess.Popen(
                cmd_list,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                env=env,
            )

            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._focus_window(command)
                return True

            if proc.returncode != 0:
                stderr_output = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
                print(f"Launch failed (exit {proc.returncode}): {command} - {stderr_output}")
                return False

            self._focus_window(command)
            return True
        except FileNotFoundError:
            return False
        except Exception as e:
            print(f"Error launching {command}: {e}")
            return False

    def _try_launch_custom(self, cmd_list: list, params: Dict[str, Any]) -> bool:
        try:
            if "args" in params:
                cmd_list = cmd_list + (params["args"] if isinstance(params["args"], list) else [str(params["args"])])
            subprocess.Popen(cmd_list, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            print(f"Error launching custom command: {e}")
            return False

class InputController:
    def __init__(self):
        self._pyautogui = None
        self._init_error = None
        try:
            self._pyautogui = _get_pyautogui()
            self._pyautogui.PAUSE = 0.1
            self._pyautogui.FAILSAFE = True
        except Exception as e:
            self._init_error = str(e)

    def _check_init(self) -> Optional[str]:
        if self._init_error:
            return f"Input controller not available (no display?): {self._init_error}"
        return None

    def _scale_coords(
        self,
        x: int,
        y: int,
        image_width: Optional[int] = None,
        image_height: Optional[int] = None,
    ) -> tuple:
        """Map AI-supplied image coordinates to real screen coordinates.

        Logic:
        - If image_width/height match the screen size (or are missing), treat
          x/y as absolute screen pixels.
        - Otherwise, scale proportionally to the real screen resolution.

        Coordinates are clamped to the screen bounds.
        """
        try:
            screen_w, screen_h = self._pyautogui.size()
        except Exception:
            return (int(x), int(y))

        x = int(x)
        y = int(y)

        if image_width and image_height and image_width > 0 and image_height > 0:
            if (image_width, image_height) != (screen_w, screen_h):
                sx = screen_w / image_width
                sy = screen_h / image_height
                x = int(round(x * sx))
                y = int(round(y * sy))
                logger.debug(
                    f"Scaled AI coords ({x}/{sx}, {y}/{sy}) from image "
                    f"({image_width}x{image_height}) to screen ({screen_w}x{screen_h})"
                )

        x = max(0, min(x, screen_w - 1))
        y = max(0, min(y, screen_h - 1))
        return (x, y)

    def type_text(
        self,
        text: str,
        click_x: Optional[int] = None,
        click_y: Optional[int] = None,
        image_width: Optional[int] = None,
        image_height: Optional[int] = None,
        grid_cell: Optional[str] = None,
        grid_rows: int = 6,
        grid_cols: int = 8,
        cell_x: float = 0.5,
        cell_y: float = 0.5,
        interval: float = 0.05,
    ) -> bool:
        err = self._check_init()
        if err:
            print(err)
            return False
        try:
            if grid_cell:
                if not image_width or not image_height:
                    print("grid_cell requires image_width and image_height")
                    return False
                coords = cell_to_pixel(grid_cell, image_width, image_height, grid_rows, grid_cols, cell_x=cell_x, cell_y=cell_y)
                if coords is None:
                    print(f"Invalid grid_cell: {grid_cell}")
                    return False
                cx_img, cy_img = coords
                cx, cy = self._scale_coords(cx_img, cy_img, image_width, image_height)
            elif click_x is not None and click_y is not None:
                cx, cy = self._scale_coords(click_x, click_y, image_width, image_height)
            else:
                return False
            self._pyautogui.click(cx, cy)
            time.sleep(0.2)

            if sys.platform == "linux":
                import shutil as _shutil
                if _shutil.which("xdotool"):
                    result = subprocess.run(
                        ["xdotool", "getactivewindow"],
                        capture_output=True, text=True, timeout=3,
                    )
                    if result.returncode == 0:
                        window_id = result.stdout.strip()
                        subprocess.run(
                            ["xdotool", "type", "--window", window_id, text],
                            timeout=30,
                        )
                        return True

            self._pyautogui.write(text, interval=interval)
            return True
        except Exception as e:
            print(f"Error typing text: {e}")
            return False

    def press_key(self, key: str) -> bool:
        err = self._check_init()
        if err:
            print(err)
            return False
        try:
            self._pyautogui.press(key)
            return True
        except Exception as e:
            print(f"Error pressing key: {e}")
            return False

    def hotkey(self, *keys) -> bool:
        err = self._check_init()
        if err:
            print(err)
            return False
        try:
            self._pyautogui.hotkey(*keys)
            return True
        except Exception as e:
            print(f"Error pressing hotkey: {e}")
            return False

    def click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        image_width: Optional[int] = None,
        image_height: Optional[int] = None,
        grid_cell: Optional[str] = None,
        grid_rows: int = 6,
        grid_cols: int = 8,
        cell_x: float = 0.5,
        cell_y: float = 0.5,
    ) -> bool:
        err = self._check_init()
        if err:
            print(err)
            return False
        try:
            if grid_cell:
                if not image_width or not image_height:
                    logger.error("grid_cell requires image_width and image_height")
                    return False
                coords = cell_to_pixel(grid_cell, image_width, image_height, grid_rows, grid_cols, cell_x=cell_x, cell_y=cell_y)
                if coords is None:
                    logger.error(f"Invalid grid_cell: {grid_cell}")
                    return False
                cx_img, cy_img = coords
                cx, cy = self._scale_coords(cx_img, cy_img, image_width, image_height)
                logger.info(
                    f"grid_cell={grid_cell} cell_xy=({cell_x:.2f},{cell_y:.2f}) "
                    f"img=({image_width}x{image_height}) "
                    f"grid={grid_cols}x{grid_rows} "
                    f"img_coords=({cx_img},{cy_img}) → screen_coords=({cx},{cy})"
                )
                self._pyautogui.click(cx, cy)
            elif x is not None and y is not None:
                cx, cy = self._scale_coords(x, y, image_width, image_height)
                logger.info(f"click raw x,y=({x},{y}) img={image_width}x{image_height} → screen=({cx},{cy})")
                self._pyautogui.click(cx, cy)
            else:
                self._pyautogui.click()
            return True
        except Exception as e:
            logger.error(f"Error clicking: {e}")
            return False

    def get_screen_size(self) -> tuple:
        err = self._check_init()
        if err:
            print(err)
            return (0, 0)
        return self._pyautogui.size()

class CommandRunner:
    SAFE_COMMANDS = ["ls", "pwd", "cd", "cat", "echo", "mkdir", "touch", "git", "npm", "python", "pip", "code"]
    DESTRUCTIVE_COMMANDS = ["rm", "rmdir", "del", "format", "dd", "mkfs", "shutdown", "reboot", "poweroff"]

    def __init__(self, safety_level: str = "medium"):
        self.safety_level = safety_level

    def run_command(self, command: str, check_safety: bool = True) -> Dict[str, Any]:
        if check_safety and not self._is_safe(command):
            return {"success": False, "error": f"Command blocked by safety level: {self.safety_level}", "output": None}
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timeout (30s)", "output": None}
        except Exception as e:
            return {"success": False, "error": str(e), "output": None}

    def run_sudo_command(self, command: str) -> Dict[str, Any]:
        sudo_pw = os.environ.get("SUDO_PASSWORD", "")
        if not sudo_pw:
            return {"success": False, "error": "SUDO_PASSWORD not configured (set sudo_password in conf.yaml)"}
        try:
            full_cmd = f"echo '{sudo_pw}' | sudo -S {command}"
            result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True, timeout=60)
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timeout (60s)", "output": None}
        except Exception as e:
            return {"success": False, "error": str(e), "output": None}

    def _is_safe(self, command: str) -> bool:
        if self.safety_level == "low":
            return True
        for dangerous in self.DESTRUCTIVE_COMMANDS:
            if dangerous in command.lower():
                return False
        return True


class FileController:
    def read_file(self, filepath: str) -> Dict[str, Any]:
        try:
            path = Path(filepath).expanduser().resolve()
            if not path.exists():
                return {"success": False, "error": f"File not found: {filepath}"}
            if not path.is_file():
                return {"success": False, "error": f"Not a file: {filepath}"}
            content = path.read_text(encoding="utf-8")
            return {"success": True, "content": content, "path": str(path), "size": len(content)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def write_file(self, filepath: str, content: str, append: bool = False) -> Dict[str, Any]:
        try:
            path = Path(filepath).expanduser().resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            mode = "a" if append else "w"
            with open(path, mode, encoding="utf-8") as f:
                f.write(content)
            return {"success": True, "message": f"{'Appended to' if append else 'Wrote'} {path}", "path": str(path)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_file(self, filepath: str, force: bool = False) -> Dict[str, Any]:
        try:
            path = Path(filepath).expanduser().resolve()
            if not path.exists():
                return {"success": False, "error": f"Path not found: {filepath}"}
            if path.is_file():
                path.unlink()
                return {"success": True, "message": f"Deleted file: {path}"}
            elif path.is_dir():
                if force:
                    import shutil
                    shutil.rmtree(path)
                    return {"success": True, "message": f"Deleted directory: {path}"}
                else:
                    path.rmdir()
                    return {"success": True, "message": f"Deleted empty directory: {path}"}
            else:
                return {"success": False, "error": f"Cannot delete: {path}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_directory(self, filepath: str = ".") -> Dict[str, Any]:
        try:
            path = Path(filepath).expanduser().resolve()
            if not path.exists():
                return {"success": False, "error": f"Directory not found: {filepath}"}
            if not path.is_dir():
                return {"success": False, "error": f"Not a directory: {filepath}"}
            entries = []
            for entry in path.iterdir():
                entry_type = "dir" if entry.is_dir() else "file"
                entries.append({"name": entry.name, "type": entry_type, "size": entry.stat().st_size if entry.is_file() else 0})
            return {"success": True, "path": str(path), "entries": sorted(entries, key=lambda x: (x["type"] != "dir", x["name"]))}
        except Exception as e:
            return {"success": False, "error": str(e)}


class DesktopController:
    def __init__(self, safety_level: str = "medium"):
        self.safety_level = safety_level
        self.app_launcher = ApplicationLauncher()
        self.input_controller = InputController()
        self.command_runner = CommandRunner(safety_level=self.safety_level)
        self.file_controller = FileController()

    def _screen_size_info(self) -> Dict[str, Any]:
        """Return physical screen dimensions for coordinate calibration."""
        sw, sh = self.input_controller.get_screen_size()
        if (sw, sh) == (0, 0):
            try:
                from .x11_controller import get_x11_controller
                x11 = get_x11_controller()
                sw, sh = x11._x_screen_size()
            except Exception:
                pass
        if (sw, sh) == (0, 0):
            return {"success": False, "error": "Could not determine screen size"}
        return {
            "success": True,
            "screen_width": sw,
            "screen_height": sh,
            "message": "Use these dimensions with image_width/image_height from the shared screen to map coordinates accurately.",
        }

    def _screen_dims_or_zero(self) -> tuple:
        sw, sh = self.input_controller.get_screen_size()
        if (sw, sh) == (0, 0):
            try:
                from .x11_controller import get_x11_controller
                x11 = get_x11_controller()
                sw, sh = x11._x_screen_size()
            except Exception:
                pass
        return (sw, sh)

    def _click_with_map(
        self,
        do_click,
        image_width=None,
        image_height=None,
    ) -> tuple:
        """Run a click and (best-effort) compute the resulting screen coordinates.

        Returns (success, mapped_coords_or_None).
        """
        try:
            do_click()
        except Exception as e:
            logger.error(f"Click action failed: {e}")
            return (False, None)
        # If we were given an image size that differs from screen size, we
        # can't know the AI's exact coords here without re-running the call —
        # the mapping already happened inside the click handler. Return None
        # so callers don't get a misleading value.
        return (True, None)

    def execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        action_type = action.get("type")
        target = action.get("target")
        params = action.get("params", {})

        if action_type == "open_app":
            success = self.app_launcher.open_app(target, params)
            return {"success": success, "message": f"Opened {target}" if success else f"Failed to open {target}"}
        elif action_type == "focus_app":
            success = self.app_launcher.focus_app(target)
            return {"success": success, "message": f"Focused {target}" if success else f"Could not find window for {target}"}
        elif action_type == "close_app":
            closed = False
            errors = []

            # Strategy 1: X11 close window by ID (safest — targets specific window, not active window)
            try:
                from .x11_controller import get_x11_controller
                x11 = get_x11_controller()
                if x11._display:
                    windows = x11.find_windows(name_contains=target)
                    if not windows:
                        commands = self.app_launcher._get_commands_for(target)
                        for cmd in commands:
                            windows = x11.find_windows(name_contains=cmd)
                            if windows:
                                break
                    for win in windows:
                        r = x11.close_window(win["id"])
                        if r.get("success"):
                            closed = True
            except Exception as e:
                errors.append(f"X11: {e}")

            # Strategy 2: SIGTERM via psutil (targets specific PID — safe, won't close wrong app)
            if not closed:
                try:
                    commands = self.app_launcher._get_commands_for(target)
                    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                        try:
                            pname = proc.info['name'] or ""
                            pcmdline = " ".join(proc.info['cmdline'] or [])
                            for cmd in commands:
                                if cmd.lower() in pname.lower() or cmd.lower() in pcmdline.lower():
                                    # Skip our own process
                                    if proc.info['pid'] == os.getpid():
                                        continue
                                    proc.terminate()
                                    closed = True
                                    break
                        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                            errors.append(str(e))
                            continue
                except Exception as e:
                    errors.append(f"SIGTERM: {e}")

            if not closed:
                return {"success": False, "error": f"Could not close {target}", "details": errors}
            return {"success": True, "message": f"Closing {target}"}
        elif action_type == "type_text":
            text = params.get("text", target)
            click_x = params.get("click_x")
            click_y = params.get("click_y")
            grid_cell = params.get("grid_cell")
            if not grid_cell and (click_x is None or click_y is None):
                return {"success": False, "error": "click_x and click_y (or grid_cell) are required for type_text. The image_width and image_height come from the [Shared screen image dimensions...] note."}
            image_width = params.get("image_width")
            image_height = params.get("image_height")
            grid_rows = params.get("grid_rows", 6)
            grid_cols = params.get("grid_cols", 8)
            cell_x = params.get("cell_x", 0.5)
            cell_y = params.get("cell_y", 0.5)
            success, mapped = self._click_with_map(
                lambda: self.input_controller.type_text(
                    text, click_x, click_y, image_width, image_height,
                    grid_cell=grid_cell, grid_rows=grid_rows, grid_cols=grid_cols,
                    cell_x=cell_x, cell_y=cell_y,
                ),
                image_width,
                image_height,
            )
            return {
                "success": success,
                "message": "Text typed" if success else "Failed to type",
                "clicked_at": mapped,
            }
        elif action_type == "press_key":
            success = self.input_controller.press_key(target)
            return {"success": success, "message": f"Pressed {target}" if success else f"Failed to press {target}"}
        elif action_type == "hotkey":
            keys = params.get("keys", [])
            success = self.input_controller.hotkey(*keys)
            return {"success": success, "message": "Hotkey pressed" if success else "Failed to press hotkey"}
        elif action_type == "click":
            x = params.get("x")
            y = params.get("y")
            grid_cell = params.get("grid_cell")
            image_width = params.get("image_width")
            image_height = params.get("image_height")
            grid_rows = params.get("grid_rows", 6)
            grid_cols = params.get("grid_cols", 8)
            cell_x = params.get("cell_x", 0.5)
            cell_y = params.get("cell_y", 0.5)
            success, mapped = self._click_with_map(
                lambda: self.input_controller.click(
                    x, y, image_width, image_height,
                    grid_cell=grid_cell, grid_rows=grid_rows, grid_cols=grid_cols,
                    cell_x=cell_x, cell_y=cell_y,
                ),
                image_width,
                image_height,
            )
            return {
                "success": success,
                "message": "Clicked" if success else "Failed to click",
                "clicked_at": mapped,
            }
        elif action_type == "screen_size":
            return self._screen_size_info()
        elif action_type == "run_command":
            return self.command_runner.run_command(target)
        elif action_type == "run_sudo_command":
            return self.command_runner.run_sudo_command(target)
        elif action_type == "read_file":
            return self.file_controller.read_file(params.get("path", target))
        elif action_type == "write_file":
            return self.file_controller.write_file(params.get("path", target), params.get("content", ""), params.get("append", False))
        elif action_type == "delete_file":
            return self.file_controller.delete_file(params.get("path", target), params.get("force", False))
        elif action_type == "list_directory":
            return self.file_controller.list_directory(params.get("path", target or "."))
        elif action_type == "find_element":
            a11y = get_accessibility_controller()
            return a11y.find_elements(
                name=params.get("name"),
                role=params.get("role"),
                app_name=params.get("app_name"),
                text=params.get("text"),
                max_results=params.get("max_results", 10)
            )
        elif action_type == "click_element":
            a11y = get_accessibility_controller()
            return a11y.click_element_by_name(
                name=params.get("name"),
                role=params.get("role"),
                app_name=params.get("app_name")
            )
        elif action_type == "list_clickable_elements":
            a11y = get_accessibility_controller()
            return a11y.list_interactive_elements(
                app_name=params.get("app_name"),
                max_results=params.get("max_results", 20)
            )
        elif action_type == "get_active_window":
            a11y = get_accessibility_controller()
            return a11y.get_active_window_info()
        elif action_type == "find_window":
            x11 = get_x11_controller()
            return x11.find_windows(
                name_contains=params.get("name"),
                class_contains=params.get("class")
            )
        elif action_type == "click_window":
            x11 = get_x11_controller()
            window_id = params.get("window_id")
            if not window_id:
                return {"success": False, "error": "window_id required"}
            click_type = params.get("click_type", "center")
            if click_type == "center":
                return x11.click_window_center(window_id)
            elif click_type == "relative":
                rel_x = params.get("rel_x", 0.5)
                rel_y = params.get("rel_y", 0.5)
                return x11.click_window_relative(window_id, rel_x, rel_y)
            else:
                return {"success": False, "error": f"Unknown click_type: {click_type}"}
        elif action_type == "x11_click":
            x11 = get_x11_controller()
            x = params.get("x")
            y = params.get("y")
            grid_cell = params.get("grid_cell")
            image_width = params.get("image_width")
            image_height = params.get("image_height")
            if grid_cell is None and (x is None or y is None):
                return {"success": False, "error": "x and y (or grid_cell) required"}
            return x11.click_at(
                x, y,
                image_width=image_width, image_height=image_height,
                grid_cell=grid_cell,
                grid_rows=params.get("grid_rows", 6),
                grid_cols=params.get("grid_cols", 8),
                cell_x=params.get("cell_x", 0.5),
                cell_y=params.get("cell_y", 0.5),
            )
        elif action_type == "x11_type":
            x11 = get_x11_controller()
            text = params.get("text", target)
            if not text:
                return {"success": False, "error": "text required"}
            return x11.type_text(text)
        elif action_type == "x11_key":
            x11 = get_x11_controller()
            key = target or params.get("key")
            if not key:
                return {"success": False, "error": "key required"}
            return x11.press_key(key)
        elif action_type == "x11_hotkey":
            x11 = get_x11_controller()
            keys = params.get("keys", [])
            if not keys:
                return {"success": False, "error": "keys required"}
            return x11.hotkey(*keys)
        elif action_type == "x11_active_window":
            x11 = get_x11_controller()
            return x11.get_active_window()
        elif action_type == "focus_window":
            x11 = get_x11_controller()
            window_id = params.get("window_id")
            if not window_id:
                return {"success": False, "error": "window_id required"}
            return x11.focus_window(window_id)
        elif action_type == "list_windows":
            x11 = get_x11_controller()
            name_contains = params.get("name")
            class_contains = params.get("class")
            if name_contains or class_contains:
                return x11.find_windows(name_contains=name_contains, class_contains=class_contains)
            else:
                return x11.list_visible_windows()
        else:
            return {"success": False, "error": f"Unknown action type: {action_type}"}
