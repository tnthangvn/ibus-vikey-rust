# -*- coding: utf-8 -*-
"""
engine.py - Lớp IBus của ViKey.

Toàn bộ logic gõ nằm ở keyhandler.py / vnengine.py; file này chỉ chuyển đổi
giữa IBus và KeyHandler, đồng thời quản lý preedit / commit / menu.
"""

import os
import subprocess
import sys

import gi

gi.require_version("IBus", "1.0")
from gi.repository import IBus  # noqa: E402

import config  # noqa: E402
import hotkey  # noqa: E402
from keyhandler import KeyHandler  # noqa: E402
from macros import MacroTable  # noqa: E402

# Bảng gõ tắt dùng chung cho mọi input context (mỗi cửa sổ là một engine instance)
_MACROS = MacroTable()

ENGINE_NAME = "vikey"
ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")


def _t(s):
    return IBus.Text.new_from_string(s)


def _keyval_to_char(keyval):
    """keyval -> ký tự unicode ('' nếu không có). Tuỳ bản PyGObject, hàm
    keyval_to_unicode trả về str (gunichar) hoặc int."""
    uc = IBus.keyval_to_unicode(keyval)
    if not uc:
        return ""
    if isinstance(uc, int):
        return chr(uc)
    return uc if uc != "\x00" else ""


