# -*- coding: utf-8 -*-
"""
settings.py - Cửa sổ "Cài đặt ViKey" (GTK4).

Mở bằng:  vikey --setup   |  menu Vi/En trên thanh trên -> "Cài đặt ViKey…"
          |  Activities -> "ViKey"  |  ibus-setup -> Preferences

Mọi thay đổi được lưu ngay vào ~/.config/ibus-vikey/ ; bộ gõ đang chạy tự nạp
lại khi bạn focus vào ô nhập tiếp theo (không cần khởi động lại IBus).
"""

import os
import sys

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

import config  # noqa: E402
import hotkey  # noqa: E402
from macros import MacroTable, parse  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

# Thẻ "Tuỳ chọn": các nhóm, mỗi mục là ("switch"|"choice", key, tiêu đề, mô tả)
SECTIONS = [
    ("Cơ bản", [
        ("choice", "method", "Kiểu gõ",
         "Telex: aa ee oo aw ow uw dd, s f r x j.  VNI: 6 7 8 9, 1-5.  Telex + VNI: dùng cả hai cùng lúc."),
        ("choice", "toggle_key", "Phím chuyển Việt/Anh",
         "Ctrl+Shift: bấm rồi thả, không kèm phím khác (giống Unikey). Alt+Z: giống Unikey cũ. "
         "Tuỳ chỉnh: bấm nút bên cạnh rồi gõ tổ hợp bạn muốn (vd Ctrl+Shift+Space). "
         "Ngoài ra luôn có Super+Space của GNOME."),
        ("choice", "charset", "Bảng mã",
         "Unicode dựng sẵn (NFC) là chuẩn, dùng cho mọi trường hợp. Unicode tổ hợp (NFD) chỉ khi phần mềm yêu cầu."),
        ("switch", "enabled", "Bật tiếng Việt khi khởi động",
         "Tắt: khởi động ở chế độ gõ tiếng Anh (En), bấm phím chuyển hoặc menu để bật."),
        ("switch", "spell_check", "Kiểm tra chính tả – khôi phục phím với từ sai",
         "Từ không phải tiếng Việt (windows, status, data, sudo apt…) giữ nguyên phím đã gõ. "
         "Nên bật khi hay dùng terminal."),
        ("switch", "modern_tone", "Đặt dấu kiểu mới (hoà, khoẻ, thuý)",
         "Tắt: đặt dấu kiểu cũ (hòa, khỏe, thúy)."),
        ("switch", "free_marking", "Bỏ dấu tự do (gõ dấu ở cuối từ)",
         "Phím dd và aa ee oo (9, 6 với VNI) tìm chữ cái trong cả từ, không cần đứng ngay sau nó: "
         "dend → đen, duongd → đường, tienge → tiêng, khongo → không. "
         "Dấu thanh (s f r x j) và w vốn đã tự do. "
         "Tắt: gõ theo lối cũ (ddeen, tieeng). Lưu ý: bật lên thì vài từ tiếng Anh như 'dad', 'data' "
         "có thể bị biến đổi."),
    ]),
    ("Gõ tắt", [
        ("switch", "macros", "Cho phép gõ tắt",
         "Bung viết tắt (vn → Việt Nam…) khi bấm space, dấu câu, Enter, Tab. Bảng ở thẻ 'Gõ tắt'."),
        ("switch", "macros_when_off", "Gõ tắt cả khi tắt tiếng Việt",
         "Đang ở chế độ En vẫn bung viết tắt. Dùng cơ chế xoá-thay chữ như 'Không gạch chân' "
         "nên có thể lặp chữ ở terminal / app không hỗ trợ."),
    ]),
    ("Nâng cao", [
        ("switch", "auto_direct", "Thử tự chọn lối gõ theo ô nhập (thử nghiệm)",
         "Dùng cờ khả năng IBus để đoán ô nhập nào nên gõ trực tiếp. Cờ này không ổn định – "
         "nó đổi ngay trong một lần focus – nên kết quả thất thường. Bật thì công tắc bên dưới "
         "mất tác dụng ở những ô bị đoán là cần gõ trực tiếp. Nên để tắt."),
        ("switch", "direct_mode", "Không gạch chân (gõ trực tiếp)",
         "Bỏ preedit ở mọi ô nhập. Cần bật khi gõ vào ô contenteditable của trang web "
         "(Adminer, editor web): ở đó preedit bị script tô màu của trang phá, sinh chữ thừa. "
         "TẮT khi dùng terminal / app bị lặp chữ. "
         "Nút bên cạnh đặt phím tắt bật/tắt tạm cho riêng ô nhập đang gõ."),
    ]),
]


