# -*- coding: utf-8 -*-
"""
hotkey.py - Phân tích tổ hợp phím dạng accelerator của GTK ("<Control><Shift>space")
mà không phụ thuộc GTK/IBus, để KeyHandler so khớp phím chuyển Việt/Anh tuỳ chỉnh.
"""

# modifier mask (giống IBus.ModifierType / GDK)
SHIFT_MASK = 1 << 0
LOCK_MASK = 1 << 1
CONTROL_MASK = 1 << 2
MOD1_MASK = 1 << 3      # Alt
MOD2_MASK = 1 << 4      # NumLock
MOD4_MASK = 1 << 6      # Super (xkb)
SUPER_MASK = 1 << 26
HYPER_MASK = 1 << 27
META_MASK = 1 << 28

_MOD_NAMES = {
    "shift": SHIFT_MASK, "shft": SHIFT_MASK,
    "control": CONTROL_MASK, "ctrl": CONTROL_MASK, "ctl": CONTROL_MASK, "primary": CONTROL_MASK,
    "alt": MOD1_MASK, "mod1": MOD1_MASK,
    "super": SUPER_MASK, "mod4": SUPER_MASK, "win": SUPER_MASK,
    "hyper": HYPER_MASK, "meta": META_MASK,
}

# keysym của một số phím hay dùng (tên theo GDK/X11)
_KEY_NAMES = {
    "space": 0x20, "tab": 0xFF09, "return": 0xFF0D, "enter": 0xFF0D, "escape": 0xFF1B,
    "backspace": 0xFF08, "delete": 0xFFFF, "insert": 0xFF63, "home": 0xFF50, "end": 0xFF57,
    "page_up": 0xFF55, "page_down": 0xFF56, "prior": 0xFF55, "next": 0xFF56,
    "left": 0xFF51, "up": 0xFF52, "right": 0xFF53, "down": 0xFF54,
    "pause": 0xFF13, "print": 0xFF61, "menu": 0xFF67, "scroll_lock": 0xFF14,
    "caps_lock": 0xFFE5, "num_lock": 0xFF7F,
    "grave": 0x60, "asciitilde": 0x7E, "minus": 0x2D, "equal": 0x3D, "plus": 0x2B,
    "bracketleft": 0x5B, "bracketright": 0x5D, "backslash": 0x5C, "bar": 0x7C,
    "semicolon": 0x3B, "colon": 0x3A, "apostrophe": 0x27, "quotedbl": 0x22,
    "comma": 0x2C, "period": 0x2E, "slash": 0x2F, "less": 0x3C, "greater": 0x3E,
    "question": 0x3F, "exclam": 0x21, "at": 0x40, "numbersign": 0x23, "dollar": 0x24,
    "percent": 0x25, "asciicircum": 0x5E, "ampersand": 0x26, "asterisk": 0x2A,
    "parenleft": 0x28, "parenright": 0x29, "underscore": 0x5F,
    "kp_space": 0xFF80, "kp_enter": 0xFF8D, "kp_add": 0xFFAB, "kp_subtract": 0xFFAD,
}
for _i in range(1, 25):
    _KEY_NAMES["f%d" % _i] = 0xFFBE + _i - 1

_MODIFIER_KEYVALS = frozenset(
    list(range(0xFFE1, 0xFFEF)) + [0xFE03, 0xFF7F, 0xFFE5])

_LABELS = {
    SHIFT_MASK: "Shift", CONTROL_MASK: "Ctrl", MOD1_MASK: "Alt", SUPER_MASK: "Super",
    HYPER_MASK: "Hyper", META_MASK: "Meta",
}
_ORDER = (CONTROL_MASK, MOD1_MASK, SUPER_MASK, HYPER_MASK, META_MASK, SHIFT_MASK)

RELEVANT_MASK = SHIFT_MASK | CONTROL_MASK | MOD1_MASK | MOD4_MASK | SUPER_MASK | HYPER_MASK | META_MASK


