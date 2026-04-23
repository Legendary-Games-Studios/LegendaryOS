import os
import importlib.util

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
from datetime import datetime

# ================= FULLSCREEN =================
Window.fullscreen = True


# ================= RISK SCANNER =================
def scan_risk(path):
    risky = [
        "exec(", "eval(", "subprocess",
        "os.system", "os.popen",
        "__import__", "ctypes"
    ]
    try:
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

    def load(self):
        self.apps = []

        for base in [
            "LegendaryOS/root/system-apps",
            "LegendaryOS/root/user-apps"
        ]:
            if not os.path.exists(base):
                continue

            for file in os.listdir(base):
                if not file.endswith(".py"):
                    continue

                path = os.path.join(base, file)

                try:
                    spec = importlib.util.spec_from_file_location(file, path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    self.apps.append({
                        "id": file[:-3],  # ✅ STABLE ID
                        "name": getattr(module, "APP_NAME", file[:-3]),
                        "icon": getattr(module, "APP_ICON", "📦"),
                        "run": getattr(module, "run"),
                        "path": path
                    })

                except Exception as e:
                    print("Load error:", file, e)


# ================= SDK =================
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


# ================= MAIN OS =================
class LegendaryOS(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)

        self.loader = AppLoader()
        self.loader.load()

        self.processes = {}
        self.app_memory = {}
        self.active_app = None

        self.desktop = BoxLayout()
        self.taskbar = BoxLayout(size_hint=(1, 0.1))

        self.add_widget(self.desktop)
        self.add_widget(self.taskbar)

        self.start_boot()

    # ================= BOOT =================
    def start_boot(self):
        self.desktop.clear_widgets()
        self.desktop.add_widget(BootScreen(self.go_home))

    def go_home(self):
        self.render_home()
        self.update_taskbar()

    # ================= HOME (SCROLL FIX) =================
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

    # ================= QUICK SETTINGS =================
    def toggle_quick_menu(self):
        box = BoxLayout(orientation="vertical", spacing=10)

        box.add_widget(Label(text="Quick Settings"))

        # WiFi
        try:
            from jnius import autoclass
            Context = autoclass('android.content.Context')
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            wifi = PythonActivity.mActivity.getSystemService(Context.WIFI_SERVICE)
            ssid = wifi.getConnectionInfo().getSSID().replace('"', '')
        except:
            ssid = "Unavailable"

        box.add_widget(Button(text=f"📶 WiFi: {ssid}"))

        # Brightness overlay
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

        # Time
        time_btn = Button(text="")
        def update_time(dt):
            time_btn.text = "🕒 " + datetime.now().strftime("%H:%M:%S")
        Clock.schedule_interval(update_time, 1)
        box.add_widget(time_btn)

        # Date
        box.add_widget(Button(text="📅 " + datetime.now().strftime("%Y-%m-%d")))

        Popup(title="Quick Settings", content=box, size_hint=(0.7, 0.6)).open()

    # ================= LAUNCH =================
    def launch_app(self, app):
        app_id = app["id"]

        if app_id not in self.app_memory:
            self.app_memory[app_id] = {"data": {}}

        risks = scan_risk(app["path"])
        if risks:
            self.desktop.clear_widgets()
            self.desktop.add_widget(Label(text="⚠ Risk:\n" + ", ".join(risks)))
            return

        self._start_app(app)

    # ================= START =================
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
            widget = app["run"](
                api,
                self.app_memory[app_id],
                api.save,
                api.load
            )
        except Exception as e:
            self.desktop.clear_widgets()
            self.desktop.add_widget(Label(text=f"Crash:\n{name}\n\n{e}"))
            return

        self.processes[name] = widget
        self.active_app = name
        self.show_app(name)
        self.update_taskbar()

    # ================= DISPLAY =================
    def show_app(self, name):
        self.desktop.clear_widgets()
        self.desktop.add_widget(self.processes[name])

    def switch_app(self, name):
        self.active_app = name
        self.show_app(name)

    # ================= CLOSE =================
    def close_app(self, name):
        self.processes.pop(name, None)
        self.render_home()
        self.update_taskbar()

    # ================= TASKBAR =================
    def update_taskbar(self):
        self.taskbar.clear_widgets()

        home = Button(text="HOME")
        home.bind(on_press=lambda x: self.render_home())
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


# ================= APP =================
class LegendaryOSApp(App):
    def build(self):
        return LegendaryOS()


if __name__ == "__main__":
    LegendaryOSApp().run()