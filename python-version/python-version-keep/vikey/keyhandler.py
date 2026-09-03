# -*- coding: utf-8 -*-
"""
keyhandler.py - Lớp xử lý phím độc lập với IBus (để có thể unit-test).

Quy tắc chống duplicate text:
  * KHÔNG bao giờ gửi Backspace giả hay forward_key_event ký tự đã gõ.
  * Từ đang soạn chỉ nằm trong preedit; khi kết thúc từ, commit ĐÚNG MỘT LẦN
    rồi xoá preedit. Preedit dùng chế độ COMMIT để IBus/GNOME Shell tự commit
    phần đang gõ khi mất focus, engine không commit lần thứ hai.
  * Ký tự kết thúc từ có thể in được (space, dấu câu, số...) được commit chung
    với từ trong cùng một lần commit -> không có chuyện ký tự tới trước từ.
  * Phím không in được (Enter, Tab, mũi tên, Esc, Ctrl+..) : commit từ rồi trả
    phím về cho ứng dụng xử lý (return False) -> Enter trong terminal, Esc trong
    vim... hoạt động bình thường.
"""

import unicodedata

import hotkey
from vnengine import VnEngine

try:
    from macros import MacroTable
except ImportError:  # pragma: no cover
    MacroTable = None

# keysym (giống IBus.KEY_*)
KEY_BACKSPACE = 0xFF08
KEY_TAB = 0xFF09
KEY_RETURN = 0xFF0D
KEY_ESCAPE = 0xFF1B
KEY_KP_ENTER = 0xFF8D
KEY_SHIFT_L, KEY_SHIFT_R = 0xFFE1, 0xFFE2
KEY_CONTROL_L, KEY_CONTROL_R = 0xFFE3, 0xFFE4
KEY_CAPS_LOCK = 0xFFE5
KEY_META_L, KEY_META_R = 0xFFE7, 0xFFE8
KEY_ALT_L, KEY_ALT_R = 0xFFE9, 0xFFEA
KEY_SUPER_L, KEY_SUPER_R = 0xFFEB, 0xFFEC
KEY_HYPER_L, KEY_HYPER_R = 0xFFED, 0xFFEE
KEY_ISO_LEVEL3_SHIFT = 0xFE03
KEY_NUM_LOCK = 0xFF7F

SHIFT_KEYS = (KEY_SHIFT_L, KEY_SHIFT_R)
CTRL_KEYS = (KEY_CONTROL_L, KEY_CONTROL_R)
MODIFIER_KEYS = SHIFT_KEYS + CTRL_KEYS + (
    KEY_CAPS_LOCK, KEY_META_L, KEY_META_R, KEY_ALT_L, KEY_ALT_R, KEY_SUPER_L,
    KEY_SUPER_R, KEY_HYPER_L, KEY_HYPER_R, KEY_ISO_LEVEL3_SHIFT, KEY_NUM_LOCK,
)

# modifier mask (giống IBus.ModifierType)
SHIFT_MASK = 1 << 0
LOCK_MASK = 1 << 1
CONTROL_MASK = 1 << 2
MOD1_MASK = 1 << 3      # Alt
MOD4_MASK = 1 << 6      # Super (xkb)
SUPER_MASK = 1 << 26
HYPER_MASK = 1 << 27
META_MASK = 1 << 28
RELEASE_MASK = 1 << 30

SHORTCUT_MASK = CONTROL_MASK | MOD1_MASK | MOD4_MASK | SUPER_MASK | HYPER_MASK | META_MASK

ASCII_LETTERS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
DIGITS = frozenset("0123456789")
KEY_z, KEY_Z = 0x7A, 0x5A

TOGGLE_KEYS = ("ctrl_shift", "alt_z", "custom", "none")
CHARSETS = ("precomposed", "decomposed")   # Unicode dựng sẵn (NFC) | Unicode tổ hợp (NFD)


class Result(object):
    """Kết quả xử lý một phím."""

    __slots__ = ("handled", "commit", "preedit", "toggled", "delete")

    def __init__(self, handled=False, commit=None, preedit=None, toggled=False, delete=0):
        self.handled = handled    # True: engine đã "ăn" phím; False: trả phím cho ứng dụng
        self.commit = commit      # chuỗi cần commit (None: không commit)
        self.preedit = preedit    # chuỗi preedit mới ('' = ẩn; None: không đổi)
        self.toggled = toggled    # vừa bật/tắt tiếng Việt bằng Ctrl+Shift
        self.delete = delete      # (chế độ gõ trực tiếp) số ký tự cần xoá trước con trỏ TRƯỚC khi commit

    def __repr__(self):
        return "Result(handled=%r, commit=%r, preedit=%r, toggled=%r, delete=%r)" % (
            self.handled, self.commit, self.preedit, self.toggled, self.delete)


