# -*- coding: utf-8 -*-
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vikey"))

from keyhandler import (  # noqa: E402
    KeyHandler, KEY_BACKSPACE, KEY_RETURN, KEY_ESCAPE, KEY_SHIFT_L, KEY_CONTROL_L, KEY_TAB,
    SHIFT_MASK, CONTROL_MASK, RELEASE_MASK, MOD1_MASK,
)
from macros import MacroTable, parse, adapt_case  # noqa: E402
import tempfile  # noqa: E402


def make_macros(text):
    f = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
    f.write(text)
    f.close()
    return MacroTable(path=f.name, auto_reload=False)


class FakeApp(object):
    """Mô phỏng ứng dụng + IBus: ghi lại text nhận được để phát hiện duplicate."""

    def __init__(self, **kw):
        self.h = KeyHandler(**kw)
        self.text = ""       # nội dung đã commit vào ứng dụng
        self.preedit = ""    # preedit đang hiển thị

    def key(self, keyval, state=0, ch=""):
        r = self.h.handle(keyval, state, ch)
        if r.delete:
            self.preedit = ""
            self.text = self.text[:-r.delete]
        if r.commit is not None:
            # engine luôn xoá preedit trước khi commit
            self.preedit = ""
            self.text += r.commit
        if r.preedit is not None:
            self.preedit = r.preedit
        if not r.handled and not (state & RELEASE_MASK):
            # ứng dụng tự xử lý phím được trả về
            if keyval == KEY_RETURN:
                self.text += "\n"
            elif keyval == KEY_BACKSPACE:
                self.text = self.text[:-1]
            elif ch and ord(ch) >= 0x20 and not (state & CONTROL_MASK):
                self.text += ch
        return r

    def type(self, s):
        for c in s:
            if c == "\n":
                self.key(KEY_RETURN)
            else:
                self.key(ord(c), 0, c)

    def focus_out(self):
        # IBus (chế độ preedit COMMIT) tự commit preedit, rồi gọi engine.focus_out
        self.text += self.preedit
        self.preedit = ""
        self.h.clear()


