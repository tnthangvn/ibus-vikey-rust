#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ViKey - biểu tượng khay Vi/En cho GNOME (Wayland dùng được nhờ extension
AppIndicator). Bù cho việc GNOME Shell không hiện menu thuộc tính của ibus.

Chức năng: hiện Vi/En trên thanh trên, menu bật/tắt tiếng Việt, đổi kiểu gõ,
mở Cài đặt, thoát. Trạng thái đồng bộ hai chiều với engine qua file
~/.config/ibus-vikey/config.json (engine tự ghi khi bấm Ctrl+Shift; tray theo
dõi file để đổi icon ngay lập tức).

Chạy:  vikey --tray   (hoặc: python3 tray.py). Tự chạy nền qua ~/.config/autostart.
"""

import fcntl
import os
import sys

import gi

gi.require_version("Gtk", "3.0")
try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator
except (ValueError, ImportError):
    try:
        gi.require_version("AppIndicator3", "0.1")
        from gi.repository import AppIndicator3 as AppIndicator
    except (ValueError, ImportError):
        sys.stderr.write(
            "ViKey tray cần thư viện AppIndicator.\n"
            "  Ubuntu:  sudo apt install gir1.2-ayatanaappindicator3-0.1\n"
            "GNOME cũng cần bật extension 'Ubuntu AppIndicators' (Ubuntu đã bật sẵn).\n"
        )
        sys.exit(1)

from gi.repository import Gio, GLib, Gtk  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config as cfgmod  # noqa: E402

APP_ID = "vikey-tray"


def icon_dir():
    env = os.environ.get("VIKEY_ICON_DIR")
    if env and os.path.isdir(env):
        return env
    local = os.path.join(os.path.dirname(HERE), "icons")  # ../icons khi chạy từ repo
    if os.path.isfile(os.path.join(local, "vikey-vi.svg")):
        return local
    return "/usr/share/ibus-vikey/icons"


def icon_path(enabled):
    return os.path.join(icon_dir(), "vikey-vi.svg" if enabled else "vikey-en.svg")


def single_instance():
    """Chặn chạy nhiều bản tray cùng lúc. Trả về file lock (giữ tham chiếu)."""
    lock = os.path.join(cfgmod.CONFIG_DIR, ".tray.lock")
    os.makedirs(cfgmod.CONFIG_DIR, exist_ok=True)
    fp = open(lock, "w")
    try:
        fcntl.flock(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.stderr.write("ViKey tray đã chạy rồi.\n")
        sys.exit(0)
    return fp


class Tray:
    def __init__(self):
        self.cfg = cfgmod.load()
        self.ind = AppIndicator.Indicator.new(
            APP_ID, icon_path(self.cfg["enabled"]),
            AppIndicator.IndicatorCategory.APPLICATION_STATUS,
        )
        self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.ind.set_title("ViKey")
        self.menu = Gtk.Menu()
        self.rebuild()
        self.ind.set_menu(self.menu)  # gắn menu SAU khi đã có item
        self.watch_config()

    # ---- đồng bộ khi engine (hoặc cửa sổ Cài đặt) sửa config
    def watch_config(self):
        gfile = Gio.File.new_for_path(cfgmod.CONFIG_FILE)
        self.monitor = gfile.monitor_file(Gio.FileMonitorFlags.NONE, None)
        self.monitor.connect("changed", self.on_config_changed)

    def on_config_changed(self, *_a):
        new = cfgmod.load()
        if new != self.cfg:
            self.cfg = new
            self.refresh()

    # ---- vẽ lại icon + menu theo self.cfg
    def refresh(self):
        self.ind.set_icon_full(icon_path(self.cfg["enabled"]), "ViKey")
        self.ind.set_label("Vi" if self.cfg["enabled"] else "En", "Vi")
        self.rebuild()
        self.ind.set_menu(self.menu)  # ép AppIndicator vẽ lại menu vừa dựng

    def rebuild(self):
        for c in self.menu.get_children():
            self.menu.remove(c)
        on = self.cfg["enabled"]

        head = Gtk.MenuItem(label="Tiếng Việt: %s  (%s)" % (
            "BẬT" if on else "TẮT", cfgmod.toggle_label(self.cfg)))
        head.set_sensitive(False)
        self.menu.append(head)
        self.menu.append(Gtk.SeparatorMenuItem())

        toggle = Gtk.CheckMenuItem(label="Gõ tiếng Việt")
        toggle.set_active(on)
        toggle.connect("toggled", self.on_toggle)
        self.menu.append(toggle)

        method_item = Gtk.MenuItem(label="Kiểu gõ: %s" % cfgmod.describe("method", self.cfg["method"]))
        submenu = Gtk.Menu()
        group = []
        for m in cfgmod.CHOICES["method"]:
            r = Gtk.RadioMenuItem.new_with_label(group, cfgmod.describe("method", m))
            group = r.get_group()
            r.set_active(m == self.cfg["method"])
            r.connect("toggled", self.on_method, m)
            submenu.append(r)
        method_item.set_submenu(submenu)
        self.menu.append(method_item)

        self.menu.append(Gtk.SeparatorMenuItem())
        setup = Gtk.MenuItem(label="Cài đặt ViKey…")
        setup.connect("activate", self.on_setup)
        self.menu.append(setup)
        quit_it = Gtk.MenuItem(label="Thoát biểu tượng")
        quit_it.connect("activate", lambda *_a: Gtk.main_quit())
        self.menu.append(quit_it)
        self.menu.show_all()

    # ---- ghi config (engine đọc lại khi focus ô nhập tiếp theo)
    def save(self):
        cfgmod.save(self.cfg)
        self.refresh()

    def on_toggle(self, item):
        self.cfg["enabled"] = item.get_active()
        self.save()

    def on_method(self, item, method):
        if item.get_active() and self.cfg["method"] != method:
            self.cfg["method"] = method
            self.save()

    def on_setup(self, *_a):
        exe = os.environ.get("VIKEY_ENGINE", "vikey")
        try:
            GLib.spawn_async([exe, "--setup"], flags=GLib.SpawnFlags.SEARCH_PATH)
        except GLib.Error:
            # fallback: gọi thẳng main.py
            GLib.spawn_async(
                [sys.executable, os.path.join(HERE, "main.py"), "--setup"],
                flags=GLib.SpawnFlags.DEFAULT,
            )


def run():
    _lock = single_instance()  # noqa: F841 (giữ khoá suốt vòng đời)
    Tray()
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(run())
