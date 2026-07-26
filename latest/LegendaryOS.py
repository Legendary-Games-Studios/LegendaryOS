import os
import sys
import importlib.util
import zipfile
import zipimport
import types
import json
import shutil
from datetime import datetime

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
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
        self.add_widget(Label(text="LegendaryOS v1.3.0", font_size=32))
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
                        self.apps.append({
                            "id": file[:-3], "name": getattr(module, "APP_NAME", file[:-3]),
                            "icon": getattr(module, "APP_ICON", "📦"), "run": getattr(module, "run"), "path": path
                        })
                    except Exception as e:
                        self.load_errors.append(f"App '{file}' failed to initialize:\n{str(e)}")

                elif file.endswith(".zip"):
                    try:
                        if not zipfile.is_zipfile(path): continue
                        abs_zip_path = os.path.abspath(path)
                        importer = zipimport.zipimporter(abs_zip_path)
                        
                        app_id = file[:-4]
                        name, version = app_id, "1.0"
                        with zipfile.ZipFile(path, 'r') as archive:
                            file_list = archive.namelist()
                            if "main.py" not in file_list: continue
                            
                            if "manifest.json" in file_list:
                                with archive.open("manifest.json") as m:
                                    try:
                                        m_data = json.loads(m.read().decode('utf-8'))
                                        name = m_data.get("name", name)
                                        version = m_data.get("version", version)
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

                        self.apps.append({
                            "id": app_id, 
                            "name": name, 
                            "icon": getattr(module, "APP_ICON", "📦"),
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
        self.desktop.add_widget(BootScreen(self.go_home))

    def go_home(self):
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
        self.grid = GridLayout(cols=1, size_hint_y=None, spacing=5)
        self.grid.bind(minimum_height=self.grid.setter("height"))
        
        search_input.bind(text=self._filter_home_view)
        
        self.populate_apps(self.loader.apps)
        scroll.add_widget(self.grid)
        self.desktop.add_widget(scroll)

    def populate_apps(self, app_list):
        self.grid.clear_widgets()
        for app in app_list:
            btn = Button(text=f"{app.get('icon','📦')} {app['name']}", size_hint_y=None, height=60)
            btn.bind(on_release=lambda x, a=app: self.launch_app(a))
            self.grid.add_widget(btn)

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
