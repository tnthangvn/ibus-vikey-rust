#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kiểm thử đầu-cuối qua ibus-daemon THẬT: đóng vai một ứng dụng (input context),
gửi phím tới engine 'vikey' và ghi lại chính xác những gì ứng dụng nhận được
(commit-text / update-preedit-text). Dùng để chứng minh không có duplicate text.

Chạy (cần ibus-daemon đang chạy và component vikey đã đăng ký):
    python3 tests/e2e_ibus.py
"""
import sys
import time

import gi

gi.require_version("IBus", "1.0")
from gi.repository import GLib, IBus  # noqa: E402

KEY = {
    "space": IBus.KEY_space, "enter": IBus.KEY_Return, "bs": IBus.KEY_BackSpace,
    "esc": IBus.KEY_Escape, "tab": IBus.KEY_Tab, "left": IBus.KEY_Left,
}


class App(object):
    def __init__(self, bus, name="vikey-e2e"):
        self.text = ""          # nội dung "ô nhập" của ứng dụng
        self.preedit = ""
        self.preedit_visible = False
        self.preedit_mode = None
        self.ic = bus.create_input_context(name)
        self.ic.set_capabilities(IBus.Capabilite.PREEDIT_TEXT | IBus.Capabilite.FOCUS | IBus.Capabilite.PROPERTY)
        self.ic.connect("commit-text", self._on_commit)
        self.ic.connect("update-preedit-text", self._on_preedit)
        self.ic.connect("update-preedit-text-with-mode", self._on_preedit_mode)
        self.ic.connect("hide-preedit-text", lambda *_a: self._set_preedit("", False))
        self.ic.connect("show-preedit-text", lambda *_a: self._set_preedit(self.preedit, True))
        self.ic.connect("forward-key-event", self._on_forward)
        self.ic.connect("delete-surrounding-text", self._on_delete)
        self.forwarded = []
        self.deletes = 0

    def _on_delete(self, _ic, offset, nchars):
        self.deletes += 1
        end = len(self.text) + offset
        self.text = self.text[:end] + self.text[end + nchars:]

    def _on_commit(self, _ic, text):
        self.text += text.get_text()

    def _on_preedit(self, _ic, text, _cursor, visible):
        self._set_preedit(text.get_text(), visible)

    def _on_preedit_mode(self, _ic, text, _cursor, visible, mode):
        self.preedit_mode = mode
        self._set_preedit(text.get_text(), visible)

    def _set_preedit(self, s, visible):
        self.preedit = s if visible else ""
        self.preedit_visible = visible

    def _on_forward(self, _ic, keyval, keycode, state):
        self.forwarded.append((keyval, state))

    def pump(self, t=0.05):
        end = time.time() + t
        ctx = GLib.MainContext.default()
        while time.time() < end:
            while ctx.pending():
                ctx.iteration(False)
            time.sleep(0.005)

    def key(self, keyval, state=0):
        handled = self.ic.process_key_event(keyval, 0, state)
        self.pump()
        if not handled:
            # ứng dụng tự xử lý phím
            if keyval == IBus.KEY_Return:
                self.text += "\n"
            elif keyval == IBus.KEY_BackSpace:
                self.text = self.text[:-1]
            else:
                uc = IBus.keyval_to_unicode(keyval)
                if isinstance(uc, int):
                    uc = chr(uc) if uc else ""
                if uc and ord(uc) >= 0x20 and not (state & IBus.ModifierType.CONTROL_MASK):
                    self.text += uc
        self.ic.process_key_event(keyval, 0, state | IBus.ModifierType.RELEASE_MASK)
        self.pump(0.01)
        return handled

    def type(self, s):
        for c in s:
            if c == " ":
                self.key(IBus.KEY_space)
            elif c == "\n":
                self.key(IBus.KEY_Return)
            else:
                self.key(IBus.unicode_to_keyval(c), IBus.ModifierType.SHIFT_MASK if c.isupper() else 0)

    def focus_in(self):
        self.ic.focus_in()
        self.pump(0.1)

    def focus_out(self):
        self.ic.focus_out()
        self.pump(0.15)

    def reset(self):
        self.ic.reset()
        self.pump(0.15)


def check(name, got, want, fails):
    ok = got == want
    print("%s %-45s %r" % ("PASS" if ok else "FAIL", name, got) + ("" if ok else "   (mong đợi %r)" % want))
    if not ok:
        fails.append(name)


def main():
    IBus.init()
    bus = IBus.Bus()
    if not bus.is_connected():
        print("Không kết nối được ibus-daemon")
        return 2
    fails = []

    app = App(bus)
    app.focus_in()
    app.ic.set_engine("vikey")
    app.pump(1.0)
    desc = app.ic.get_engine()
    print("engine:", desc.get_name() if desc else None)
    if not desc or desc.get_name() != "vikey":
        print("Không bật được engine vikey")
        return 2

    # 1. câu tiếng Việt thường
    app.type("Tieesng Vieejt raats hay.\n")
    check("câu tiếng Việt", app.text, "Tiếng Việt rất hay.\n", fails)
    check("preedit rỗng sau Enter", app.preedit, "", fails)

    # 2. lệnh terminal
    app.text = ""
    app.type("sudo apt install git\nls -la\n")
    check("lệnh terminal giữ nguyên", app.text, "sudo apt install git\nls -la\n", fails)

    # 3. backspace trong từ và ngoài từ
    app.text = ""
    app.type("vieets")
    check("preedit hiển thị", app.preedit, "viết", fails)
    app.key(IBus.KEY_BackSpace)
    check("backspace trong từ", app.preedit, "viêt", fails)
    app.type(" ")
    app.key(IBus.KEY_BackSpace)
    check("backspace ngoài từ về ứng dụng", app.text, "viêt", fails)

    # 4. mất focus khi đang gõ dở: IBus tự commit đúng 1 lần
    app.text = ""
    app.type("xin chaof")
    app.focus_out()
    app.focus_in()
    check("focus out commit 1 lần", app.text, "xin chào", fails)
    check("preedit rỗng sau focus out", app.preedit, "", fails)
    app.type(" banj")
    app.reset()
    check("reset (click chuột) commit 1 lần", app.text, "xin chào bạn", fails)
    app.type(" nhes")
    app.focus_out()
    app.focus_in()
    app.type(" tieeps tucj\n")
    check("gõ tiếp sau focus", app.text, "xin chào bạn nhé tiếp tục\n", fails)

    # 5. dấu câu, số
    app.text = ""
    app.type("chaof, banj! 123 a1b\n")
    check("dấu câu & số", app.text, "chào, bạn! 123 a1b\n", fails)

    # 6. Esc / Ctrl+C khi đang gõ dở
    app.text = ""
    app.type("abc")
    app.key(IBus.KEY_Escape)
    app.type("xyz")
    app.key(IBus.KEY_c, IBus.ModifierType.CONTROL_MASK)
    check("Esc/Ctrl+C commit rồi nhường phím", app.text, "abcxyz", fails)

    # 7. Ctrl+Shift bật/tắt
    app.text = ""
    app.type("vieet")
    app.key(IBus.KEY_Control_L, 0)
    app.ic.process_key_event(IBus.KEY_Shift_L, 0, IBus.ModifierType.CONTROL_MASK)
    app.pump()
    app.ic.process_key_event(IBus.KEY_Shift_L, 0, IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.SHIFT_MASK | IBus.ModifierType.RELEASE_MASK)
    app.pump()
    app.ic.process_key_event(IBus.KEY_Control_L, 0, IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.RELEASE_MASK)
    app.pump(0.2)
    app.type(" vieets")
    check("Ctrl+Shift tắt tiếng Việt", app.text, "viêt vieets", fails)
    app.key(IBus.KEY_Shift_L, 0)
    app.ic.process_key_event(IBus.KEY_Control_L, 0, IBus.ModifierType.SHIFT_MASK)
    app.pump()
    app.ic.process_key_event(IBus.KEY_Control_L, 0, IBus.ModifierType.SHIFT_MASK | IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.RELEASE_MASK)
    app.pump(0.2)
    app.type(" vieets\n")
    check("Ctrl+Shift bật lại", app.text, "viêt vieets viết\n", fails)

    # 8. Không bao giờ forward key giả
    check("không forward_key_event", app.forwarded, [], fails)

    # 9. Client kiểu GNOME Shell / GTK4: tự commit preedit (client_commit_preedit)
    if hasattr(app.ic, "set_client_commit_preedit"):
        app2 = App(bus, "vikey-e2e-ccp")
        app2.ic.set_client_commit_preedit(True)
        app2.focus_in()
        app2.ic.set_engine("vikey")
        app2.pump(0.5)

        def client_commit(a):
            # giống gnome-shell: khi focus_out/reset, client tự commit preedit nếu mode == COMMIT
            if a.preedit_visible and a.preedit and a.preedit_mode == IBus.PreeditFocusMode.COMMIT:
                a.text += a.preedit
            a._set_preedit("", False)

        app2.type("xin chaof")
        client_commit(app2)
        app2.focus_out()
        app2.focus_in()
        check("[ccp] focus out commit 1 lần", app2.text, "xin chào", fails)
        app2.type(" banj")
        client_commit(app2)
        app2.reset()
        check("[ccp] reset commit 1 lần", app2.text, "xin chào bạn", fails)
        app2.type(" nhes tieeps.\n")
        check("[ccp] gõ tiếp", app2.text, "xin chào bạn nhé tiếp.\n", fails)
        check("[ccp] nhận update-preedit-text-with-mode COMMIT", app2.preedit_mode, IBus.PreeditFocusMode.COMMIT, fails)

    # 10. Chế độ gõ trực tiếp (không gạch chân): đổi qua file cấu hình, engine nạp lại khi focus
    import json, os
    cfg_path = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "ibus-vikey", "config.json")
    os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
    def set_cfg(**kw):
        try:
            cur = json.load(open(cfg_path))
        except Exception:
            cur = {}
        cur.update(kw)
        json.dump(cur, open(cfg_path, "w"))
        time.sleep(0.05)
    set_cfg(direct_mode=True)
    app3 = App(bus, "vikey-e2e-direct")
    app3.focus_in()
    app3.ic.set_engine("vikey")
    app3.pump(0.5)
    app3.focus_out(); app3.focus_in()
    app3.type("Tieesng Vieejt raats hay.\n")
    check("[direct] câu tiếng Việt, không preedit", (app3.text, app3.preedit_visible), ("Tiếng Việt rất hay.\n", False), fails)
    app3.type("nguowif")
    app3.key(IBus.KEY_BackSpace)
    app3.key(IBus.KEY_BackSpace)
    app3.type(" xong\n")
    check("[direct] backspace trong từ", app3.text, "Tiếng Việt rất hay.\nngươ xong\n", fails)
    check("[direct] có dùng delete_surrounding_text", app3.deletes > 0, True, fails)
    set_cfg(direct_mode=False)
    app3.focus_out(); app3.focus_in()
    app3.text = ""
    app3.type("vieets ")
    check("[direct->preedit] nạp lại cấu hình", app3.text, "viết ", fails)

    # 11. Gõ tắt: sửa file macros.txt -> engine tự nạp lại khi focus
    macro_path = os.path.join(os.path.dirname(cfg_path), "macros.txt")
    old_macros = open(macro_path, encoding="utf-8").read() if os.path.exists(macro_path) else None
    with open(macro_path, "w", encoding="utf-8") as f:
        f.write("vn:Việt Nam\nhn:Hà Nội\nko:không\n")
    time.sleep(1.1)
    app3.focus_out(); app3.focus_in()
    app3.text = ""
    app3.type("vn, Hn! KO\nfile.vn ")
    check("[macro] bung viết tắt + chữ hoa", app3.text, "Việt Nam, Hà Nội! KHÔNG\nfile.vn ", fails)
    set_cfg(macros=False)
    app3.focus_out(); app3.focus_in()
    app3.text = ""
    app3.type("vn ")
    check("[macro] tắt gõ tắt", app3.text, "vn ", fails)
    set_cfg(macros=True, direct_mode=True)
    app3.focus_out(); app3.focus_in()
    app3.text = ""
    app3.type("xin chaof vn.\n")
    check("[macro+direct] bung viết tắt không preedit", app3.text, "xin chào Việt Nam.\n", fails)
    set_cfg(direct_mode=False)

    # 12. Kiểu gõ VNI + phím chuyển Alt+Z + gõ tắt khi tắt tiếng Việt
    set_cfg(method="vni", toggle_key="alt_z", macros_when_off=True)
    app3.focus_out(); app3.focus_in()
    app3.text = ""
    app3.type("Tie61ng Vie65t 123\n")
    check("[vni] gõ VNI qua cấu hình", app3.text, "Tiếng Việt 123\n", fails)
    app3.type("vie65t")
    app3.key(IBus.KEY_z, IBus.ModifierType.MOD1_MASK)      # Alt+Z -> tắt tiếng Việt
    app3.type(" vie65t vn ")
    check("[alt+z] tắt tiếng Việt, gõ tắt vẫn chạy", app3.text, "Tiếng Việt 123\nviệt vie65t Việt Nam ", fails)
    app3.key(IBus.KEY_z, IBus.ModifierType.MOD1_MASK)      # bật lại
    app3.type("vie65t\n")
    check("[alt+z] bật lại", app3.text, "Tiếng Việt 123\nviệt vie65t Việt Nam việt\n", fails)
    set_cfg(method="telex", toggle_key="ctrl_shift", macros_when_off=False)
    app3.focus_out(); app3.focus_in()

    # 13. Phím chuyển tuỳ chỉnh Ctrl+Shift+Space
    set_cfg(toggle_key="custom", toggle_custom="<Control><Shift>space")
    app3.focus_out(); app3.focus_in()
    app3.text = ""
    app3.type("vieet")
    app3.key(IBus.KEY_space, IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.SHIFT_MASK)
    app3.type(" vieets")
    app3.key(IBus.KEY_space, IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.SHIFT_MASK)
    app3.type(" vieets\n")
    check("[custom] Ctrl+Shift+Space bật/tắt", app3.text, "viêt vieets viết\n", fails)
    set_cfg(toggle_key="ctrl_shift")
    app3.focus_out(); app3.focus_in()
    if old_macros is None:
        os.remove(macro_path)
    else:
        open(macro_path, "w", encoding="utf-8").write(old_macros)

    print()
    if fails:
        print("THẤT BẠI: %d" % len(fails), fails)
        return 1
    print("TẤT CẢ ĐẠT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
