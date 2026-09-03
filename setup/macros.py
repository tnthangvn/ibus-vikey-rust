# -*- coding: utf-8 -*-
"""
macros.py - Bảng gõ tắt (giống "Bảng gõ tắt" của Unikey).

File: ~/.config/ibus-vikey/macros.txt, mỗi dòng  viết_tắt:nội_dung_đầy_đủ
  - dòng bắt đầu bằng # là chú thích
  - viết tắt chỉ gồm chữ cái (a-z), không phân biệt hoa/thường
  - nội dung có thể chứa dấu cách, dấu câu, tiếng Việt có dấu, cả dấu ':'

Khi gõ xong viết tắt rồi bấm space / dấu câu / Enter, ViKey thay bằng nội dung
đầy đủ. Chữ hoa được tự điều chỉnh: "vn" -> "Việt Nam", "Vn" -> "Việt Nam"
(viết hoa chữ đầu), "VN" -> "VIỆT NAM".
"""

import os
import time

from config import CONFIG_DIR

MACRO_FILE = os.path.join(CONFIG_DIR, "macros.txt")

DEFAULT_MACROS = """\
# Bảng gõ tắt ViKey - mỗi dòng:  viết_tắt:nội_dung_đầy_đủ
# Viết tắt chỉ gồm chữ cái, không phân biệt hoa/thường. Dòng bắt đầu bằng # bị bỏ qua.
# Sửa xong lưu file là dùng được ngay (không cần khởi động lại IBus).
# Xem nhanh:  vikey --macro        thêm:  vikey --macro add tphcm "Thành phố Hồ Chí Minh"
vn:Việt Nam
hn:Hà Nội
hcm:Hồ Chí Minh
tphcm:Thành phố Hồ Chí Minh
# ko:không
# dc:được
# ng:người
# email:ten.cua.ban@gmail.com
"""

_ALLOWED = frozenset("abcdefghijklmnopqrstuvwxyz")


def parse(text):
    """Trả về dict {viết_tắt_thường: nội_dung}. Bỏ qua dòng sai định dạng."""
    table = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if not key or not value or any(c not in _ALLOWED for c in key):
            continue
        table[key] = value
    return table


def adapt_case(typed, expansion):
    """Điều chỉnh hoa/thường của nội dung theo cách gõ viết tắt."""
    if len(typed) > 1 and typed.isupper():
        return expansion.upper()
    if typed[:1].isupper():
        return expansion[:1].upper() + expansion[1:]
    return expansion


class MacroTable(object):
    def __init__(self, path=MACRO_FILE, auto_reload=True):
        self.path = path
        self.table = {}
        self._mtime = None
        self._last_check = 0.0
        self.auto_reload = auto_reload
        self.reload()

    # ---------------------------------------------------------------- file
    def ensure_file(self):
        """Tạo file mẫu nếu chưa có. Trả về đường dẫn."""
        if not os.path.exists(self.path):
            try:
                os.makedirs(os.path.dirname(self.path), exist_ok=True)
                with open(self.path, "w", encoding="utf-8") as f:
                    f.write(DEFAULT_MACROS)
            except OSError:
                pass
        return self.path

    def _stat(self):
        try:
            return os.stat(self.path).st_mtime
        except OSError:
            return None

    def reload(self):
        self._mtime = self._stat()
        self._last_check = time.time()
        if self._mtime is None:
            self.table = parse(DEFAULT_MACROS)
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self.table = parse(f.read())
        except (OSError, UnicodeDecodeError):
            self.table = {}

    def maybe_reload(self, min_interval=1.0):
        """Nạp lại nếu file đổi (kiểm tra tối đa mỗi min_interval giây)."""
        if not self.auto_reload:
            return
        now = time.time()
        if now - self._last_check < min_interval:
            return
        self._last_check = now
        if self._stat() != self._mtime:
            self.reload()

    # ------------------------------------------------------------- tra cứu
    def lookup(self, typed):
        """typed: dãy phím thô của từ. Trả về nội dung đã chỉnh hoa/thường, hoặc None."""
        if not typed:
            return None
        exp = self.table.get(typed.lower())
        if exp is None:
            return None
        return adapt_case(typed, exp)

    # ------------------------------------------------------------ sửa bảng
    def add(self, key, value):
        key = key.strip().lower()
        value = value.strip()
        if not key or not value or any(c not in _ALLOWED for c in key):
            raise ValueError("Viết tắt chỉ gồm chữ cái a-z và nội dung không được rỗng")
        self.ensure_file()
        lines = []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
        except OSError:
            pass
        out, replaced = [], False
        for line in lines:
            s = line.strip()
            if s and not s.startswith("#") and ":" in s and s.split(":", 1)[0].strip().lower() == key:
                if not replaced:
                    out.append("%s:%s" % (key, value))
                    replaced = True
                continue
            out.append(line)
        if not replaced:
            out.append("%s:%s" % (key, value))
        self._write(out)

    def remove(self, key):
        key = key.strip().lower()
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
        except OSError:
            return False
        out, found = [], False
        for line in lines:
            s = line.strip()
            if s and not s.startswith("#") and ":" in s and s.split(":", 1)[0].strip().lower() == key:
                found = True
                continue
            out.append(line)
        if found:
            self._write(out)
        return found

    def _write(self, lines):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines).rstrip("\n") + "\n")
        self.reload()