class KeyHandler(object):
    def __init__(self, spell_check=True, modern_tone=False, ctrl_shift_toggle=True, direct_mode=False,
                 macros_enabled=True, macros=None, method="telex", toggle_key=None,
                 macros_when_off=False, charset="precomposed", toggle_custom="<Control><Shift>space",
                 keyval_resolver=None):
        self.engine = VnEngine(spell_check=spell_check, modern_tone=modern_tone, method=method)
        self.enabled = True
        # phím chuyển Việt/Anh: "ctrl_shift" (giống Unikey), "alt_z", "none"
        if toggle_key is None:
            toggle_key = "ctrl_shift" if ctrl_shift_toggle else "none"
        self.toggle_key = toggle_key if toggle_key in TOGGLE_KEYS else "ctrl_shift"
        self.keyval_resolver = keyval_resolver      # tên phím lạ -> keyval (vd IBus.keyval_from_name)
        self.toggle_custom = toggle_custom
        self._hotkey = hotkey.parse(toggle_custom, keyval_resolver)
        # gõ tắt cả khi đang tắt tiếng Việt (dùng delete_surrounding_text để thay chữ)
        self.macros_when_off = bool(macros_when_off)
        self._shadow = ""         # (khi tắt tiếng Việt) các chữ cái vừa gõ, để nhận diện viết tắt
        self.charset = charset if charset in CHARSETS else "precomposed"
        # direct_mode: KHÔNG dùng preedit (không gạch chân). Chữ được gửi thẳng vào
        # ứng dụng; khi từ đổi dạng thì xoá phần khác biệt bằng delete_surrounding_text
        # rồi commit phần mới. Chỉ an toàn với ứng dụng hỗ trợ surrounding text
        # (GTK/Qt/LibreOffice/Firefox...), KHÔNG nên dùng trong terminal.
        self.direct_mode = direct_mode
        self._sent = ""           # (direct_mode) phần của từ hiện tại đã gửi vào ứng dụng
        self._pending_toggle = False
        # gõ tắt
        self.macros_enabled = macros_enabled
        self.macros = macros if macros is not None else (MacroTable() if MacroTable else None)
        # ký tự đã kết thúc từ TRƯỚC (để không bung gõ tắt giữa "file.vn", "a-vn"...)
        self._last_boundary = None

    # ------------------------------------------------------------- cấu hình
    @property
    def ctrl_shift_toggle(self):
        return self.toggle_key == "ctrl_shift"

    @ctrl_shift_toggle.setter
    def ctrl_shift_toggle(self, value):
        self.toggle_key = "ctrl_shift" if value else "none"

    def configure(self, spell_check=None, modern_tone=None, ctrl_shift_toggle=None, direct_mode=None,
                  macros_enabled=None, method=None, toggle_key=None, macros_when_off=None, charset=None,
                  toggle_custom=None):
        """Trả về chuỗi cần commit nếu việc đổi chế độ buộc phải kết thúc từ đang dở."""
        pending = ""
        if toggle_custom is not None and toggle_custom != self.toggle_custom:
            self.toggle_custom = toggle_custom
            self._hotkey = hotkey.parse(toggle_custom, self.keyval_resolver)
        if macros_enabled is not None:
            self.macros_enabled = bool(macros_enabled)
        if macros_when_off is not None:
            self.macros_when_off = bool(macros_when_off)
            self._shadow = ""
        if spell_check is not None:
            self.engine.spell_check = spell_check
        if modern_tone is not None:
            self.engine.modern_tone = modern_tone
        if ctrl_shift_toggle is not None:
            self.ctrl_shift_toggle = ctrl_shift_toggle
        if toggle_key is not None and toggle_key in TOGGLE_KEYS:
            self.toggle_key = toggle_key
        if method is not None and method != self.engine.method:
            pending = self._flush()
            self.engine.method = method if method in ("telex", "vni", "both") else "telex"
        if charset is not None and charset in CHARSETS and charset != self.charset:
            pending = pending or self._flush()
            self.charset = charset
        if direct_mode is not None and bool(direct_mode) != self.direct_mode:
            pending = pending or self._flush()
            self.direct_mode = bool(direct_mode)
        return pending

    def _out(self, text):
        """Chuỗi xuất ra ứng dụng theo bảng mã đã chọn."""
        if self.charset == "decomposed":
            return unicodedata.normalize("NFD", text)
        return text

    def set_enabled(self, enabled):
        """Bật/tắt tiếng Việt. Trả về chuỗi cần commit (từ đang dở), có thể rỗng."""
        pending = self._flush()
        self._shadow = ""
        self.enabled = bool(enabled)
        return pending

    # ------------------------------------------------------------ tiện ích
    def preedit(self):
        return "" if self.direct_mode else self.engine.text()

    def is_composing(self):
        return not self.engine.is_empty()

    def clear(self):
        """Bỏ từ đang soạn KHÔNG commit (dùng ở focus_out/reset: IBus đã commit preedit)."""
        self.engine.reset()
        self._sent = ""
        self._shadow = ""
        self._last_boundary = None

    # ------------------------------------------------------------- gõ tắt
    _MACRO_OK_BEFORE = frozenset([None, " ", "\n", "\t", "(", "[", "{", "\"", "'", "\u201c", "\u2018"])

    def _macro_expansion(self, typed=None):
        """Nội dung gõ tắt cho từ đang soạn (hoặc chuỗi `typed`), hoặc None."""
        if typed is None:
            if self.engine.is_empty():
                return None
            typed = self.engine.raw()
        if not self.macros_enabled or self.macros is None or not typed:
            return None
        if self._last_boundary not in self._MACRO_OK_BEFORE:
            return None
        self.macros.maybe_reload()
        exp = self.macros.lookup(typed)
        return self._out(exp) if exp is not None else None

    def _finish_word(self, allow_macro):
        """Kết thúc từ đang soạn. Trả về (số_ký_tự_cần_xoá, chuỗi_cần_commit)."""
        expansion = self._macro_expansion() if allow_macro else None
        if self.direct_mode:
            sent = self._sent
            self.engine.reset()
            self._sent = ""
            if expansion is not None:
                return len(sent), expansion
            return 0, ""
        text = self._out(self.engine.text()) if expansion is None else expansion
        self.engine.reset()
        self._sent = ""
        return 0, text

    def _flush(self):
        """Kết thúc từ đang dở. Trả về phần cần commit (ở chế độ gõ trực tiếp thì
        chữ đã nằm trong ứng dụng rồi nên trả về rỗng)."""
        text = "" if self.direct_mode else self._out(self.engine.text())
        self.engine.reset()
        self._sent = ""
        return text

    def _direct_update(self):
        """(direct_mode) So sánh từ mới với phần đã gửi, trả về Result xoá/commit phần khác."""
        new = self._out(self.engine.text())
        old = self._sent
        n = 0
        while n < len(old) and n < len(new) and old[n] == new[n]:
            n += 1
        self._sent = new
        delete, insert = len(old) - n, new[n:]
        if delete == 1 and not insert:
            return Result(False)   # chỉ cần xoá 1 ký tự: để ứng dụng tự xử lý Backspace
        return Result(True, commit=insert or None, delete=delete)

    # -------------------------------------------------------------- xử lý
    def handle(self, keyval, state, ch):
        """
        keyval: keysym; state: modifier mask; ch: ký tự unicode tương ứng ('' nếu không có).
        """
        released = bool(state & RELEASE_MASK)

        # --- Alt+Z bật/tắt tiếng Việt
        if (self.toggle_key == "alt_z" and not released and keyval in (KEY_z, KEY_Z)
                and state & MOD1_MASK and not state & (CONTROL_MASK | SUPER_MASK | MOD4_MASK)):
            self._pending_toggle = False
            commit = self.set_enabled(not self.enabled)
            return Result(True, commit=commit or None, preedit="", toggled=True)

        # --- tổ hợp phím tuỳ chỉnh (vd Ctrl+Shift+Space)
        if self.toggle_key == "custom" and self._hotkey is not None and keyval not in MODIFIER_KEYS:
            if self._hotkey.matches(keyval, state & ~RELEASE_MASK):
                self._pending_toggle = False
                if released:
                    return Result(True)      # nuốt cả sự kiện nhả phím
                commit = self.set_enabled(not self.enabled)
                return Result(True, commit=commit or None, preedit="", toggled=True)

        # --- Ctrl+Shift (không kèm phím khác) để bật/tắt tiếng Việt, giống Unikey
        if keyval in MODIFIER_KEYS:
            if self.toggle_key != "ctrl_shift":
                return Result(False)
            if not released:
                if keyval in SHIFT_KEYS and state & CONTROL_MASK:
                    self._pending_toggle = True
                elif keyval in CTRL_KEYS and state & SHIFT_MASK:
                    self._pending_toggle = True
                else:
                    self._pending_toggle = False
            elif self._pending_toggle and keyval in SHIFT_KEYS + CTRL_KEYS:
                self._pending_toggle = False
                commit = self.set_enabled(not self.enabled)
                return Result(False, commit=commit or None, preedit="", toggled=True)
            return Result(False)
        self._pending_toggle = False

        if released:
            return Result(False)
        if not self.enabled:
            return self._handle_disabled(keyval, state, ch)

        # --- tổ hợp phím tắt (Ctrl/Alt/Super + ...): commit từ dở rồi nhường phím
        if state & SHORTCUT_MASK:
            return self._commit_and_pass()

        if keyval == KEY_BACKSPACE:
            if not self.is_composing():
                return Result(False)
            self.engine.backspace()
            if self.direct_mode:
                r = self._direct_update()
                if self.engine.is_empty():
                    self._sent = ""
                return r
            return Result(True, preedit=self.engine.text())

        if keyval in (KEY_RETURN, KEY_KP_ENTER, KEY_TAB):
            return self._commit_and_pass(allow_macro=True, boundary="\n")

        if keyval == KEY_ESCAPE:
            return self._commit_and_pass()

        if ch and (ch in ASCII_LETTERS or (ch in DIGITS and self.engine.accepts_digit())):
            self.engine.process_key(ch)
            if self.direct_mode:
                return self._direct_update()
            return Result(True, preedit=self.engine.text())

        if ch and ord(ch) >= 0x20 and ch != "\x7f":
            # ký tự in được khác (space, số, dấu câu, ký tự unicode...)
            if not self.is_composing():
                self._last_boundary = ch
                return Result(False)
            delete, text = self._finish_word(allow_macro=True)
            self._last_boundary = ch
            if self.direct_mode and not text:
                return Result(False)      # chữ đã trong ứng dụng, nhường phím này
            return Result(True, commit=text + ch, preedit="", delete=delete)

        # phím chức năng, mũi tên, Home/End, Delete, F1..F12 ...
        return self._commit_and_pass()

    def _handle_disabled(self, keyval, state, ch):
        """Đang tắt tiếng Việt: mọi phím đi thẳng vào ứng dụng. Nếu bật 'gõ tắt khi
        tắt tiếng Việt' thì theo dõi các chữ cái vừa gõ để bung viết tắt."""
        if not (self.macros_when_off and self.macros_enabled and self.macros is not None):
            return Result(False)
        if state & SHORTCUT_MASK:
            self._shadow = ""
            self._last_boundary = None
            return Result(False)
        if ch and ch in ASCII_LETTERS:
            self._shadow += ch
            return Result(False)
        if keyval == KEY_BACKSPACE:
            self._shadow = self._shadow[:-1]
            return Result(False)
        boundary = None
        if keyval in (KEY_RETURN, KEY_KP_ENTER, KEY_TAB):
            boundary = "\n"
        elif ch and ord(ch) >= 0x20 and ch != "\x7f":
            boundary = ch
        else:
            self._shadow = ""
            self._last_boundary = None
            return Result(False)
        exp = self._macro_expansion(self._shadow) if self._shadow else None
        n = len(self._shadow)
        self._shadow = ""
        self._last_boundary = boundary
        if exp is None:
            return Result(False)
        if boundary == "\n":
            return Result(False, commit=exp, delete=n)
        return Result(True, commit=exp + ch, delete=n)

    def _commit_and_pass(self, allow_macro=False, boundary=None):
        """Kết thúc từ đang dở (nếu có) rồi nhường phím cho ứng dụng."""
        if not self.is_composing():
            self._last_boundary = boundary
            return Result(False)
        delete, text = self._finish_word(allow_macro)
        self._last_boundary = boundary
        return Result(False, commit=text or None, preedit="", delete=delete)
