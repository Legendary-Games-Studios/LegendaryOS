import os
import sys
import importlib.util
import zipfile
import zipimport
import types
import json
import shutil
import urllib.request
import threading
import hashlib
from datetime import datetime

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Line, Rotate, Rectangle
from kivy.animation import Animation
from kivy.uix.slider import Slider
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.textinput import TextInput
from kivy.uix.image import Image
from kivy.core.text import LabelBase

# ================= GLOBAL EMOJI FIX =================
if os.name == "nt":
    emoji_font_path = "C:\\Windows\\Fonts\\seguiemj.ttf"
    if os.path.exists(emoji_font_path):
        LabelBase.register(name="Roboto", fn_regular=emoji_font_path)

# ================= THEME CONFIGURATIONS =================
THEMES = {
    "dark": {
        "bg_color": [0.1, 0.1, 0.1, 1],
        "text_color": [1, 1, 1, 1],
        "accent_color": [0.2, 0.2, 0.2, 1]
    },
    "light": {
        "bg_color": [0.9, 0.9, 0.9, 1],
        "text_color": [0, 0, 0, 1],
        "accent_color": [0.8, 0.8, 0.8, 1]
    },
    "blue": {
        "bg_color": [0.05, 0.15, 0.3, 1],
        "text_color": [0.9, 0.95, 1, 1],
        "accent_color": [0.1, 0.3, 0.6, 1]
    }
}

# ================= RISK SCANNER =================
def scan_risk(path):
    risky = ["exec(", "eval(", "subprocess", "os.system", "os.popen", "__import__", "ctypes"]
    try:
        if path.lower().endswith(".zip"):
            if not zipfile.is_zipfile(path): return []
            with zipfile.ZipFile(path, 'r') as archive:
                if "main.py" in archive.namelist():
                    with archive.open("main.py") as f:
                        code = f.read().decode('utf-8', errors='ignore')
                else: return []
        else:
            with open(path, "r", errors="ignore") as f: code = f.read()
        return [r for r in risky if r in code]
    except:
        return []

# ================= ICON RESOLUTION =================
# Apps can declare an icon in three ways:
#   - a plain emoji/text string (rendered as a Label, default behavior)
#   - an "http://" or "https://" URL (downloaded once and cached locally)
#   - (zip apps only) the filename of an image embedded inside the app's
#     own zip archive, e.g. "icon.png" (extracted once and cached locally)
#
# .py apps expose this via a module-level APP_ICON.
# zip apps expose this via manifest.json's "icon" key, or APP_ICON in main.py.
# Apps can also set/override their icon at runtime via OSAPI.set_icon().

ICON_CACHE_DIR = "LegendaryOS/root/storage/.icons/"


def _cache_ext(name_hint, default=".png"):
    ext = os.path.splitext(name_hint.split("?")[0])[1]
    return ext if ext else default


def download_icon(url, cache_id):
    try:
        os.makedirs(ICON_CACHE_DIR, exist_ok=True)
        dest = os.path.join(ICON_CACHE_DIR, f"{cache_id}{_cache_ext(url)}")
        req = urllib.request.Request(url, headers={"User-Agent": "LegendaryOS/1.0"})
        with urllib.request.urlopen(req, timeout=6) as resp, open(dest, "wb") as f:
            f.write(resp.read())
        return dest
    except Exception:
        return None


def extract_icon_from_zip(zip_path, inner_name, cache_id):
    try:
        with zipfile.ZipFile(zip_path, 'r') as archive:
            if inner_name not in archive.namelist():
                return None
            os.makedirs(ICON_CACHE_DIR, exist_ok=True)
            dest = os.path.join(ICON_CACHE_DIR, f"{cache_id}{_cache_ext(inner_name)}")
            with archive.open(inner_name) as src, open(dest, "wb") as out:
                out.write(src.read())
            return dest
    except Exception:
        return None


