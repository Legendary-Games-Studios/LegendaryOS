import os
import sys
import importlib.util
import zipfile
import zipimport
import types
import json
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


# ================= RISK SCANNER =================
def scan_risk(path):
    risky = [
        "exec(", "eval(", "subprocess",
        "os.system", "os.popen",
        "__import__", "ctypes"
    ]
    try:
        if path.lower().endswith(".zip"):
            if not zipfile.is_zipfile(path):
                return []
            with zipfile.ZipFile(path, 'r') as archive:
                if "main.py" in archive.namelist():
                    with archive.open("main.py") as f:
                        code = f.read().decode('utf-8', errors='ignore')
                else:
                    return []
        else:
            with open(path, "r", errors="ignore") as f:
                code = f.read()
                
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

        anim = Animation(angle=360, duration=1)
        anim += Animation(angle=0, duration=0)
        anim.repeat = True
        anim.start(self.rot)

    def update(self, *args):
        self.rot.origin = self.center
        self.line.circle = (self.center_x, self.center_y, 60, 0, 300)


# ================= BOOT =================
class BootScreen(BoxLayout):
    def __init__(self, done, **kwargs):
        super().__init__(orientation="vertical", **kwargs)

        self.add_widget(Label(text="LegendaryOS", font_size=32))
        self.add_widget(Spinner())

        Clock.schedule_once(lambda dt: done(), 2.8)


# ================= APP LOADER =================
class AppLoader:
    def __init__(self):
        self.apps = []
        self.load_errors = [] 

    def load(self):
        self.apps = []
        self.load_errors = []

        for base in [
            "LegendaryOS/root/system-apps",
            "LegendaryOS/root/user-apps"
        ]:
            if not os.path.exists(base):
                continue

            for file in os.listdir(base):
                path = os.path.join(base, file)

                # --- METHOD 1: Standard Python App ---
                if file.endswith(".py"):
                    try:
                        spec = importlib.util.spec_from_file_location(file[:-3], path)
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)

                        self.apps.append({
                            "id": file[:-3],
                            "name": getattr(module, "APP_NAME", file[:-3]),
                            "icon": getattr(module, "APP_ICON", "📦"),
                            "run": getattr(module, "run"),
                            "path": path
                        })

                    except Exception as e:
                        self.load_errors.append(f"App '{file}' crashed during boot:\n{str(e)}")

                # --- METHOD 2: Bulletproof Zipped App with zipimport ---
                elif file.endswith(".zip"):
                    try:
                        if not zipfile.is_zipfile(path):
                            self.load_errors.append(f"File '{file}' is not a valid zip file binary.")
                            continue

                        abs_zip_path = os.path.abspath(path)
                        importer = zipimport.zipimporter(abs_zip_path)
                        
                        with zipfile.ZipFile(path, 'r') as archive:
                            file_list = archive.namelist()
                            
                            if "main.py" not in file_list:
                                self.load_errors.append(f"Zip '{file}' missing 'main.py' at its root layout.")
                                continue
                                
                            with archive.open("main.py") as f:
                                code_content = f.read().decode('utf-8')

                        app_id = file[:-4]
                        
                        sys.path.insert(0, abs_zip_path)
                        module = types.ModuleType(app_id)
                        module.__dict__['__file__'] = abs_zip_path
                        module.__dict__['__loader__'] = importer
                        
                        exec(code_content, module.__dict__)

                        self.apps.append({
                            "id": app_id,
                            "name": getattr(module, "APP_NAME", app_id),
                            "icon": getattr(module, "APP_ICON", "📦"),
                            "run": getattr(module, "run"),
                            "path": path
                        })
                        
                        if abs_zip_path in sys.path:
                            sys.path.remove(abs_zip_path)
                                    
                    except Exception as e:
                        self.load_errors.append(f"Zip App '{file}' failed to initialize:\n{str(e)}")


# ================= SDK / OSAPI BRIDGE =================
class OSAPI:
    def __init__(self, os_ref, app_id):
        self.os = os_ref
        self.app_id = app_id

    def save(self, key, value):
        if self.app_id not in self.os.app_memory:
            self.os.app_memory[self.app_id] = {"data": {}}
        self.os.app_memory[self.app_id]["data"][key] = value

    def load(self, key):
        if self.app_id not in self.os.app_memory:
            self.os.app_memory[self.app_id] = {"data": {}}
        return self.os.app_memory[self.app_id]["data"].get(key)

    def set_wallpaper_color(self, r, g, b, a=1.0):
        """Allows external apps to pass color configurations safely."""
        self.os.update_wallpaper_color(r, g, b, a)

    def set_setting(self, key, value):
        """Global persistent key-value configuration wrapper."""
        self.os.set_setting(key, value)

    def get_setting(self, key, default=None):
        """Global configuration lookup wrapper."""
        return self.os.get_setting(key, default)