class TestKeyHandler(unittest.TestCase):
    def test_sentence(self):
        app = FakeApp()
        app.type("Tieesng Vieejt raats hay.\n")
        self.assertEqual(app.text, "Tiếng Việt rất hay.\n")
        self.assertEqual(app.preedit, "")

    def test_terminal_command(self):
        app = FakeApp()
        app.type("sudo apt install git\n")
        self.assertEqual(app.text, "sudo apt install git\n")
        app.type("ls -la /home\n")
        self.assertEqual(app.text, "sudo apt install git\nls -la /home\n")

    def test_backspace_in_and_out_of_word(self):
        app = FakeApp()
        app.type("vieets")
        self.assertEqual(app.preedit, "viết")
        app.key(KEY_BACKSPACE)
        self.assertEqual(app.preedit, "viêt")
        app.type(" ")
        self.assertEqual(app.text, "viêt ")
        r = app.key(KEY_BACKSPACE)   # không còn preedit -> trả cho ứng dụng
        self.assertFalse(r.handled)
        self.assertEqual(app.text, "viêt")

    def test_focus_out_no_duplicate(self):
        app = FakeApp()
        app.type("xin chaof")
        self.assertEqual(app.text, "xin ")
        self.assertEqual(app.preedit, "chào")
        app.focus_out()
        self.assertEqual(app.text, "xin chào")
        app.type(" banj")
        app.focus_out()
        self.assertEqual(app.text, "xin chào bạn")

    def test_escape_and_ctrl(self):
        app = FakeApp()
        app.type("abc")
        r = app.key(KEY_ESCAPE)
        self.assertFalse(r.handled)
        self.assertEqual(r.commit, "abc")
        app.type("xyz")
        r = app.key(ord("c"), CONTROL_MASK, "c")   # Ctrl+C
        self.assertFalse(r.handled)
        self.assertEqual(app.text, "abcxyz")

    def test_ctrl_shift_toggle(self):
        app = FakeApp()
        app.type("vieet")
        app.key(KEY_CONTROL_L, 0)
        app.key(KEY_SHIFT_L, CONTROL_MASK)
        app.key(KEY_SHIFT_L, CONTROL_MASK | SHIFT_MASK | RELEASE_MASK)
        r = app.key(KEY_CONTROL_L, CONTROL_MASK | RELEASE_MASK)
        self.assertFalse(app.h.enabled)
        self.assertEqual(app.text, "viêt")
        app.type(" vieets")
        self.assertEqual(app.text, "viêt vieets")
        # bật lại
        app.key(KEY_SHIFT_L, 0)
        app.key(KEY_CONTROL_L, SHIFT_MASK)
        app.key(KEY_CONTROL_L, SHIFT_MASK | CONTROL_MASK | RELEASE_MASK)
        self.assertTrue(app.h.enabled)
        app.type(" vieets ")
        self.assertEqual(app.text, "viêt vieets viết ")

    def test_ctrl_shift_with_other_key_does_not_toggle(self):
        app = FakeApp()
        app.key(KEY_CONTROL_L, 0)
        app.key(KEY_SHIFT_L, CONTROL_MASK)
        app.key(ord("C"), CONTROL_MASK | SHIFT_MASK, "C")     # Ctrl+Shift+C (copy)
        app.key(ord("C"), CONTROL_MASK | SHIFT_MASK | RELEASE_MASK, "C")
        app.key(KEY_SHIFT_L, CONTROL_MASK | SHIFT_MASK | RELEASE_MASK)
        app.key(KEY_CONTROL_L, CONTROL_MASK | RELEASE_MASK)
        self.assertTrue(app.h.enabled)

    def test_punctuation_committed_once(self):
        app = FakeApp()
        app.type("chaof, banj!")
        self.assertEqual(app.text, "chào, bạn!")
        self.assertEqual(app.preedit, "")

    def test_direct_mode_no_preedit(self):
        app = FakeApp(direct_mode=True)
        app.type("Tieesng Vieejt raats hay.\n")
        self.assertEqual(app.text, "Tiếng Việt rất hay.\n")
        self.assertEqual(app.preedit, "")
        app.text = ""
        app.type("nguowif")
        self.assertEqual(app.text, "người")
        app.key(KEY_BACKSPACE)
        self.assertEqual(app.text, "ngươi")
        app.key(KEY_BACKSPACE)
        self.assertEqual(app.text, "ngươ")
        app.key(KEY_BACKSPACE)
        self.assertEqual(app.text, "nguo")   # bỏ phím w -> "nguo"
        app.type(" tools status\n")
        self.assertEqual(app.text, "nguo tools status\n")

    def test_direct_mode_switch_mid_word(self):
        app = FakeApp()
        app.type("vieet")
        self.assertEqual(app.preedit, "viêt")
        pending = app.h.configure(direct_mode=True)
        self.assertEqual(pending, "viêt")
        app.text += pending
        app.type("s ")
        self.assertEqual(app.text, "viêts ")

    def test_digits_break_word(self):
        app = FakeApp()
        app.type("abc123 x2")
        self.assertEqual(app.text, "abc123 x2")

    def test_vni_method(self):
        app = FakeApp(method="vni")
        app.type("Tie61ng Vie65t 123 a1 x2\n")
        self.assertEqual(app.text, "Tiếng Việt 123 á x2\n")
        app.text = ""
        app.type("vieets ")                 # Telex không có tác dụng ở chế độ VNI
        self.assertEqual(app.text, "vieets ")
        app.text = ""
        app.type("ngu7o72i d9i")
        app.key(KEY_RETURN)
        self.assertEqual(app.text, "người đi\n")

    def test_both_methods(self):
        app = FakeApp(method="both")
        app.type("vieets ngu7o72i ")
        self.assertEqual(app.text, "viết người ")

    def test_alt_z_toggle(self):
        app = FakeApp(toggle_key="alt_z")
        app.type("vieet")
        r = app.key(ord("z"), MOD1_MASK, "z")
        self.assertTrue(r.handled and r.toggled)
        self.assertFalse(app.h.enabled)
        self.assertEqual(app.text, "viêt")
        app.type(" vieets")
        self.assertEqual(app.text, "viêt vieets")
        app.key(ord("z"), MOD1_MASK, "z")
        app.type(" vieets ")
        self.assertEqual(app.text, "viêt vieets viết ")
        # Ctrl+Shift không còn tác dụng
        app.key(KEY_CONTROL_L, 0)
        app.key(KEY_SHIFT_L, CONTROL_MASK)
        app.key(KEY_SHIFT_L, CONTROL_MASK | SHIFT_MASK | RELEASE_MASK)
        app.key(KEY_CONTROL_L, CONTROL_MASK | RELEASE_MASK)
        self.assertTrue(app.h.enabled)

    def test_custom_hotkey_ctrl_shift_space(self):
        app = FakeApp(toggle_key="custom", toggle_custom="<Control><Shift>space")
        app.type("vieet")
        r = app.key(0x20, CONTROL_MASK | SHIFT_MASK, " ")
        self.assertTrue(r.handled and r.toggled)
        self.assertFalse(app.h.enabled)
        self.assertEqual(app.text, "viêt")            # không chèn dấu cách
        app.type(" vieets")
        self.assertEqual(app.text, "viêt vieets")
        app.key(0x20, CONTROL_MASK | SHIFT_MASK, " ")
        self.assertTrue(app.h.enabled)
        app.type(" vieets ")
        self.assertEqual(app.text, "viêt vieets viết ")
        # Ctrl+Shift rồi thả (không kèm phím) không còn tác dụng
        app.key(KEY_CONTROL_L, 0)
        app.key(KEY_SHIFT_L, CONTROL_MASK)
        app.key(KEY_SHIFT_L, CONTROL_MASK | SHIFT_MASK | RELEASE_MASK)
        app.key(KEY_CONTROL_L, CONTROL_MASK | RELEASE_MASK)
        self.assertTrue(app.h.enabled)
        # Space thường vẫn là dấu cách
        app.type("a b ")
        self.assertEqual(app.text, "viêt vieets viết a b ")

    def test_custom_hotkey_variants(self):
        app = FakeApp(toggle_key="custom", toggle_custom="<Shift>F12")
        app.key(0xFFC9, SHIFT_MASK, "")
        self.assertFalse(app.h.enabled)
        app.h.configure(toggle_custom="<Alt>grave")
        app.key(0x60, MOD1_MASK, "`")
        self.assertTrue(app.h.enabled)
        app.h.configure(toggle_custom="<Control><Shift>z")
        app.key(ord("Z"), CONTROL_MASK | SHIFT_MASK, "Z")   # Shift làm keyval thành Z hoa
        self.assertFalse(app.h.enabled)
        app.key(ord("Z"), CONTROL_MASK | SHIFT_MASK | RELEASE_MASK, "Z")
        self.assertFalse(app.h.enabled)

    def test_decomposed_charset(self):
        import unicodedata
        app = FakeApp(charset="decomposed")
        app.type("vieets ")
        self.assertEqual(app.text, unicodedata.normalize("NFD", "viết "))
        self.assertNotEqual(app.text, "viết ")
        app2 = FakeApp(charset="decomposed", direct_mode=True)
        app2.type("vieets ")
        self.assertEqual(app2.text, unicodedata.normalize("NFD", "viết "))
        app2.type("nguowif")
        app2.key(KEY_BACKSPACE)
        app2.type(" ")
        self.assertEqual(app2.text, unicodedata.normalize("NFD", "viết ngươi "))