class Hotkey(object):
    """Tổ hợp phím đã phân tích. `keyval` None nghĩa là chỉ có modifier (vd Ctrl+Shift)."""

    __slots__ = ("mods", "keyval", "name", "text")

    def __init__(self, mods, keyval, name, text):
        self.mods = mods
        self.keyval = keyval
        self.name = name
        self.text = text

    def matches(self, keyval, state):
        if self.keyval is None:
            return False
        st = state & RELEVANT_MASK
        if st & MOD4_MASK:                       # Super theo xkb -> gộp về SUPER_MASK
            st = (st & ~MOD4_MASK) | SUPER_MASK
        if st != self.mods:
            return False
        if keyval == self.keyval:
            return True
        # chữ cái: Shift/CapsLock làm keyval thành chữ hoa
        if 0x20 <= keyval < 0x7F and 0x20 <= self.keyval < 0x7F:
            return chr(keyval).lower() == chr(self.keyval).lower()
        return False

    def label(self):
        parts = [_LABELS[m] for m in _ORDER if self.mods & m]
        if self.name:
            parts.append(self.name[0].upper() + self.name[1:] if len(self.name) > 1 else self.name.upper())
        return "+".join(parts)


def parse(text, resolver=None):
    """'<Control><Shift>space' -> Hotkey. resolver(name) -> keyval cho tên phím lạ (vd IBus.keyval_from_name).
    Trả về None nếu chuỗi không hợp lệ."""
    if not text:
        return None
    s = text.strip()
    mods = 0
    while s.startswith("<"):
        end = s.find(">")
        if end < 0:
            return None
        name = s[1:end].strip().lower()
        s = s[end + 1:].strip()
        if name not in _MOD_NAMES:
            return None
        mods |= _MOD_NAMES[name]
    key = s.strip()
    if not key:
        return Hotkey(mods, None, "", text) if mods else None
    kl = key.lower()
    keyval = None
    if len(key) == 1:
        keyval = ord(kl)
    elif kl in _KEY_NAMES:
        keyval = _KEY_NAMES[kl]
    elif resolver is not None:
        try:
            v = resolver(key)
            keyval = v if v and v != 0xFFFFFF else None
        except Exception:  # noqa
            keyval = None
    if keyval is None or keyval in _MODIFIER_KEYVALS:
        return None
    return Hotkey(mods, keyval, key, text)


def label(text, resolver=None):
    hk = parse(text, resolver)
    return hk.label() if hk else text


# Tổ hợp đã bị trình duyệt / desktop / ô nhập GTK chiếm (so theo nhãn chuẩn hoá).
TAKEN = {
    "Ctrl+Shift+A": "Chrome: tìm thẻ",
    "Ctrl+Shift+B": "Chrome: thanh dấu trang",
    "Ctrl+Shift+C": "Chrome: chọn phần tử để kiểm tra",
    "Ctrl+Shift+D": "Chrome: lưu tất cả thẻ vào dấu trang",
    "Ctrl+Shift+G": "Chrome: tìm ngược",
    "Ctrl+Shift+I": "Chrome: DevTools",
    "Ctrl+Shift+J": "Chrome: DevTools Console",
    "Ctrl+Shift+M": "Chrome: đổi hồ sơ người dùng",
    "Ctrl+Shift+N": "Chrome: cửa sổ ẩn danh",
    "Ctrl+Shift+O": "Chrome: trình quản lý dấu trang",
    "Ctrl+Shift+P": "Chrome: in bằng hộp thoại hệ thống",
    "Ctrl+Shift+R": "Chrome: tải lại bỏ qua cache",
    "Ctrl+Shift+T": "Chrome: mở lại thẻ vừa đóng",
    "Ctrl+Shift+V": "Chrome: dán không định dạng",
    "Ctrl+Shift+W": "Chrome: đóng cửa sổ",
    "Ctrl+Shift+Delete": "Chrome: xoá dữ liệu duyệt web",
    "Ctrl+Shift+Tab": "Chrome: thẻ trước đó",
    "Ctrl+Shift+U": "GTK/IBus: nhập ký tự Unicode",
    "Ctrl+Shift+E": "GTK/IBus: bảng emoji",
    "Ctrl+Shift+Z": "ô nhập: làm lại (redo)",
    "Ctrl+Alt+T": "GNOME: mở terminal",
    "Ctrl+Alt+D": "GNOME: hiện màn hình nền",
    "Ctrl+Alt+Delete": "GNOME: đăng xuất",
    "Ctrl+Shift+Alt+R": "GNOME: quay màn hình",
    "Alt+F2": "GNOME: chạy lệnh",
    "Alt+Space": "GNOME: menu cửa sổ",
}


def conflict(text, resolver=None):
    """Tổ hợp có đụng phím tắt phổ biến không? -> tên hành động, hoặc None."""
    return TAKEN.get(label(text, resolver))