# ================= MAIN OS LAYER =================
class LegendaryOS(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)

        self.loader = AppLoader()
        self.loader.load()

        self.processes = {}
        self.app_memory = {}
        self.active_app = None

        # GLOBAL STORAGE PATH PATTERN CONFIGURATION
        self.settings_path = os.path.join(
            "LegendaryOS/root/system-apps/AppData/settings",
            "settings.json"
        )
        self.settings = {}
        self.load_settings()

        self.desktop = BoxLayout()
        self.taskbar = BoxLayout(size_hint=(1, 0.1))

        # Core fallback validation logic
        fallback_color = [0, 0, 0, 1]
        initial_color = self.get_setting("wallpaper_color", fallback_color)
        if not isinstance(initial_color, list) or len(initial_color) < 4:
            initial_color = fallback_color

        # Canvas Context Registration
        with self.desktop.canvas.before:
            self.bg_color = Color(*initial_color)
            self.bg_rect = Rectangle(pos=self.desktop.pos, size=self.desktop.size)
            
        self.desktop.bind(pos=self._update_bg_layout, size=self._update_bg_layout)

        self.add_widget(self.desktop)
        self.add_widget(self.taskbar)

        self.start_boot()

    # ================= PERSISTENCE INTERNALS =================
    def load_settings(self):
        """Parses saved persistent configurations directly off local disk tracking vectors."""
        try:
            os.makedirs(os.path.dirname(self.settings_path), exist_ok=True)
            if os.path.exists(self.settings_path):
                with open(self.settings_path, "r") as f:
                    self.settings = json.load(f)
            else:
                self.settings = {}
        except Exception:
            self.settings = {}

    def save_settings(self):
        """Guarantees uncorrupted configuration writes using low-level kernel storage syncs."""
        try:
            os.makedirs(os.path.dirname(self.settings_path), exist_ok=True)
            with open(self.settings_path, "w") as f:
                json.dump(self.settings, f, indent=4)
                f.flush()
                os.fsync(f.fileno())  # Forces unwritten runtime buffers out onto cold memory storage
        except Exception:
            pass

    def set_setting(self, key, value):
        self.settings[key] = value
        self.save_settings()

    def get_setting(self, key, default=None):
        return self.settings.get(key, default)

    # ================= CANVAS HARDENING INTERNALS =================
    def _update_bg_layout(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

    def update_wallpaper_color(self, r, g, b, a):
        """Clamps system colors safely between 0.0 and 1.0 to block engine exceptions."""
        try:
            clamped_r = max(0.0, min(float(r), 1.0))
            clamped_g = max(0.0, min(float(g), 1.0))
            clamped_b = max(0.0, min(float(b), 1.0))
            clamped_a = max(0.0, min(float(a), 1.0))
            
            if hasattr(self, 'bg_color') and self.bg_color:
                self.bg_color.rgba = (clamped_r, clamped_g, clamped_b, clamped_a)
        except Exception as e:
            print(f"[OS Kernel Error] Intercepted illegal canvas rendering vector: {e}")

    # ================= BOOT LAYER =================
    def start_boot(self):
        self.desktop.clear_widgets()
        self.desktop.add_widget(BootScreen(self.go_home))

    def go_home(self):
        self.render_home()
        self.update_taskbar()
        
        # Ensures race-conditioned layouts settle cleanly before execution
        Clock.schedule_once(lambda dt: self._apply_boot_wallpaper(), 0)

        if self.loader.load_errors:
            Clock.schedule_once(lambda dt: self.show_system_diagnostic_report(), 0.5)

    def _apply_boot_wallpaper(self):
        """Guarantees configuration arrays get loaded and applied down to canvas hardware."""
        saved_color = self.get_setting("wallpaper_color", [0, 0, 0, 1])
        self.update_wallpaper_color(*saved_color)

    def show_system_diagnostic_report(self):
        box = BoxLayout(orientation='vertical', padding=10, spacing=10)
        errors_text = "\n\n".join(self.loader.load_errors)
        
        scroll = ScrollView()
        scroll.add_widget(Label(text=errors_text, size_hint_y=None, text_size=(Window.width * 0.8, None)))
        scroll.children[0].bind(texture_size=lambda instance, value: setattr(instance, 'height', value[1]))
        
        box.add_widget(scroll)
        close_btn = Button(text="Acknowledge System Diagnostics", size_hint_y=0.2)
        popup = Popup(title="App Boot Subsystem Log Diagnostics", content=box, size_hint=(0.9, 0.7))
        close_btn.bind(on_press=popup.dismiss)
        box.add_widget(close_btn)
        popup.open()

    # ================= HOME INTERFACE LAYER =================
    def render_home(self):
        self.desktop.clear_widgets()

        scroll = ScrollView()
        grid = GridLayout(cols=1, size_hint_y=None, spacing=5)
        grid.bind(minimum_height=grid.setter("height"))

        for app in self.loader.apps:
            btn = Button(text=f"{app['icon']} {app['name']}", size_hint_y=None, height=60)
            hold = {"event": None, "held": False}

            def press(instance, a=app):
                hold["held"] = False
                hold["event"] = Clock.schedule_once(
                    lambda dt: self._cancel_launch(hold), 1
                )

            def release(instance, a=app):
                if hold["event"]:
                    hold["event"].cancel()
                if not hold["held"]:
                    self.launch_app(a)

            btn.bind(on_press=press)
            btn.bind(on_release=release)
            grid.add_widget(btn)

        scroll.add_widget(grid)
        self.desktop.add_widget(scroll)

    def _cancel_launch(self, hold):
        hold["held"] = True

    # ================= SYSTEM DESKTOP UTILITIES =================
    def launch_app_by_id(self, app_id, file_to_open=None):
        target_app = None
        for app in self.loader.apps:
            if app["id"] == app_id:
                target_app = app
                break

        if target_app:
            if app_id not in self.app_memory:
                self.app_memory[app_id] = {"data": {}}
            if file_to_open:
                self.app_memory[app_id]["target_file"] = file_to_open
            Clock.schedule_once(lambda dt: self.launch_app(target_app), 0.05)
        else:
            box = BoxLayout(orientation='vertical', padding=10, spacing=10)
            loaded_ids = [a["id"] for a in self.loader.apps]
            box.add_widget(Label(text=f"App ID '{app_id}' not found!\n\nLoaded apps collection:\n{loaded_ids}"))
            
            close_btn = Button(text="Dismiss", size_hint_y=0.3)
            popup = Popup(title="System Subsystem Error", content=box, size_hint=(0.9, 0.6))
            close_btn.bind(on_press=popup.dismiss)
            box.add_widget(close_btn)
            popup.open()

    def toggle_quick_menu(self):
        box = BoxLayout(orientation="vertical", spacing=10)
        box.add_widget(Label(text="Quick Settings"))

        try:
            from jnius import autoclass
            Context = autoclass('android.content.Context')
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            wifi = PythonActivity.mActivity.getSystemService(Context.WIFI_SERVICE)
            ssid = wifi.getConnectionInfo().getSSID().replace('"', '')
        except:
            ssid = "Unavailable"

        box.add_widget(Button(text=f"📶 WiFi: {ssid}"))

        if not hasattr(self, "_brightness"):
            self._brightness = Widget()
            with self._brightness.canvas:
                self._b_color = Color(0, 0, 0, 0)
                self._b_rect = Rectangle(pos=(0, 0), size=Window.size)

            self.desktop.add_widget(self._brightness)
            Window.bind(size=lambda *a: setattr(self._b_rect, "size", Window.size))

        def set_brightness(val):
            self._b_color.a = 1 - val

        box.add_widget(Label(text="🔆 Brightness"))
        slider = Slider(min=0, max=1, value=1)
        slider.bind(value=lambda i, v: set_brightness(v))
        box.add_widget(slider)

        time_btn = Button(text="")
        def update_time(dt):
            time_btn.text = "🕒 " + datetime.now().strftime("%H:%M:%S")
        Clock.schedule_interval(update_time, 1)
        box.add_widget(time_btn)

        box.add_widget(Button(text="📅 " + datetime.now().strftime("%Y-%m-%d")))
        Popup(title="Quick Settings", content=box, size_hint=(0.7, 0.6)).open()

    def open_power_menu(self):
        box = BoxLayout(orientation="vertical", spacing=10, padding=10)
        popup = Popup(title="Power Menu", content=box, size_hint=(0.6, 0.5), auto_dismiss=True)

        btn_restart = Button(text="🔄 Restart")
        btn_shutdown = Button(text="🛑 Shut Down")
        btn_sleep = Button(text="🌙 Sleep")
        btn_cancel = Button(text="❌ Cancel")

        btn_restart.bind(on_press=lambda x: [popup.dismiss(), self.trigger_restart()])
        btn_shutdown.bind(on_press=lambda x: [popup.dismiss(), self.trigger_shutdown()])
        btn_sleep.bind(on_press=lambda x: [popup.dismiss(), self.simulate_sleep()])
        btn_cancel.bind(on_press=lambda x: popup.dismiss())

        box.add_widget(btn_restart)
        box.add_widget(btn_shutdown)
        box.add_widget(btn_sleep)
        box.add_widget(btn_cancel)

        popup.open()

    def trigger_restart(self):
        self.taskbar.clear_widgets()
        self.processes.clear()
        self.desktop.clear_widgets()
        self.desktop.add_widget(Label(text="Restarting...", font_size=28))
        Clock.schedule_once(lambda dt: self.start_boot(), 3.0)

    def trigger_shutdown(self):
        self.taskbar.clear_widgets()
        self.processes.clear()
        self.desktop.clear_widgets()
        self.desktop.add_widget(Label(text="Shutting Down...", font_size=28))
        Clock.schedule_once(lambda dt: App.get_running_app().stop(), 3.0)

    def simulate_sleep(self):
        self.desktop.clear_widgets()
        sleep_label = Label(text="System Sleeping...\nTap Taskbar Home to Wake Up", font_size=24)
        self.desktop.add_widget(sleep_label)

    # ================= APPLICATION LIFECYCLE MANAGEMENT =================
    def launch_app(self, app):
        app_id = app["id"]
        if app_id not in self.app_memory:
            self.app_memory[app_id] = {"data": {}}

        risks = scan_risk(app["path"])
        if risks:
            self.desktop.clear_widgets()
            self.desktop.add_widget(Label(text="⚠ Risk Warning Flagged:\n" + ", ".join(risks)))
            return

        self._start_app(app)

    def _start_app(self, app):
        app_id = app["id"]
        name = app["name"]

        if name in self.processes:
            self.switch_app(name)
            return

        if app_id not in self.app_memory:
            self.app_memory[app_id] = {"data": {}}

        api = OSAPI(self, app_id)

        try:
            is_zip = app["path"].lower().endswith(".zip")
            if is_zip:
                sys.path.insert(0, os.path.abspath(app["path"]))

            widget = app["run"](
                api,
                self.app_memory[app_id],
                api.save,
                api.load
            )
            
            if is_zip:
                sys.path.remove(os.path.abspath(app["path"]))
                
        except Exception as e:
            self.desktop.clear_widgets()
            self.desktop.add_widget(Label(text=f"Crash:\n{name}\n\n{e}"))
            return

        self.processes[name] = widget
        self.active_app = name
        self.show_app(name)
        self.update_taskbar()

    def show_app(self, name):
        self.desktop.clear_widgets()
        self.desktop.add_widget(self.processes[name])

    def switch_app(self, name):
        self.active_app = name
        self.show_app(name)

    def close_app(self, name):
        self.processes.pop(name, None)
        self.render_home()
        self.update_taskbar()

    # ================= GLOBAL USER WINDOW INTERACTION INTERFACES =================
    def update_taskbar(self):
        self.taskbar.clear_widgets()

        home = Button(text="HOME")
        home_hold = {"event": None, "triggered": False}

        def home_press(instance):
            home_hold["triggered"] = False
            home_hold["event"] = Clock.schedule_once(
                lambda dt: home_long_press(), 1.5
            )

        def home_long_press():
            home_hold["triggered"] = True
            self.open_power_menu()

        def home_release(instance):
            if home_hold["event"]:
                home_hold["event"].cancel()
            if not home_hold["triggered"]:
                self.render_home()
                self.update_taskbar()

        home.bind(on_press=home_press)
        home.bind(on_release=home_release)
        self.taskbar.add_widget(home)

        settings = Button(text="☰")
        settings.bind(on_press=lambda x: self.toggle_quick_menu())
        self.taskbar.add_widget(settings)

        for name in list(self.processes.keys()):
            btn = Button(text=name)
            hold = {"event": None}

            def start(instance, n=name):
                hold["event"] = Clock.schedule_once(
                    lambda dt: self.close_app(n), 2
                )

            def cancel(instance):
                if hold["event"]:
                    hold["event"].cancel()
                    hold["event"] = None

            def switch(instance, n=name):
                if hold["event"] is None:
                    self.switch_app(n)

            btn.bind(on_press=start)
            btn.bind(on_release=cancel)
            btn.bind(on_release=switch)
            self.taskbar.add_widget(btn)


# ================= RUNTIME ENTRYPOINT =================
class LegendaryOSApp(App):
    def build(self):
        return LegendaryOS()

    def on_start(self):
        try:
            from kivy.core.window import Window
            Window.fullscreen = True
        except Exception as e:
            print("Fullscreen toggle caught:", e)


if __name__ == "__main__":
    LegendaryOSApp().run()