def resolve_icon(source, cache_id, zip_path=None):
    """Resolve an APP_ICON / manifest 'icon' value into something renderable:
    returns either a short text/emoji string, or a local image file path."""
    if not source or not isinstance(source, str):
        return "📦"
    if source.startswith("http://") or source.startswith("https://"):
        cached = download_icon(source, cache_id)
        return cached if cached else "📦"
    if zip_path:
        extracted = extract_icon_from_zip(zip_path, source, cache_id)
        if extracted:
            return extracted
    return source

# ================= AUTO-UPDATE =================
# Checks a GitHub repo's /latest folder for a newer LegendaryOS.py on every
# boot. Pulls the file straight from raw.githubusercontent.com (no API call,
# so no rate limit) and hashes it directly against the running file's bytes.

UPDATE_REPO = "Legendary-Games-Studios/LegendaryOS"
UPDATE_BRANCH = "main"
UPDATE_PATH = "latest/LegendaryOS.py"
UPDATE_RAW_URL = f"https://raw.githubusercontent.com/{UPDATE_REPO}/{UPDATE_BRANCH}/{UPDATE_PATH}"
UPDATE_STAGING_DIR = "LegendaryOS/root/storage/.updates/"


def check_for_update():
    """Downloads the raw file and hashes it against the running file's own
    bytes. Returns the new file's bytes if they differ, else None."""
    try:
        req = urllib.request.Request(UPDATE_RAW_URL, headers={"User-Agent": "LegendaryOS-Updater"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            remote_bytes = resp.read()

        self_path = os.path.abspath(__file__)
        with open(self_path, "rb") as f:
            local_bytes = f.read()

        if hashlib.sha256(remote_bytes).hexdigest() != hashlib.sha256(local_bytes).hexdigest():
            return remote_bytes
        return None
    except Exception:
        return None

# ================= SPINNER =================
class Spinner(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas:
            Color(1, 1, 1)
            self.rot = Rotate()
            self.line = Line(circle=(0, 0, 60, 0, 300), width=2)
        self.bind(pos=self.update, size=self.update)
        anim = Animation(angle=360, duration=1) + Animation(angle=0, duration=0)
        anim.repeat = True
        anim.start(self.rot)

    def update(self, *args):
        self.rot.origin = self.center
        self.line.circle = (self.center_x, self.center_y, 60, 0, 300)

# ================= BOOT SCREEN =================
class BootScreen(BoxLayout):
    def __init__(self, done, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.add_widget(Label(text="LegendaryOS v1.4.0-pre", font_size=32))
        self.add_widget(Spinner())
        Clock.schedule_once(lambda dt: done(), 2.8)

# ================= WINDOW CONTAINER SYSTEM =================
class WindowFrame(BoxLayout):
    def __init__(self, app_name, content, close_cb, minimize_cb, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        
        self.title_bar = BoxLayout(size_hint_y=None, height=40, spacing=5)
        with self.title_bar.canvas.before:
            Color(0.15, 0.15, 0.15, 1)
            self.bg_rect = Rectangle(pos=self.title_bar.pos, size=self.title_bar.size)
        self.title_bar.bind(pos=self._update_bg, size=self._update_bg)
        
        self.title_label = Label(text=f"  {app_name}", halign="left", valign="middle")
        self.title_label.bind(size=self.title_label.setter('text_size'))
        
        min_btn = Button(text="—", size_hint_x=None, width=40)
        max_btn = Button(text="🗖", size_hint_x=None, width=40)
        close_btn = Button(text="✕", size_hint_x=None, width=40, background_color=[0.8, 0.2, 0.2, 1])
        
        min_btn.bind(on_press=lambda x: minimize_cb())
        close_btn.bind(on_press=lambda x: close_cb())
        
        self.title_bar.add_widget(self.title_label)
        self.title_bar.add_widget(min_btn)
        self.title_bar.add_widget(max_btn)
        self.title_bar.add_widget(close_btn)
        
        self.add_widget(self.title_bar)
        self.add_widget(content)

    def _update_bg(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

# ================= HOME SCREEN TILE =================
class AppTile(ButtonBehavior, BoxLayout):
    """A tappable home-screen tile: icon (image or emoji) stacked over a name label."""
    pass

# ================= APP LOADER =================
class AppLoader:
    def __init__(self):
        self.apps = []
        self.load_errors = [] 

    def load(self):
        self.apps = []
        self.load_errors = []
        bases = ["LegendaryOS/root/system-apps", "LegendaryOS/root/user-apps"]
        
        for base in bases:
            if not os.path.exists(base): os.makedirs(base, exist_ok=True)
            for file in os.listdir(base):
                path = os.path.join(base, file)
                
                if file.endswith(".py"):
                    try:
                        spec = importlib.util.spec_from_file_location(file[:-3], path)
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        app_id = file[:-3]
                        raw_icon = getattr(module, "APP_ICON", "📦")
                        icon = resolve_icon(raw_icon, app_id)
                        self.apps.append({
                            "id": app_id, "name": getattr(module, "APP_NAME", app_id),
                            "icon": icon, "run": getattr(module, "run"), "path": path
                        })
                    except Exception as e:
                        self.load_errors.append(f"App '{file}' failed to initialize:\n{str(e)}")

                elif file.endswith(".zip"):
                    try:
                        if not zipfile.is_zipfile(path): continue
                        abs_zip_path = os.path.abspath(path)
                        importer = zipimport.zipimporter(abs_zip_path)
                        
                        app_id = file[:-4]
                        name, version, icon_source = app_id, "1.0", None
                        with zipfile.ZipFile(path, 'r') as archive:
                            file_list = archive.namelist()
                            if "main.py" not in file_list: continue
                            
                            if "manifest.json" in file_list:
                                with archive.open("manifest.json") as m:
                                    try:
                                        m_data = json.loads(m.read().decode('utf-8'))
                                        name = m_data.get("name", name)
                                        version = m_data.get("version", version)
                                        # Icon may be a URL, or a filename of an image
                                        # embedded elsewhere in this same zip.
                                        icon_source = m_data.get("icon", icon_source)
                                    except: pass
                                    
                            with archive.open("main.py") as f:
                                code_content = f.read().decode('utf-8')

                        # Inject path properly for dependencies lookup
                        if abs_zip_path not in sys.path:
                            sys.path.insert(0, abs_zip_path)
                            
                        module = types.ModuleType(app_id)
                        module.__dict__['__file__'] = abs_zip_path
                        module.__dict__['__loader__'] = importer
                        exec(code_content, module.__dict__)

                        if icon_source is None:
                            icon_source = getattr(module, "APP_ICON", "📦")
                        icon = resolve_icon(icon_source, app_id, zip_path=abs_zip_path)

                        self.apps.append({
                            "id": app_id, 
                            "name": name, 
                            "icon": icon,
                            "run": getattr(module, "run"), 
                            "path": path, 
                            "version": version
                        })
                    except Exception as e:
                        self.load_errors.append(f"Zip App '{file}' crashed:\n{str(e)}")

# ================= SDK / OSAPI BRIDGE =================
class OSAPI:
    def __init__(self, os_ref, app_id):
        self.os = os_ref
        self.app_id = app_id

    def save(self, key, value):
        if self.app_id not in self.os.app_memory: self.os.app_memory[self.app_id] = {"data": {}}
        self.os.app_memory[self.app_id]["data"][key] = value

    def load(self, key):
        if self.app_id not in self.os.app_memory: return None
        return self.os.app_memory[self.app_id]["data"].get(key)

    def notify(self, text):
        self.os.show_notification(text)

    def copy_to_clipboard(self, text):
        self.os.clipboard = text

    def paste_from_clipboard(self):
        return self.os.clipboard

    def set_wallpaper_color(self, r, g, b, a=1):
        if hasattr(self.os, 'bg_color') and self.os.bg_color is not None:
            self.os.bg_color.rgba = [r, g, b, a]

    def set_setting(self, key, value):
        self.os.settings[key] = value
        self.os.save_settings()

    def set_icon(self, source):
        """Set/override this app's home-screen icon at runtime.
        `source` may be an emoji/text, an http(s) URL, or (zip apps only)
        the filename of an image embedded inside this app's own zip."""
        self.os.set_app_icon(self.app_id, source)

# ================= MAIN OS LAYER =================
class LegendaryOS(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.loader = AppLoader()
        self.loader.load()

        self.processes = {}
        self.app_memory = {}
        self.active_app = None
        self.clipboard = ""
        
        self.trash_dir = "LegendaryOS/root/storage/.Trash/"
        os.makedirs(self.trash_dir, exist_ok=True)

        self.settings_path = "LegendaryOS/root/system-apps/AppData/settings/settings.json"
        self.settings = {}
        self.load_settings()
        self._apply_icon_overrides()

        # Canvas Setup
        self.desktop = BoxLayout(orientation="vertical")
        self.taskbar = BoxLayout(size_hint=(1, 0.08))

        with self.desktop.canvas.before:
            self.bg_color = Color(0, 0, 0, 1)
            self.bg_rect = Rectangle(pos=self.desktop.pos, size=self.desktop.size)
            self.bg_image = Rectangle(pos=self.desktop.pos, size=self.desktop.size, texture=None)
            
        self.desktop.bind(pos=self._update_bg_layout, size=self._update_bg_layout)

        # Notification Bar Setup
        self.notification_bar = Label(text="", size_hint_y=None, height=0)
        with self.notification_bar.canvas.before:
            Color(0.1, 0.6, 1, 0.9)
            self.notif_rect = Rectangle(pos=self.notification_bar.pos, size=self.notification_bar.size)
        self.notification_bar.bind(pos=self._update_notif, size=self._update_notif)

        self.add_widget(self.notification_bar)
        self.add_widget(self.desktop)
        self.add_widget(self.taskbar)
        self.start_boot()

    def _apply_icon_overrides(self):
        """Re-apply any icons that were set at runtime via OSAPI.set_icon()
        on previous runs, once apps have been (re)loaded."""
        overrides = self.settings.get("icon_overrides", {})
        if not overrides:
            return
        for app in self.loader.apps:
            if app['id'] in overrides:
                zip_path = os.path.abspath(app['path']) if app['path'].lower().endswith('.zip') else None
                app['icon'] = resolve_icon(overrides[app['id']], app['id'], zip_path=zip_path)

    def set_app_icon(self, app_id, source):
        zip_path = None
        for app in self.loader.apps:
            if app['id'] == app_id:
                if app['path'].lower().endswith('.zip'):
                    zip_path = os.path.abspath(app['path'])
                break
        icon = resolve_icon(source, app_id, zip_path=zip_path)
        for app in self.loader.apps:
            if app['id'] == app_id:
                app['icon'] = icon
                break
        self.settings.setdefault("icon_overrides", {})[app_id] = source
        self.save_settings()
        if hasattr(self, 'grid') and self.active_app is None:
            self.render_home()

    def safety_delete(self, target_path):
        if os.path.exists(target_path):
            dest = os.path.join(self.trash_dir, os.path.basename(target_path))
            shutil.move(target_path, dest)
            self.show_notification(f"Moved to Recycle Bin: {os.path.basename(target_path)}")

    def show_notification(self, text):
        if not self.settings.get("notifications_enabled", True):
            return
        self.notification_bar.text = text
        self.notification_bar.height = 40
        Clock.unschedule(self._hide_notification)
        Clock.schedule_once(self._hide_notification, 3.5)

    def _hide_notification(self, dt):
        self.notification_bar.text = ""
        self.notification_bar.height = 0

    def _update_notif(self, instance, value):
        self.notif_rect.pos = instance.pos
        self.notif_rect.size = instance.size

    def load_settings(self):
        try:
            os.makedirs(os.path.dirname(self.settings_path), exist_ok=True)
            if os.path.exists(self.settings_path):
                with open(self.settings_path, "r") as f: self.settings = json.load(f)
        except: pass

    def save_settings(self):
        try:
            with open(self.settings_path, "w") as f: json.dump(self.settings, f, indent=4)
        except: pass

    def apply_theme(self, name):
        if name in THEMES:
            self.settings["theme"] = name
            
            # Flush out background overrides so core theme updates render instantly
            self.settings.pop("wallpaper_color", None)
            self.settings.pop("wallpaper_img", None)
            self.bg_image.texture = None
            
            self.save_settings()
            if hasattr(self, 'bg_color') and self.bg_color is not None:
                self.bg_color.rgba = THEMES[name]["bg_color"]

    def apply_wallpaper_image(self, path):
        if os.path.exists(path):
            self.settings["wallpaper_img"] = path
            self.save_settings()
            try:
                self.bg_image.texture = Image(source=path).texture
            except: pass

    def _update_bg_layout(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size
        self.bg_image.pos = instance.pos
        self.bg_image.size = instance.size

    def start_boot(self):
        self.desktop.clear_widgets()
        self._booted = False
        threading.Thread(target=self._background_update_check, daemon=True).start()
        self.desktop.add_widget(BootScreen(self.go_home))

    def _background_update_check(self):
        remote_bytes = check_for_update()
        if remote_bytes:
            pending_path = self._save_pending_update(remote_bytes)
            if pending_path:
                Clock.schedule_once(lambda dt: self._offer_update(pending_path), 0)

    def _save_pending_update(self, remote_bytes):
        try:
            os.makedirs(UPDATE_STAGING_DIR, exist_ok=True)
            pending_path = os.path.join(UPDATE_STAGING_DIR, "LegendaryOS_pending.py")
            with open(pending_path, "wb") as f:
                f.write(remote_bytes)
            return pending_path
        except Exception:
            return None

    def _offer_update(self, pending_path):
        # Don't interrupt the boot animation; wait until the home screen is up.
        if not self._booted:
            Clock.schedule_once(lambda dt: self._offer_update(pending_path), 0.5)
            return
        self._show_update_popup(pending_path)

    def _show_update_popup(self, pending_path):
        box = BoxLayout(orientation="vertical", spacing=10, padding=10)
        box.add_widget(Label(text="A new version of LegendaryOS is available.\nUpdate now?"))
        btn_row = BoxLayout(size_hint_y=None, height=45, spacing=10)
        yes_btn = Button(text="Yes")
        cancel_btn = Button(text="Cancel")
        btn_row.add_widget(yes_btn)
        btn_row.add_widget(cancel_btn)
        box.add_widget(btn_row)

        popup = Popup(title="Update Available", content=box, size_hint=(0.75, 0.4), auto_dismiss=False)
        yes_btn.bind(on_release=lambda x: [popup.dismiss(), self._apply_update(pending_path)])
        cancel_btn.bind(on_release=lambda x: [popup.dismiss(), self._cancel_update(pending_path)])
        popup.open()

    def _cancel_update(self, pending_path):
        # Don't just discard it in place - move it to the Recycle Bin, same
        # as any other file removal in the OS.
        self.safety_delete(pending_path)

    def _apply_update(self, pending_path):
        self.desktop.clear_widgets()
        self.taskbar.clear_widgets()
        self.desktop.add_widget(Label(text="Installing update...", font_size=24))
        threading.Thread(target=self._install_update, args=(pending_path,), daemon=True).start()

    def _install_update(self, pending_path):
        try:
            with open(pending_path, "rb") as f:
                new_code = f.read()

            # Sanity-check it's valid Python before touching the running file.
            self_path = os.path.abspath(__file__)
            compile(new_code, self_path, "exec")

            tmp_path = self_path + ".new"
            with open(tmp_path, "wb") as f:
                f.write(new_code)
            os.replace(tmp_path, self_path)

            try:
                os.remove(pending_path)
            except Exception:
                pass

            Clock.schedule_once(lambda dt: self._restart_after_update(), 0)
        except Exception as e:
            err = str(e)
            Clock.schedule_once(lambda dt: self.show_notification(f"Update failed: {err}"), 0)
            Clock.schedule_once(lambda dt: self.go_home(), 0)

    def _restart_after_update(self):
        self.desktop.clear_widgets()
        self.desktop.add_widget(Label(text="LegendaryOS will now restart...", font_size=26))
        Clock.schedule_once(lambda dt: self._relaunch_process(), 2.0)

    def _relaunch_process(self):
        python = sys.executable
        os.execv(python, [python, os.path.abspath(__file__)] + sys.argv[1:])

    def go_home(self):
        self._booted = True
        self.render_home()
        self.update_taskbar()
        
        if "wallpaper_color" in self.settings:
            c = self.settings["wallpaper_color"]
            if hasattr(self, 'bg_color') and self.bg_color is not None:
                self.bg_color.rgba = c
        else:
            theme = self.settings.get("theme", "blue")
            self.apply_theme(theme)

        if "wallpaper_img" in self.settings:
            self.apply_wallpaper_image(self.settings["wallpaper_img"])

    def render_home(self):
        self.desktop.clear_widgets()
        
        search_box = BoxLayout(size_hint_y=None, height=45, padding=5)
        search_input = TextInput(hint_text="Search apps...", multiline=False)
        search_box.add_widget(search_input)
        self.desktop.add_widget(search_box)
        
        scroll = ScrollView()
        cols = max(1, int(Window.width // 130))
        self.grid = GridLayout(cols=cols, size_hint_y=None, spacing=10, padding=10)
        self.grid.bind(minimum_height=self.grid.setter("height"))
        
        search_input.bind(text=self._filter_home_view)
        
        self.populate_apps(self.loader.apps)
        scroll.add_widget(self.grid)
        self.desktop.add_widget(scroll)

    def populate_apps(self, app_list):
        self.grid.clear_widgets()
        for app in app_list:
            tile = AppTile(orientation="vertical", size_hint_y=None, height=110, padding=6, spacing=4)

            icon = app.get('icon', '📦')
            if isinstance(icon, str) and os.path.isfile(icon):
                icon_widget = Image(source=icon, size_hint_y=0.65, allow_stretch=True, keep_ratio=True)
            else:
                icon_widget = Label(text=icon if isinstance(icon, str) else "📦",
                                     font_size='30sp', size_hint_y=0.65)

            name_label = Label(text=app['name'], size_hint_y=0.35, font_size='11sp',
                                halign='center', valign='middle', shorten=True)
            name_label.bind(size=name_label.setter('text_size'))

            tile.add_widget(icon_widget)
            tile.add_widget(name_label)
            tile.bind(on_release=lambda x, a=app: self.launch_app(a))
            self.grid.add_widget(tile)

    def _filter_home_view(self, instance, value):
        query = value.lower()
        filtered = [a for a in self.loader.apps if query in a['name'].lower()]
        self.populate_apps(filtered)

    def launch_app(self, app):
        name = app["name"]
        
        if "Settings" not in self.app_memory: 
            self.app_memory["Settings"] = {"data": {}}
        if self.active_app and self.active_app != "Settings":
            self.app_memory["Settings"]["data"]["last_app"] = self.active_app

        if name in self.processes:
            self.switch_app(name)
            return

        api = OSAPI(self, app["id"])
        if app["id"] not in self.app_memory: self.app_memory[app["id"]] = {"data": {}}

        try:
            widget = app["run"](api, self.app_memory[app["id"]], api.save, api.load)
            frame = WindowFrame(name, widget, lambda: self.close_app(name), lambda: self.render_home())
            self.processes[name] = frame
            self.switch_app(name)
        except Exception as e:
            self.show_notification(f"Launch Failed: {str(e)}")

    def switch_app(self, name):
        self.active_app = name
        self.desktop.clear_widgets()
        self.desktop.add_widget(self.processes[name])
        self.update_taskbar()

    def close_app(self, name):
        self.processes.pop(name, None)
        self.render_home()
        self.update_taskbar()

    def toggle_quick_menu(self):
        box = BoxLayout(orientation="vertical", spacing=10, padding=10)
        box.add_widget(Label(text="Desktop Personalization"))

        theme_grid = GridLayout(cols=3, size_hint_y=None, height=45, spacing=5)
        # Fixed key matching here from "navy blue" back to "blue"
        for theme in ["dark", "light", "blue"]:
            btn = Button(text="Navy Blue" if theme == "blue" else theme.capitalize())
            btn.bind(on_press=lambda x, t=theme: [self.apply_theme(t), self.show_notification(f"Theme: {t}")])
            theme_grid.add_widget(btn)
        box.add_widget(theme_grid)

        box.add_widget(Button(text="📶 Network Connection: Connected Status"))

        time_lbl = Label(text="🕒 " + datetime.now().strftime("%H:%M:%S"))
        box.add_widget(time_lbl)

        Popup(title="Quick Settings Menu", content=box, size_hint=(0.8, 0.5)).open()

    def open_power_menu(self):
        box = BoxLayout(orientation="vertical", spacing=10, padding=10)
        popup = Popup(title="Power Menu", content=box, size_hint=(0.6, 0.5))

        btn_restart = Button(text="🔄 Restart")
        btn_shutdown = Button(text="🛑 Shut Down")
        btn_cancel = Button(text="❌ Cancel")

        btn_restart.bind(on_press=lambda x: [popup.dismiss(), self.trigger_restart()])
        btn_shutdown.bind(on_press=lambda x: [popup.dismiss(), App.get_running_app().stop()])
        btn_cancel.bind(on_press=lambda x: popup.dismiss())

        box.add_widget(btn_restart)
        box.add_widget(btn_shutdown)
        box.add_widget(btn_cancel)
        popup.open()

    def trigger_restart(self):
        self.taskbar.clear_widgets()
        self.processes.clear()
        self.desktop.clear_widgets()
        self.desktop.add_widget(Label(text="Restarting...", font_size=28))
        Clock.schedule_once(lambda dt: self.start_boot(), 2.0)

    def update_taskbar(self):
        self.taskbar.clear_widgets()
        
        home = Button(text="HOME", size_hint_x=0.2)
        home_hold = {"event": None, "triggered": False}

        def home_press(instance):
            home_hold["triggered"] = False
            home_hold["event"] = Clock.schedule_once(lambda dt: home_long_press(), 1.5)

        def home_long_press():
            home_hold["triggered"] = True
            self.open_power_menu()

        def home_release(instance):
            if home_hold["event"]:
                Clock.unschedule(home_hold["event"])
            if not home_hold["triggered"]:
                self.render_home()

        home.bind(on_press=home_press)
        home.bind(on_release=home_release)
        self.taskbar.add_widget(home)

        settings = Button(text="⚙", size_hint_x=0.15)
        settings.bind(on_release=lambda x: self.toggle_quick_menu())
        self.taskbar.add_widget(settings)

        for name in list(self.processes.keys()):
            btn = Button(text=name)
            hold = {"event": None, "triggered": False}

            def start_hold(instance, n=name, h=hold):
                h["triggered"] = False
                h["event"] = Clock.schedule_once(lambda dt: trigger_hold_close(n, h), 2.0)

            def trigger_hold_close(n, h):
                h["triggered"] = True
                self.close_app(n)
                self.show_notification(f"Terminated Process: {n}")

            def release_tap(instance, n=name, h=hold):
                if h["event"]:
                    Clock.unschedule(h["event"])
                if not h["triggered"]:
                    self.switch_app(n)

            btn.bind(on_press=start_hold)
            btn.bind(on_release=release_tap)
            self.taskbar.add_widget(btn)

class LegendaryOSApp(App):
    def build(self): return LegendaryOS()

if __name__ == "__main__":
    LegendaryOSApp().run()