def _label(text, css=None, wrap=True, xalign=0.0):
    lb = Gtk.Label(label=text, xalign=xalign, wrap=wrap)
    if css:
        lb.add_css_class(css)
    return lb


class SettingsWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Cài đặt ViKey")
        self.set_default_size(680, 720)
        self.cfg = config.load()
        self.macros = MacroTable()
        self._macro_rows = []
        self._dirty_macros = False

        header = Gtk.HeaderBar()
        self.set_titlebar(header)

        nb = Gtk.Notebook()
        nb.set_margin_top(6)
        nb.set_margin_bottom(6)
        nb.set_margin_start(6)
        nb.set_margin_end(6)
        nb.append_page(self._build_options_page(), Gtk.Label(label="Tuỳ chọn"))
        nb.append_page(self._build_macros_page(), Gtk.Label(label="Gõ tắt"))
        nb.append_page(self._build_about_page(), Gtk.Label(label="Thông tin"))
        self.set_child(nb)

        self.status = Gtk.Label(label="", xalign=0.0)
        self.status.add_css_class("dim-label")
        header.pack_start(self.status)

        self.connect("close-request", self._on_close)

    # --------------------------------------------------------------- tiện ích
    def flash(self, msg):
        self.status.set_text(msg)
        GLib.timeout_add(2500, lambda: (self.status.set_text(""), False)[1])

    # ------------------------------------------------------------ Tuỳ chọn
    def _build_options_page(self):
        scroller = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        for m in ("set_margin_top", "set_margin_bottom", "set_margin_start", "set_margin_end"):
            getattr(box, m)(12)
        for title, items in SECTIONS:
            head = _label(title)
            head.add_css_class("heading")
            head.set_margin_top(6)
            box.append(head)
            listbox = Gtk.ListBox()
            listbox.set_selection_mode(Gtk.SelectionMode.NONE)
            listbox.add_css_class("boxed-list")
            for kind, key, name, desc in items:
                listbox.append(self._option_row(kind, key, name, desc))
            box.append(listbox)
        box.append(_label("Thay đổi được lưu ngay và có hiệu lực khi bạn bấm vào ô nhập tiếp theo.",
                          css="dim-label"))
        scroller.set_child(box)
        return scroller

    def _option_row(self, kind, key, name, desc):
        row = Gtk.ListBoxRow(activatable=False)
        h = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        for m in ("set_margin_top", "set_margin_bottom", "set_margin_start", "set_margin_end"):
            getattr(h, m)(10)
        v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
        v.append(_label(name))
        v.append(_label(desc, css="dim-label"))
        h.append(v)
        if kind == "switch":
            sw = Gtk.Switch(valign=Gtk.Align.CENTER)
            sw.set_active(bool(self.cfg.get(key, config.DEFAULTS[key])))
            sw.connect("state-set", self._on_switch, key)
            if key == "direct_mode":
                self._direct_btn = Gtk.Button(valign=Gtk.Align.CENTER)
                self._direct_btn.set_tooltip_text(
                    "Phím tắt bật/tắt nhanh khi chuyển qua lại giữa terminal và app web")
                self._direct_btn.connect("clicked", self._capture_direct_key)
                self._refresh_direct_btn()
                h.append(self._direct_btn)
            h.append(sw)
        else:
            values = list(config.CHOICES[key])
            labels = [config.CHOICE_LABELS[key][val] for val in values]
            dd = Gtk.DropDown.new_from_strings(labels)
            dd.set_valign(Gtk.Align.CENTER)
            cur = self.cfg.get(key, config.DEFAULTS[key])
            dd.set_selected(values.index(cur) if cur in values else 0)
            dd.connect("notify::selected", self._on_choice, key, values)
            if key == "toggle_key":
                self._toggle_dd = dd
                self._hotkey_btn = Gtk.Button(valign=Gtk.Align.CENTER)
                self._hotkey_btn.set_tooltip_text("Bấm rồi gõ tổ hợp phím mới")
                self._hotkey_btn.connect("clicked", self._capture_hotkey)
                self._refresh_hotkey_btn()
                h.append(self._hotkey_btn)
            h.append(dd)
        row.set_child(h)
        return row

    # --- phím chuyển tuỳ chỉnh
    def _refresh_hotkey_btn(self):
        cur = self.cfg.get("toggle_custom", config.DEFAULTS["toggle_custom"])
        self._hotkey_btn.set_label(hotkey.label(cur))
        self._hotkey_btn.set_visible(self.cfg.get("toggle_key") == "custom")

    def _capture_hotkey(self, *_a):
        self._capture_into("toggle_custom", "Phím chuyển Việt/Anh",
                           "Bấm tổ hợp phím bạn muốn dùng để bật/tắt tiếng Việt…")

    # --- phím tắt "Không gạch chân"
    def _refresh_direct_btn(self):
        cur = self.cfg.get("direct_key", "")
        self._direct_btn.set_label(hotkey.label(cur) if cur else "Đặt phím tắt")

    def _capture_direct_key(self, *_a):
        self._capture_into("direct_key", "Phím tắt Không gạch chân",
                           "Bấm tổ hợp phím bạn muốn dùng để bật/tắt Không gạch chân…",
                           clearable=True)

    def _capture_into(self, cfg_key, title, prompt, clearable=False):
        dlg = Gtk.Window(transient_for=self, modal=True, title=title)
        dlg.set_default_size(380, 140)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for m in ("set_margin_top", "set_margin_bottom", "set_margin_start", "set_margin_end"):
            getattr(box, m)(20)
        lb = _label(prompt, xalign=0.5)
        lb.set_justify(Gtk.Justification.CENTER)
        hint_text = "Ví dụ: Ctrl+Shift+F9, Ctrl+Shift+Space, Shift+F12.  Esc để huỷ."
        if clearable:
            hint_text += "  Backspace để bỏ phím tắt."
        hint = _label(hint_text, css="dim-label", xalign=0.5)
        box.append(lb)
        box.append(hint)
        dlg.set_child(box)
        ctl = Gtk.EventControllerKey()
        ctl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)

        def on_key(_c, keyval, _keycode, state):
            from gi.repository import Gdk
            mask = Gtk.accelerator_get_default_mod_mask()
            if keyval == Gdk.KEY_Escape and not (state & mask):
                dlg.close()
                return True
            if clearable and keyval == Gdk.KEY_BackSpace and not (state & mask):
                self.cfg[cfg_key] = ""
                config.save(self.cfg)
                self._refresh_direct_btn()
                self.flash("Đã bỏ phím tắt Không gạch chân")
                dlg.close()
                return True
            if keyval in (Gdk.KEY_Shift_L, Gdk.KEY_Shift_R, Gdk.KEY_Control_L, Gdk.KEY_Control_R,
                          Gdk.KEY_Alt_L, Gdk.KEY_Alt_R, Gdk.KEY_Super_L, Gdk.KEY_Super_R,
                          Gdk.KEY_Meta_L, Gdk.KEY_Meta_R, Gdk.KEY_Hyper_L, Gdk.KEY_Hyper_R,
                          Gdk.KEY_ISO_Level3_Shift, Gdk.KEY_Caps_Lock, Gdk.KEY_Num_Lock):
                return True   # chờ phím chính
            mods = state & Gtk.accelerator_get_default_mod_mask()
            keyval_l = Gdk.keyval_to_lower(keyval)
            name = Gtk.accelerator_name(keyval_l, mods)
            if hotkey.parse(name) is None:
                lb.set_text("Tổ hợp này không dùng được, thử tổ hợp khác…")
                return True
            if not mods and not (Gdk.KEY_F1 <= keyval_l <= Gdk.KEY_F35):
                lb.set_text("Cần kèm ít nhất một phím Ctrl/Alt/Shift/Super (trừ phím F1–F12)…")
                return True
            taken = hotkey.conflict(name)
            if taken:
                lb.set_text("Đụng phím tắt sẵn có – %s. Thử tổ hợp khác, vd Ctrl+Shift+F9…" % taken)
                return True
            if cfg_key == "direct_key":
                self.cfg["direct_key"] = name
                config.save(self.cfg)
                self._refresh_direct_btn()
                self.flash("Phím tắt Không gạch chân: " + hotkey.label(name))
                dlg.close()
                return True
            self.cfg["toggle_custom"] = name
            self.cfg["toggle_key"] = "custom"
            config.save(self.cfg)
            self._refresh_hotkey_btn()
            if hasattr(self, "_toggle_dd"):
                values = list(config.CHOICES["toggle_key"])
                self._toggle_dd.set_selected(values.index("custom"))
            self.flash("Phím chuyển: " + hotkey.label(name))
            dlg.close()
            return True

        ctl.connect("key-pressed", on_key)
        dlg.add_controller(ctl)
        dlg.present()

    def _on_switch(self, _sw, state, key):
        self.cfg[key] = bool(state)
        config.save(self.cfg)
        self.flash("Đã lưu")
        return False

    def _on_choice(self, dd, _pspec, key, values):
        idx = dd.get_selected()
        if 0 <= idx < len(values):
            self.cfg[key] = values[idx]
            config.save(self.cfg)
            if key == "toggle_key":
                self._refresh_hotkey_btn()
                if values[idx] == "custom":
                    self.flash("Phím chuyển: " + hotkey.label(self.cfg["toggle_custom"]) +
                               " – bấm nút bên cạnh để đổi")
                    return
            self.flash("Đã lưu")

    # -------------------------------------------------------------- Gõ tắt
    def _build_macros_page(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for m in ("set_margin_top", "set_margin_bottom", "set_margin_start", "set_margin_end"):
            getattr(outer, m)(12)

        outer.append(_label(
            "Gõ viết tắt rồi bấm space / dấu câu / Enter để bung nội dung. Viết tắt chỉ gồm chữ cái, "
            "không phân biệt hoa/thường; chữ hoa tự điều chỉnh (vn → Việt Nam, VN → VIỆT NAM).",
            css="dim-label"))

        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        head.append(_label("Viết tắt", xalign=0.0))
        head.get_last_child().set_size_request(140, -1)
        head.append(_label("Nội dung đầy đủ", xalign=0.0))
        head.get_last_child().set_hexpand(True)
        head.append(Gtk.Label(label="   "))
        outer.append(head)

        self.macro_list = Gtk.ListBox()
        self.macro_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.macro_list.add_css_class("boxed-list")
        sc = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        sc.set_child(self.macro_list)
        outer.append(sc)

        for k in sorted(self.macros.table):
            self._add_macro_row(k, self.macros.table[k])

        btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        b_add = Gtk.Button(label="＋ Thêm")
        b_add.connect("clicked", lambda *_a: self._add_macro_row("", "", focus=True))
        b_save = Gtk.Button(label="Lưu bảng gõ tắt")
        b_save.add_css_class("suggested-action")
        b_save.connect("clicked", self._save_macros)
        b_open = Gtk.Button(label="Mở file…")
        b_open.set_tooltip_text(self.macros.path)
        b_open.connect("clicked", self._open_macro_file)
        b_reload = Gtk.Button(label="Nạp lại")
        b_reload.connect("clicked", self._reload_macros)
        btns.append(b_add)
        btns.append(b_save)
        btns.append(Gtk.Box(hexpand=True))
        btns.append(b_reload)
        btns.append(b_open)
        outer.append(btns)
        outer.append(_label("File: " + self.macros.path, css="dim-label"))
        return outer

    def _add_macro_row(self, key, value, focus=False):
        row = Gtk.ListBoxRow(activatable=False)
        h = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        for m in ("set_margin_top", "set_margin_bottom", "set_margin_start", "set_margin_end"):
            getattr(h, m)(4)
        e_key = Gtk.Entry(text=key, placeholder_text="vd: vn")
        e_key.set_size_request(140, -1)
        e_val = Gtk.Entry(text=value, placeholder_text="vd: Việt Nam", hexpand=True)
        b_del = Gtk.Button(icon_name="user-trash-symbolic")
        b_del.add_css_class("flat")
        b_del.set_tooltip_text("Xoá dòng này")
        for e in (e_key, e_val):
            e.connect("changed", lambda *_a: self._mark_dirty())
        e_key.connect("activate", lambda *_a: e_val.grab_focus())
        e_val.connect("activate", self._save_macros)
        h.append(e_key)
        h.append(e_val)
        h.append(b_del)
        row.set_child(h)
        self.macro_list.append(row)
        entry = (row, e_key, e_val)
        self._macro_rows.append(entry)
        b_del.connect("clicked", self._del_macro_row, entry)
        if focus:
            e_key.grab_focus()
            self._mark_dirty()
        return entry

    def _del_macro_row(self, _b, entry):
        self.macro_list.remove(entry[0])
        self._macro_rows.remove(entry)
        self._mark_dirty()

    def _mark_dirty(self):
        self._dirty_macros = True

    def _collect(self):
        table, errors = {}, []
        for _row, e_key, e_val in self._macro_rows:
            k = e_key.get_text().strip().lower()
            v = e_val.get_text().strip()
            if not k and not v:
                continue
            if not k or not v or not k.isascii() or not k.isalpha():
                errors.append(k or "(trống)")
                continue
            table[k] = v
        return table, errors

    def _save_macros(self, *_a):
        table, errors = self._collect()
        if errors:
            self.flash("Dòng sai (viết tắt chỉ gồm chữ cái, nội dung không rỗng): " + ", ".join(errors))
            return
        lines = [
            "# Bảng gõ tắt ViKey - mỗi dòng:  viết_tắt:nội_dung_đầy_đủ",
            "# Viết tắt chỉ gồm chữ cái, không phân biệt hoa/thường. Dòng bắt đầu bằng # bị bỏ qua.",
        ]
        for k in sorted(table):
            lines.append("%s:%s" % (k, table[k]))
        try:
            self.macros._write(lines)
        except OSError as e:
            self.flash("Không lưu được: %s" % e)
            return
        self._dirty_macros = False
        self.flash("Đã lưu %d mục gõ tắt" % len(table))

    def _reload_macros(self, *_a):
        self.macros.reload()
        for row, _k, _v in list(self._macro_rows):
            self.macro_list.remove(row)
        self._macro_rows = []
        for k in sorted(self.macros.table):
            self._add_macro_row(k, self.macros.table[k])
        self._dirty_macros = False
        self.flash("Đã nạp lại từ file")

    def _open_macro_file(self, *_a):
        path = self.macros.ensure_file()
        Gio.AppInfo.launch_default_for_uri("file://" + path, None)

    def _on_close(self, *_a):
        if self._dirty_macros:
            table, errors = self._collect()
            if not errors:
                self._save_macros()
        return False

    # ------------------------------------------------------------- Thông tin
    def _build_about_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for m in ("set_margin_top", "set_margin_bottom", "set_margin_start", "set_margin_end"):
            getattr(box, m)(16)
        try:
            from main import VERSION
        except Exception:  # pragma: no cover
            VERSION = "?"
        title = _label("ViKey %s – bộ gõ tiếng Việt Telex cho IBus" % VERSION)
        title.add_css_class("title-2")
        box.append(title)
        rows = [
            ("Chuyển bộ gõ", "Super+Space (GNOME) hoặc biểu tượng bàn phím trên thanh trên"),
            ("Bật/tắt tiếng Việt nhanh", "Phím chuyển hiện tại: %s (đổi ở thẻ Tuỳ chọn) hoặc menu Vi/En"
             % config.toggle_label(self.cfg)),
            ("Telex", "aa ee oo → â ê ô · aw ow uw → ă ơ ư · dd → đ · s f r x j → sắc huyền hỏi ngã nặng · z xoá dấu"),
            ("VNI", "6 → â ê ô · 7 → ơ ư · 8 → ă · 9 → đ · 1 2 3 4 5 → sắc huyền hỏi ngã nặng · 0 xoá dấu"),
            ("Lấy chữ gốc", "Gõ lặp phím dấu: ass → as, tesst → test, ddd → dd"),
            ("Gõ thử trong terminal", 'vikey --test "tieesng vieejt"'),
            ("Cấu hình", config.CONFIG_FILE),
            ("Bảng gõ tắt", self.macros.path),
            ("Xem log khi lỗi", "journalctl --user -b | grep -i vikey"),
        ]
        grid = Gtk.Grid(column_spacing=16, row_spacing=6)
        for i, (k, v) in enumerate(rows):
            lk = _label(k, css="dim-label", wrap=False)
            lv = _label(v)
            lv.set_selectable(True)
            grid.attach(lk, 0, i, 1, 1)
            grid.attach(lv, 1, i, 1, 1)
        box.append(grid)
        return box


class SettingsApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.vikey.Settings",
                         flags=Gio.ApplicationFlags.FLAGS_NONE)

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = SettingsWindow(self)
        win.present()


def run():
    app = SettingsApp()
    return app.run([sys.argv[0]])


if __name__ == "__main__":
    sys.exit(run())