class ViKeyEngine(IBus.Engine):
    __gtype_name__ = "ViKeyEngine"

    def __init__(self, **kwargs):
        super(ViKeyEngine, self).__init__(**kwargs)
        self._cfg = config.load()
        self._cfg_mtime = config.mtime()
        self._handler = KeyHandler(macros=_MACROS, keyval_resolver=IBus.keyval_from_name,
                                   **self._handler_kwargs(self._cfg))
        self._handler.enabled = self._cfg["enabled"]
        self._preedit_visible = False
        self._build_props()

    @staticmethod
    def _handler_kwargs(cfg):
        return dict(
            spell_check=cfg["spell_check"],
            modern_tone=cfg["modern_tone"],
            direct_mode=cfg["direct_mode"],
            macros_enabled=cfg["macros"],
            macros_when_off=cfg["macros_when_off"],
            method=cfg["method"],
            toggle_key=cfg["toggle_key"],
            toggle_custom=cfg["toggle_custom"],
            charset=cfg["charset"],
        )

    # ------------------------------------------------------------ menu/props
    TOGGLES = (
        # (khoá cấu hình, nhãn, gợi ý)
        ("spell_check", "Kiểm tra chính tả (khôi phục phím với từ sai)",
         "Từ không phải tiếng Việt (windows, status...) sẽ giữ nguyên phím gõ"),
        ("modern_tone", "Đặt dấu kiểu mới (hoà, khoẻ, thuý)", "Tắt: hòa, khỏe, thúy"),
        ("macros", "Gõ tắt (vn → Việt Nam...)",
         "Bung viết tắt khi bấm space/dấu câu/Enter. Bảng: ~/.config/ibus-vikey/macros.txt"),
        ("direct_mode", "Không gạch chân (gõ trực tiếp – TẮT khi dùng terminal)",
         "Không dùng preedit; sửa chữ bằng delete_surrounding_text. Có thể lặp chữ ở terminal/app không hỗ trợ"),
    )
    RADIOS = (
        ("method", "Kiểu gõ"),
        ("toggle_key", "Phím chuyển Việt/Anh"),
    )

    def _build_props(self):
        self._props = IBus.PropList()
        self._toggle_props = {}
        self._radio_props = {}     # key -> (menu prop, {value: sub prop})

        self._prop_mode = IBus.Property.new(
            "InputMode", IBus.PropType.NORMAL, _t(""), None,
            _t("Bấm để bật/tắt tiếng Việt"),
            True, True, IBus.PropState.UNCHECKED, None)
        self._props.append(self._prop_mode)

        for key, label in self.RADIOS:
            sub = IBus.PropList()
            subs = {}
            for value in config.CHOICES[key]:
                p = IBus.Property.new(
                    "%s:%s" % (key, value), IBus.PropType.RADIO, _t(config.CHOICE_LABELS[key][value]),
                    None, _t(""), True, True, IBus.PropState.UNCHECKED, None)
                sub.append(p)
                subs[value] = p
            menu = IBus.Property.new(key, IBus.PropType.MENU, _t(label), None, _t(""),
                                     True, True, IBus.PropState.UNCHECKED, sub)
            self._props.append(menu)
            self._radio_props[key] = (menu, subs)

        for key, label, tip in self.TOGGLES:
            p = IBus.Property.new(key, IBus.PropType.TOGGLE, _t(label), None, _t(tip),
                                  True, True, IBus.PropState.UNCHECKED, None)
            self._props.append(p)
            self._toggle_props[key] = p

        self._props.append(IBus.Property.new(
            "setup", IBus.PropType.NORMAL, _t("Cài đặt ViKey…"),
            None, _t("Mở cửa sổ cài đặt: tuỳ chọn và bảng gõ tắt"),
            True, True, IBus.PropState.UNCHECKED, None))

        self._sync_props()

    def _current_values(self):
        h = self._handler
        return {
            "spell_check": h.engine.spell_check, "modern_tone": h.engine.modern_tone,
            "macros": h.macros_enabled, "direct_mode": h.direct_mode,
            "method": h.engine.method, "toggle_key": h.toggle_key,
        }

    def _sync_props(self):
        on = self._handler.enabled
        tl = config.toggle_label({"toggle_key": self._handler.toggle_key, "toggle_custom": self._handler.toggle_custom})
        hint = "" if self._handler.toggle_key == "none" else " – " + tl
        self._prop_mode.set_label(_t(("Tiếng Việt: BẬT" if on else "Tiếng Việt: TẮT (đang gõ tiếng Anh)") + hint))
        self._prop_mode.set_symbol(_t("Vi" if on else "En"))
        self._prop_mode.set_icon(os.path.join(ICON_DIR, "vikey-vi.svg" if on else "vikey-en.svg"))
        vals = self._current_values()
        checked = lambda b: IBus.PropState.CHECKED if b else IBus.PropState.UNCHECKED  # noqa: E731
        for key, p in self._toggle_props.items():
            p.set_state(checked(vals[key]))
        for key, (menu, subs) in self._radio_props.items():
            cur_label = tl if key == "toggle_key" else config.CHOICE_LABELS[key][vals[key]]
            menu.set_label(_t("%s: %s" % (dict(self.RADIOS)[key], cur_label)))
            for value, p in subs.items():
                p.set_state(checked(value == vals[key]))
                if key == "toggle_key" and value == "custom":
                    p.set_label(_t("Tuỳ chỉnh (%s)" % hotkey.label(self._handler.toggle_custom, IBus.keyval_from_name)))

    def _update_props(self):
        self._sync_props()
        self.update_property(self._prop_mode)
        for p in self._toggle_props.values():
            self.update_property(p)
        for menu, subs in self._radio_props.values():
            self.update_property(menu)
            for p in subs.values():
                self.update_property(p)

    def _save_cfg(self):
        h = self._handler
        self._cfg.update(
            spell_check=h.engine.spell_check,
            modern_tone=h.engine.modern_tone,
            enabled=h.enabled,
            direct_mode=h.direct_mode,
            macros=h.macros_enabled,
            macros_when_off=h.macros_when_off,
            method=h.engine.method,
            toggle_key=h.toggle_key,
            toggle_custom=h.toggle_custom,
            charset=h.charset,
        )
        config.save(self._cfg)
        self._cfg_mtime = config.mtime()

    def _reload_cfg_if_changed(self):
        m = config.mtime()
        if m == self._cfg_mtime:
            return
        self._cfg_mtime = m
        self._cfg = config.load()
        pending = self._handler.configure(**self._handler_kwargs(self._cfg))
        self._apply_result_commit(pending)
        # trạng thái Việt/Anh dùng chung cho mọi cửa sổ (bật/tắt ở cửa sổ này -> cửa sổ khác theo)
        if bool(self._cfg["enabled"]) != self._handler.enabled:
            self._apply_result_commit(self._handler.set_enabled(self._cfg["enabled"]))
        self._update_props()

    def do_property_activate(self, prop_name, state):
        checked = state == IBus.PropState.CHECKED
        if prop_name == "InputMode":
            self._apply_result_commit(self._handler.set_enabled(not self._handler.enabled))
        elif prop_name == "spell_check":
            self._handler.configure(spell_check=checked)
        elif prop_name == "modern_tone":
            self._handler.configure(modern_tone=checked)
        elif prop_name == "direct_mode":
            self._apply_result_commit(self._handler.configure(direct_mode=checked))
        elif prop_name == "macros":
            self._handler.configure(macros_enabled=checked)
        elif ":" in prop_name and prop_name.split(":", 1)[0] in self._radio_props:
            key, value = prop_name.split(":", 1)
            if not checked or value not in config.CHOICES[key]:
                return
            self._apply_result_commit(self._handler.configure(**{key: value}))
        elif prop_name == "setup":
            try:
                subprocess.Popen([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py"),
                                  "--setup"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                pass
            return
        else:
            return
        self._save_cfg()
        self._update_props()

    # --------------------------------------------------------- preedit/commit
    def _show_preedit(self, text):
        if not text:
            if self._preedit_visible:
                self.hide_preedit_text()
                self._preedit_visible = False
            return
        t = _t(text)
        n = len(text)
        t.append_attribute(IBus.AttrType.UNDERLINE, IBus.AttrUnderline.SINGLE, 0, n)
        # COMMIT: khi mất focus / reset, IBus (hoặc GNOME Shell) tự commit phần
        # đang gõ đúng một lần; engine không commit lại -> không duplicate.
        self.update_preedit_text_with_mode(t, n, True, IBus.PreeditFocusMode.COMMIT)
        self._preedit_visible = True

    def _apply_result_commit(self, text, delete=0):
        """Ẩn preedit TRƯỚC rồi mới commit, để không còn preedit nào có thể bị
        commit lần nữa khi đổi focus. `delete` > 0 (chế độ gõ trực tiếp): xoá
        bấy nhiêu ký tự trước con trỏ bằng delete_surrounding_text rồi mới commit."""
        if self._preedit_visible:
            self.hide_preedit_text()
            self._preedit_visible = False
        if delete > 0:
            self.delete_surrounding_text(-delete, delete)
        if text:
            self.commit_text(_t(text))

    # ------------------------------------------------------------- sự kiện
    def do_process_key_event(self, keyval, keycode, state):
        ch = _keyval_to_char(keyval)
        r = self._handler.handle(keyval, state, ch)
        if r.commit is not None or r.delete:
            self._apply_result_commit(r.commit, r.delete)
        if r.preedit is not None:
            self._show_preedit(r.preedit)
        if r.toggled:
            self._save_cfg()
            self._update_props()
        return bool(r.handled)

    def do_focus_in(self):
        self._reload_cfg_if_changed()
        _MACROS.maybe_reload(min_interval=0.0)
        self.register_properties(self._props)

    def do_focus_out(self):
        # IBus đã commit preedit (chế độ COMMIT); chỉ cần quên từ đang soạn.
        self._handler.clear()
        self._preedit_visible = False

    def do_reset(self):
        self._handler.clear()
        self._preedit_visible = False

    def do_enable(self):
        self._reload_cfg_if_changed()

    def do_disable(self):
        self._handler.clear()
        self._preedit_visible = False


class ViKeyFactory(IBus.Factory):
    def __init__(self, bus):
        self._bus = bus
        self._counter = 0
        super(ViKeyFactory, self).__init__(connection=bus.get_connection(), object_path=IBus.PATH_FACTORY)

    def do_create_engine(self, engine_name):
        if engine_name != ENGINE_NAME:
            return None
        self._counter += 1
        path = "/org/freedesktop/IBus/Engine/ViKey/%d" % self._counter
        return ViKeyEngine(engine_name=engine_name, connection=self._bus.get_connection(), object_path=path)


def make_component(version, prefix):
    component = IBus.Component.new(
        "org.freedesktop.IBus.ViKey", "ViKey - bộ gõ tiếng Việt", version, "GPL-3.0",
        "ViKey", "https://github.com/", "", "ibus-vikey")
    desc = IBus.EngineDesc.new(
        ENGINE_NAME, "Tiếng Việt (ViKey)", "Bộ gõ tiếng Việt kiểu Telex", "vi", "GPL-3.0",
        "ViKey", os.path.join(prefix, "icons", "vikey.svg"), "default")
    component.add_engine(desc)
    return component
