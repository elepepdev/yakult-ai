import sys
import os
import subprocess
import time
from typing import Optional, Dict, Any, List, Tuple

try:
    import Xlib
    import Xlib.display
    import Xlib.X
    import Xlib.Xatom
    import Xlib.XK
    import Xlib.ext.xtest
    XLIB_AVAILABLE = True
except ImportError:
    XLIB_AVAILABLE = False


class X11Controller:
    def __init__(self):
        self._display = None
        self._root = None
        self._utf8_atom = None
        if XLIB_AVAILABLE:
            self._init_x11()

    def _init_x11(self):
        try:
            self._display = Xlib.display.Display()
            self._root = self._display.screen().root
            self._utf8_atom = self._display.intern_atom('UTF8_STRING')
        except Exception as e:
            print(f"X11 init failed: {e}")
            self._display = None
            self._root = None
            self._utf8_atom = None

    def _get_window_name(self, window) -> str:
        """Get window name trying multiple properties"""
        if not self._display:
            return ""
        try:
            atoms_to_try = [
                ("_NET_WM_NAME", self._utf8_atom),
                ("WM_NAME", self._utf8_atom),
                ("WM_NAME", Xlib.Xatom.STRING),
                ("_NET_WM_VISIBLE_NAME", self._utf8_atom),
                ("_NET_WM_ICON_NAME", self._utf8_atom),
                ("WM_ICON_NAME", Xlib.Xatom.STRING),
            ]
            for atom_name, atom_type in atoms_to_try:
                try:
                    atom = self._display.intern_atom(atom_name)
                    prop = window.get_full_property(atom, atom_type)
                    if prop and prop.value:
                        if atom_type == self._utf8_atom:
                            return prop.value.decode('utf-8', errors='ignore')
                        else:
                            return prop.value.decode('latin-1', errors='ignore')
                except:
                    pass
        except:
            pass
        return ""

    def find_windows(self, name_contains: str = None, class_contains: str = None) -> List[Dict[str, Any]]:
        """Find windows matching name or class"""
        if not self._display or not self._root:
            return [{"error": "X11 not available"}]
        
        results = []
        
        def traverse(window, depth=0):
            if depth > 10:
                return
            try:
                # Get window name
                name = self._get_window_name(window)
                
                # Get window class
                wm_class = ""
                try:
                    class_prop = window.get_full_property(
                        self._display.intern_atom("WM_CLASS"),
                        Xlib.Xatom.STRING
                    )
                    if class_prop:
                        wm_class = class_prop.value.decode('utf-8', errors='ignore')
                except:
                    pass
                
                # Get geometry
                try:
                    geom = window.get_geometry()
                    x, y, w, h = geom.x, geom.y, geom.width, geom.height
                except:
                    x, y, w, h = 0, 0, 0, 0
                
                # Check match
                match = True
                if name_contains and name_contains.lower() not in name.lower():
                    match = False
                if class_contains and class_contains.lower() not in wm_class.lower():
                    match = False
                
                if match and w > 0 and h > 0:
                    results.append({
                        "id": window.id,
                        "name": name,
                        "class": wm_class,
                        "x": x,
                        "y": y,
                        "width": w,
                        "height": h,
                    })
                
                # Traverse children
                try:
                    children = window.query_tree().children
                    for child in children:
                        traverse(child, depth + 1)
                except:
                    pass
                    
            except Exception:
                pass
        
        traverse(self._root)
        return results

    def get_window_geometry(self, window_id: int) -> Optional[Dict[str, int]]:
        """Get geometry of a window"""
        if not self._display:
            return None
        try:
            window = self._display.create_resource_object('window', window_id)
            geom = window.get_geometry()
            # Get absolute position
            translated = window.translate_coords(self._root, 0, 0)
            return {
                "x": translated.x,
                "y": translated.y,
                "width": geom.width,
                "height": geom.height,
            }
        except Exception:
            return None

    def _x_screen_size(self) -> tuple:
        """Return current X screen (width, height) in pixels."""
        if not self._display:
            return (0, 0)
        try:
            screen = self._display.screen()
            return (screen.width_in_pixels, screen.height_in_pixels)
        except Exception:
            return (0, 0)

    def _scale_coords(self, x: int, y: int, image_width: int = None, image_height: int = None) -> tuple:
        """Map AI-supplied image-space coordinates to real X screen coords.

        Returns clamped ints in screen-pixel space.
        """
        screen_w, screen_h = self._x_screen_size()
        ix = int(x)
        iy = int(y)

        if image_width and image_height and image_width > 0 and image_height > 0:
            if (image_width, image_height) != (screen_w, screen_h):
                sx = screen_w / image_width
                sy = screen_h / image_height
                ix = int(round(ix * sx))
                iy = int(round(iy * sy))

        ix = max(0, min(ix, screen_w - 1))
        iy = max(0, min(iy, screen_h - 1))
        return (ix, iy)

    def click_at(
        self,
        x: int = None,
        y: int = None,
        image_width: int = None,
        image_height: int = None,
        grid_cell: str = None,
        grid_rows: int = 6,
        grid_cols: int = 8,
        cell_x: float = 0.5,
        cell_y: float = 0.5,
    ) -> Dict[str, Any]:
        """Click at absolute screen coordinates (with optional image-space scaling)."""
        if not self._display:
            return {"success": False, "error": "X11 not available"}
        try:
            if grid_cell:
                if not image_width or not image_height:
                    return {"success": False, "error": "grid_cell requires image_width and image_height"}
                from .grid_overlay import cell_to_pixel
                coords = cell_to_pixel(grid_cell, image_width, image_height, grid_rows, grid_cols, cell_x=cell_x, cell_y=cell_y)
                if coords is None:
                    return {"success": False, "error": f"Invalid grid_cell: {grid_cell}"}
                x, y = coords
            elif x is None or y is None:
                return {"success": False, "error": "x and y (or grid_cell) required"}
            cx, cy = self._scale_coords(x, y, image_width, image_height)
            # Move mouse
            self._display.warp_pointer(cx, cy)
            self._display.sync()

            # Click (button 1 = left click)
            Xlib.ext.xtest.fake_input(self._display, Xlib.X.ButtonPress, 1)
            self._display.sync()
            time.sleep(0.05)
            Xlib.ext.xtest.fake_input(self._display, Xlib.X.ButtonRelease, 1)
            self._display.sync()

            return {"success": True, "message": f"Clicked at ({cx}, {cy})"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def click_window_center(self, window_id: int) -> Dict[str, Any]:
        """Click center of a window"""
        geom = self.get_window_geometry(window_id)
        if not geom:
            return {"success": False, "error": "Could not get window geometry"}
        
        center_x = geom["x"] + geom["width"] // 2
        center_y = geom["y"] + geom["height"] // 2
        return self.click_at(center_x, center_y)

    def click_window_relative(self, window_id: int, rel_x: float, rel_y: float) -> Dict[str, Any]:
        """Click at relative position within window (0.0-1.0)"""
        geom = self.get_window_geometry(window_id)
        if not geom:
            return {"success": False, "error": "Could not get window geometry"}
        
        x = geom["x"] + int(geom["width"] * rel_x)
        y = geom["y"] + int(geom["height"] * rel_y)
        return self.click_at(x, y)

    def type_text(self, text: str) -> Dict[str, Any]:
        """Type text using XTest"""
        if not self._display:
            return {"success": False, "error": "X11 not available"}
        try:
            for char in text:
                keysym = Xlib.XK.string_to_keysym(char)
                if keysym == Xlib.XK.NoSymbol:
                    continue
                keycode = self._display.keysym_to_keycode(keysym)
                Xlib.ext.xtest.fake_input(self._display, Xlib.X.KeyPress, keycode)
                self._display.sync()
                time.sleep(0.01)
                Xlib.ext.xtest.fake_input(self._display, Xlib.X.KeyRelease, keycode)
                self._display.sync()
                time.sleep(0.01)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def press_key(self, key: str) -> Dict[str, Any]:
        """Press a key (e.g., 'Return', 'Escape', 'Tab', 'a', 'ctrl')"""
        if not self._display:
            return {"success": False, "error": "X11 not available"}
        try:
            # Handle modifier keys
            key_lower = key.lower()
            modifiers = []
            
            if key_lower.startswith('ctrl') or key_lower.startswith('control'):
                modifiers.append(Xlib.X.ControlMask)
                key = key_lower.replace('ctrl', '').replace('control', '').replace('+', '').strip()
            if key_lower.startswith('alt'):
                modifiers.append(Xlib.X.Mod1Mask)
                key = key_lower.replace('alt', '').replace('+', '').strip()
            if key_lower.startswith('shift'):
                modifiers.append(Xlib.X.ShiftMask)
                key = key_lower.replace('shift', '').replace('+', '').strip()
            if key_lower.startswith('super') or key_lower.startswith('meta'):
                modifiers.append(Xlib.X.Mod4Mask)
                key = key_lower.replace('super', '').replace('meta', '').replace('+', '').strip()
            
            if not key:
                return {"success": False, "error": "No key specified"}
            
            keysym = Xlib.XK.string_to_keysym(key)
            if keysym == Xlib.XK.NoSymbol:
                # Try common aliases
                key_aliases = {
                    'enter': 'Return', 'esc': 'Escape', 'escape': 'Escape',
                    'space': 'space', 'tab': 'Tab', 'backspace': 'BackSpace',
                    'delete': 'Delete', 'up': 'Up', 'down': 'Down',
                    'left': 'Left', 'right': 'Right', 'home': 'Home',
                    'end': 'End', 'pageup': 'Page_Up', 'pagedown': 'Page_Down',
                }
                key = key_aliases.get(key_lower, key)
                keysym = Xlib.XK.string_to_keysym(key)
            
            if keysym == Xlib.XK.NoSymbol:
                return {"success": False, "error": f"Unknown key: {key}"}
            
            keycode = self._display.keysym_to_keycode(keysym)
            
            # Press modifiers
            for mod in modifiers:
                mod_keysym = {
                    Xlib.X.ControlMask: Xlib.XK.Control_L,
                    Xlib.X.Mod1Mask: Xlib.XK.Alt_L,
                    Xlib.X.ShiftMask: Xlib.XK.Shift_L,
                    Xlib.X.Mod4Mask: Xlib.XK.Super_L,
                }.get(mod)
                if mod_keysym:
                    mod_keycode = self._display.keysym_to_keycode(mod_keysym)
                    Xlib.ext.xtest.fake_input(self._display, Xlib.X.KeyPress, mod_keycode)
            
            # Press main key
            Xlib.ext.xtest.fake_input(self._display, Xlib.X.KeyPress, keycode)
            self._display.sync()
            time.sleep(0.05)
            Xlib.ext.xtest.fake_input(self._display, Xlib.X.KeyRelease, keycode)
            self._display.sync()
            
            # Release modifiers
            for mod in reversed(modifiers):
                mod_keysym = {
                    Xlib.X.ControlMask: Xlib.XK.Control_L,
                    Xlib.X.Mod1Mask: Xlib.XK.Alt_L,
                    Xlib.X.ShiftMask: Xlib.XK.Shift_L,
                    Xlib.X.Mod4Mask: Xlib.XK.Super_L,
                }.get(mod)
                if mod_keysym:
                    mod_keycode = self._display.keysym_to_keycode(mod_keysym)
                    Xlib.ext.xtest.fake_input(self._display, Xlib.X.KeyRelease, mod_keycode)
            
            self._display.sync()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def hotkey(self, *keys) -> Dict[str, Any]:
        """Press key combination like ('ctrl', 'c')"""
        if not self._display:
            return {"success": False, "error": "X11 not available"}
        try:
            keycodes = []
            for key in keys:
                key_lower = key.lower()
                keysym = Xlib.XK.string_to_keysym(key_lower)
                if keysym == Xlib.XK.NoSymbol:
                    key_aliases = {
                        'ctrl': 'Control_L', 'control': 'Control_L',
                        'alt': 'Alt_L', 'shift': 'Shift_L',
                        'super': 'Super_L', 'meta': 'Meta_L',
                        'enter': 'Return', 'esc': 'Escape',
                        'space': 'space', 'tab': 'Tab',
                    }
                    key = key_aliases.get(key_lower, key)
                    keysym = Xlib.XK.string_to_keysym(key)
                if keysym != Xlib.XK.NoSymbol:
                    keycodes.append(self._display.keysym_to_keycode(keysym))
            
            # Press all keys
            for kc in keycodes:
                Xlib.ext.xtest.fake_input(self._display, Xlib.X.KeyPress, kc)
            self._display.sync()
            time.sleep(0.05)
            # Release all keys
            for kc in reversed(keycodes):
                Xlib.ext.xtest.fake_input(self._display, Xlib.X.KeyRelease, kc)
            self._display.sync()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_active_window(self) -> Dict[str, Any]:
        """Get currently active window"""
        if not self._display:
            return {"error": "X11 not available"}
        try:
            atom = self._display.intern_atom("_NET_ACTIVE_WINDOW")
            prop = self._root.get_full_property(atom, Xlib.Xatom.WINDOW)
            if prop and prop.value:
                window_id = prop.value[0]
                window = self._display.create_resource_object('window', window_id)
                # Get name
                name = self._get_window_name(window)
                geom = self.get_window_geometry(window_id)
                return {
                    "id": window_id,
                    "name": name,
                    "geometry": geom
                }
        except Exception as e:
            return {"error": str(e)}
        return {"error": "No active window"}

    def focus_window(self, window_id: int) -> Dict[str, Any]:
        """Focus/raise a window"""
        if not self._display:
            return {"success": False, "error": "X11 not available"}
        try:
            window = self._display.create_resource_object('window', window_id)
            # Set input focus
            self._display.set_input_focus(window, Xlib.X.RevertToParent, Xlib.X.CurrentTime)
            # Raise window using configure
            window.configure(stack_mode=Xlib.X.Above)
            self._display.sync()
            return {"success": True, "message": f"Focused window {window_id}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def close_window(self, window_id: int) -> Dict[str, Any]:
        """Send close request to a window (equivalent to clicking X button)"""
        if not self._display:
            return {"success": False, "error": "X11 not available"}
        try:
            window = self._display.create_resource_object('window', window_id)
            atom = self._display.intern_atom("_NET_CLOSE_WINDOW")
            wm_protocols = self._display.intern_atom("WM_PROTOCOLS")
            wm_delete_window = self._display.intern_atom("WM_DELETE_WINDOW")

            # Try _NET_CLOSE_WINDOW first (modern EWMH compliant way)
            try:
                client_msg = Xlib.protocol.event.ClientMessage(
                    window=window,
                    client_type=atom,
                    data=(32, [Xlib.X.CurrentTime, 0, 0, 0, 0])
                )
                mask = Xlib.X.SubstructureRedirectMask | Xlib.X.SubstructureNotifyMask
                self._root.send_event(client_msg, event_mask=mask)
                self._display.sync()
                return {"success": True, "message": f"Sent close request to window {window_id}"}
            except Exception:
                pass

            # Fallback: send WM_DELETE_WINDOW protocol
            try:
                client_msg = Xlib.protocol.event.ClientMessage(
                    window=window,
                    client_type=wm_protocols,
                    data=(32, [wm_delete_window, Xlib.X.CurrentTime, 0, 0, 0])
                )
                self._root.send_event(client_msg, event_mask=mask)
                self._display.sync()
                return {"success": True, "message": f"Sent WM_DELETE_WINDOW to window {window_id}"}
            except Exception:
                pass

            return {"success": False, "error": "Failed to send close request"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_visible_windows(self) -> List[Dict[str, Any]]:
        """List all visible/non-minimal windows"""
        return self.find_windows()


_x11_controller = None

def get_x11_controller() -> X11Controller:
    global _x11_controller
    if _x11_controller is None:
        _x11_controller = X11Controller()
    return _x11_controller