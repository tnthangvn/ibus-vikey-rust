# -*- coding: utf-8 -*-
"""Đọc/ghi cấu hình ~/.config/ibus-vikey/config.json"""

import json
import os

CONFIG_DIR = os.path.join(
    os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "ibus-vikey")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

# Các giá trị cho phép của từng khoá dạng lựa chọn
CHOICES = {
    # Kiểu gõ
    "method": ("telex", "vni", "both"),
    # Phím chuyển Việt/Anh
    "toggle_key": ("ctrl_shift", "alt_z", "custom", "none"),
    # Bảng mã xuất ra: Unicode dựng sẵn (NFC, mặc định) | Unicode tổ hợp (NFD)
    "charset": ("precomposed", "decomposed"),
}

CHOICE_LABELS = {
    "method": {"telex": "Telex", "vni": "VNI", "both": "Telex + VNI"},
    "toggle_key": {"ctrl_shift": "Ctrl+Shift", "alt_z": "Alt+Z", "custom": "Tuỳ chỉnh", "none": "Không dùng"},
    "charset": {"precomposed": "Unicode dựng sẵn", "decomposed": "Unicode tổ hợp"},
}

DEFAULTS = {
    # --- Cơ bản
    "method": "telex",
    "toggle_key": "ctrl_shift",
    # Tổ hợp phím chuyển tuỳ chỉnh (khi toggle_key = custom), dạng accelerator GTK
    "toggle_custom": "<Control><Shift>space",
    # Phím tắt bật/tắt "Không gạch chân" (direct_mode); rỗng = không dùng
    "direct_key": "",
    "charset": "precomposed",
    # Trạng thái tiếng Việt khi khởi động
    "enabled": True,
    # Khôi phục phím thô khi từ không phải tiếng Việt (windows, status, data...)
    "spell_check": True,
    # Đặt dấu kiểu mới: hoà, khoẻ, thuý (False = hòa, khỏe, thúy)
    "modern_tone": False,
    # Bỏ dấu tự do: gõ dd / aa ee oo ở cuối từ vẫn ăn (dend -> đen, tienge -> tiêng)
    "free_marking": False,
    # --- Gõ tắt
    "macros": True,
    # Gõ tắt cả khi đang tắt tiếng Việt (thay chữ bằng delete_surrounding_text)
    "macros_when_off": False,
    # --- Nâng cao
    # Gõ trực tiếp, KHÔNG gạch chân (không dùng preedit). Trong terminal có thể lặp chữ.
    "direct_mode": False,
    # Ghi nhật ký chẩn đoán vào ~/.cache/ibus-vikey/vikey.log
    "debug_log": False,
}

BOOL_KEYS = tuple(k for k, v in DEFAULTS.items() if isinstance(v, bool))
STRING_KEYS = ("toggle_custom", "direct_key")


def _coerce(key, value):
    if key in CHOICES:
        return value if value in CHOICES[key] else DEFAULTS[key]
    if key in STRING_KEYS:
        return str(value).strip() if value is not None else DEFAULTS[key]
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "on", "yes")
    return bool(value)


def load():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return cfg
    if not isinstance(data, dict):
        return cfg
    for k in DEFAULTS:
        if k in data:
            cfg[k] = _coerce(k, data[k])
    # tương thích bản cũ: ctrl_shift_toggle (bool) -> toggle_key
    if "toggle_key" not in data and "ctrl_shift_toggle" in data:
        cfg["toggle_key"] = "ctrl_shift" if data["ctrl_shift_toggle"] else "none"
    return cfg


def save(cfg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        out = {k: _coerce(k, cfg.get(k, DEFAULTS[k])) for k in DEFAULTS}
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except OSError:
        pass


def mtime():
    try:
        return os.stat(CONFIG_FILE).st_mtime
    except OSError:
        return 0.0


def describe(key, value):
    """Chuỗi hiển thị cho một giá trị."""
    if key in CHOICE_LABELS:
        return CHOICE_LABELS[key].get(value, str(value))
    if key in STRING_KEYS:
        return str(value)
    return "on" if value else "off"


def toggle_label(cfg):
    """Nhãn phím chuyển hiện tại, vd 'Ctrl+Shift', 'Alt+Z', 'Ctrl+Shift+Space'."""
    tk = cfg.get("toggle_key", DEFAULTS["toggle_key"])
    if tk == "custom":
        import hotkey
        return hotkey.label(cfg.get("toggle_custom", DEFAULTS["toggle_custom"]))
    return CHOICE_LABELS["toggle_key"][tk]
