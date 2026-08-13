import sys
import subprocess
from typing import Optional, Dict, Any, List, Tuple

if sys.platform == "linux":
    try:
        import gi

        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi

        AT_SPI_AVAILABLE = True
    except Exception:
        AT_SPI_AVAILABLE = False
else:
    AT_SPI_AVAILABLE = False


class AccessibilityController:
    def __init__(self):
        self._initialized = False
        self._desktop = None
        if AT_SPI_AVAILABLE:
            self._init_atspi()

    def _init_atspi(self):
        try:
            Atspi.init()
            self._desktop = Atspi.get_desktop(0)
            self._initialized = True
        except Exception as e:
            print(f"AT-SPI init failed: {e}")
            self._initialized = False

    def find_elements(
        self,
        name: str = None,
        role: str = None,
        app_name: str = None,
        text: str = None,
        max_results: int = 10,
    ) -> List[Dict[str, Any]]:
        if not self._initialized:
            return [{"error": "AT-SPI not available"}]

        results = []

        def traverse(node, depth=0):
            if len(results) >= max_results:
                return
            try:
                if node.get_role_name() in ["defunct", ""]:
                    return

                match = True
                if name and name.lower() not in (node.get_name() or "").lower():
                    match = False
                if role and role.lower() != node.get_role_name().lower():
                    match = False
                if text and text.lower() not in (node.get_name() or "").lower():
                    match = False
                if app_name:
                    app = self._get_application_name(node)
                    if app_name.lower() not in app.lower():
                        match = False

                if match:
                    coords = self._get_element_coords(node)
                    if coords:
                        results.append(
                            {
                                "name": node.get_name() or "",
                                "role": node.get_role_name(),
                                "description": node.get_description(0) or "",
                                "x": coords[0],
                                "y": coords[1],
                                "width": coords[2],
                                "height": coords[3],
                                "application": self._get_application_name(node),
                                "states": [
                                    str(s) for s in node.get_state_set().get_states()
                                ]
                                if node.get_state_set()
                                else [],
                            }
                        )

                for i in range(node.get_child_count()):
                    traverse(node.get_child_at_index(i), depth + 1)
            except Exception:
                pass

        try:
            for i in range(self._desktop.get_child_count()):
                traverse(self._desktop.get_child_at_index(i))
        except Exception as e:
            return [{"error": f"Traversal failed: {e}"}]

        return results if results else [{"error": "No matching elements found"}]

    def _get_element_coords(self, node) -> Optional[Tuple[int, int, int, int]]:
        try:
            x, y, w, h = node.get_extents(Atspi.CoordType.SCREEN)
            if w > 0 and h > 0:
                return (x, y, w, h)
        except Exception:
            pass
        return None

    def _get_application_name(self, node) -> str:
        try:
            app = node.get_application()
            if app:
                return app.get_name() or ""
        except Exception:
            pass
        return ""

    def click_element(self, x: int, y: int) -> Dict[str, Any]:
        try:
            subprocess.run(
                ["xdotool", "mousemove", str(x), str(y)], check=True, timeout=2
            )
            subprocess.run(["xdotool", "click", "1"], check=True, timeout=2)
            return {"success": True, "message": f"Clicked at ({x}, {y})"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def click_element_by_name(
        self, name: str, role: str = None, app_name: str = None
    ) -> Dict[str, Any]:
        elements = self.find_elements(
            name=name, role=role, app_name=app_name, max_results=1
        )
        if not elements or "error" in elements[0]:
            return {
                "success": False,
                "error": elements[0].get("error", "Element not found"),
            }

        el = elements[0]
        center_x = el["x"] + el["width"] // 2
        center_y = el["y"] + el["height"] // 2
        return self.click_element(center_x, center_y)

    def get_active_window_info(self) -> Dict[str, Any]:
        try:
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if result.returncode == 0:
                return {"window_name": result.stdout.strip()}
        except Exception:
            pass
        return {"window_name": "unknown"}

    def list_interactive_elements(
        self, app_name: str = None, max_results: int = 20
    ) -> List[Dict[str, Any]]:
        interactive_roles = [
            "push button",
            "toggle button",
            "check box",
            "radio button",
            "menu item",
            "link",
            "slider",
            "spin button",
            "combo box",
            "text entry",
            "password text",
            "search box",
        ]

        results = []
        for role in interactive_roles:
            elements = self.find_elements(
                role=role, app_name=app_name, max_results=max_results
            )
            for el in elements:
                if "error" not in el:
                    results.append(el)
            if len(results) >= max_results:
                break
        return results[:max_results]


_accessibility_controller = None


def get_accessibility_controller() -> AccessibilityController:
    global _accessibility_controller
    if _accessibility_controller is None:
        _accessibility_controller = AccessibilityController()
    return _accessibility_controller