MACROS = "vn:Việt Nam\nhn:Hà Nội\nko:không\nemail:ten@gmail.com\n# bo:bỏ qua\nbad key:x\n:x\n"


class TestMacros(unittest.TestCase):
    def test_parse(self):
        t = parse(MACROS)
        self.assertEqual(t, {"vn": "Việt Nam", "hn": "Hà Nội", "ko": "không", "email": "ten@gmail.com"})

    def test_adapt_case(self):
        self.assertEqual(adapt_case("vn", "Việt Nam"), "Việt Nam")
        self.assertEqual(adapt_case("Vn", "việt nam"), "Việt nam")
        self.assertEqual(adapt_case("VN", "Việt Nam"), "VIỆT NAM")
        self.assertEqual(adapt_case("K", "không"), "Không")

    def test_expand_on_space_punct_enter_tab(self):
        app = FakeApp(macros=make_macros(MACROS))
        app.type("vn, hn! ko\n")
        self.assertEqual(app.text, "Việt Nam, Hà Nội! không\n")
        app.text = ""
        app.type("VN")
        app.key(KEY_TAB)
        self.assertEqual(app.text, "VIỆT NAM")

    def test_no_expand_on_escape_or_arrow(self):
        app = FakeApp(macros=make_macros(MACROS))
        app.type("vn")
        app.key(KEY_ESCAPE)
        self.assertEqual(app.text, "vn")
        app.type(" vn")
        app.key(0xFF51)   # Left
        self.assertEqual(app.text, "vn vn")

    def test_no_expand_inside_token(self):
        app = FakeApp(macros=make_macros(MACROS))
        app.type("file.vn ")
        self.assertEqual(app.text, "file.vn ")
        app.type("a-vn ")
        self.assertEqual(app.text, "file.vn a-vn ")
        app.type("(vn) ")
        self.assertEqual(app.text, "file.vn a-vn (Việt Nam) ")

    def test_preedit_shows_typed_word_not_expansion(self):
        app = FakeApp(macros=make_macros(MACROS))
        app.type("vn")
        self.assertEqual(app.preedit, "vn")
        app.type(" ")
        self.assertEqual(app.text, "Việt Nam ")
        self.assertEqual(app.preedit, "")

    def test_macros_disabled(self):
        app = FakeApp(macros=make_macros(MACROS), macros_enabled=False)
        app.type("vn ")
        self.assertEqual(app.text, "vn ")

    def test_direct_mode_expand(self):
        app = FakeApp(macros=make_macros(MACROS), direct_mode=True)
        app.type("vn ")
        self.assertEqual(app.text, "Việt Nam ")
        app.type("tphcm ")     # không có trong bảng -> giữ nguyên
        self.assertEqual(app.text, "Việt Nam tphcm ")
        app.type("Ko")
        app.key(KEY_RETURN)
        self.assertEqual(app.text, "Việt Nam tphcm Không\n")

    def test_backspace_then_expand(self):
        app = FakeApp(macros=make_macros(MACROS))
        app.type("vnx")
        app.key(KEY_BACKSPACE)
        app.type(" ")
        self.assertEqual(app.text, "Việt Nam ")

    def test_macros_when_vietnamese_off(self):
        app = FakeApp(macros=make_macros(MACROS), macros_when_off=True)
        app.h.set_enabled(False)
        app.type("vn ")                 # chữ đã vào app từng phím -> xoá 2 rồi commit
        self.assertEqual(app.text, "Việt Nam ")
        app.type("hello vn")
        app.key(KEY_RETURN)
        self.assertEqual(app.text, "Việt Nam hello Việt Nam\n")
        app.type("file.vn ")
        self.assertEqual(app.text, "Việt Nam hello Việt Nam\nfile.vn ")
        app.type("vnx")
        app.key(KEY_BACKSPACE)
        app.type(" ")
        self.assertEqual(app.text, "Việt Nam hello Việt Nam\nfile.vn Việt Nam ")
        app2 = FakeApp(macros=make_macros(MACROS))   # mặc định: tắt tiếng Việt thì không gõ tắt
        app2.h.set_enabled(False)
        app2.type("vn ")
        self.assertEqual(app2.text, "vn ")

    def test_add_remove_reload(self):
        m = make_macros(MACROS)
        m.add("Tp", "Thành phố")
        self.assertEqual(m.lookup("tp"), "Thành phố")
        self.assertEqual(m.lookup("TP"), "THÀNH PHỐ")
        m.add("vn", "Việt Nam ơi")
        self.assertEqual(m.lookup("vn"), "Việt Nam ơi")
        self.assertTrue(m.remove("hn"))
        self.assertIsNone(m.lookup("hn"))
        self.assertFalse(m.remove("hn"))
        with self.assertRaises(ValueError):
            m.add("a b", "x")



if __name__ == "__main__":
    unittest.main()
