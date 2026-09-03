#!/bin/bash
# =============================================================================
#  ViKey - GỠ SẠCH HOÀN TOÀN, không để lại rác.
#  Chạy KHÔNG kèm sudo:   ./uninstall.sh
#
#  Xoá: engine + lệnh vikey, component IBus, shortcut + icon hệ thống,
#       nguồn nhập trong GNOME, cache registry của IBus,
#       VÀ toàn bộ cấu hình cá nhân (~/.config/ibus-vikey: config.json,
#       bảng gõ tắt macros.txt).
#  Muốn GIỮ cấu hình/bảng gõ tắt để sau cài lại:  ./uninstall.sh --keep-config
# =============================================================================
set -e

PREFIX=/usr/share/ibus-vikey
COMPONENT=/usr/share/ibus/component/vikey.xml
DESKTOP=/usr/share/applications/vikey-settings.desktop
HICOLOR_ICON=/usr/share/icons/hicolor/scalable/apps/vikey.svg
KEEP_CONFIG=""
[ "$1" = "--keep-config" ] && KEEP_CONFIG=1

if [ "$(id -u)" = 0 ] && [ -z "$VIKEY_ALLOW_ROOT" ]; then
  echo "Vui lòng chạy ./uninstall.sh bằng user thường (không sudo)."
  exit 1
fi

echo "==> [1/4] Bỏ 'Tiếng Việt (ViKey)' khỏi Input Sources của GNOME (nếu có)"
if command -v gsettings >/dev/null 2>&1 && gsettings list-schemas 2>/dev/null | grep -q '^org.gnome.desktop.input-sources$'; then
  python3 - <<'PYEOF'
import ast, subprocess
SCHEMA = "org.gnome.desktop.input-sources"
try:
    out = subprocess.check_output(["gsettings", "get", SCHEMA, "sources"], text=True).strip()
    if out.startswith("@"):
        out = out.split(" ", 1)[1].strip()
    src = [tuple(x) for x in ast.literal_eval(out)] if out not in ("", "[]") else []
    new = [s for s in src if s != ("ibus", "vikey")]
    if new != src:
        val = "[" + ", ".join("('%s', '%s')" % s for s in new) + "]" if new else "[('xkb', 'us')]"
        subprocess.check_call(["gsettings", "set", SCHEMA, "sources", val])
        print("    Đã bỏ khỏi Input Sources.")
    else:
        print("    Không có trong Input Sources.")
except Exception as e:  # noqa
    print("    Không sửa được Input Sources:", e)
PYEOF
fi

echo "==> [2/4] Xoá file hệ thống (engine, lệnh vikey, shortcut, icon, component IBus)"
sudo rm -f "$COMPONENT" "$DESKTOP" "$HICOLOR_ICON" /usr/local/bin/vikey
sudo rm -rf "$PREFIX"
sudo update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
sudo gtk-update-icon-cache -f /usr/share/icons/hicolor >/dev/null 2>&1 || true

echo "==> [3/4] Xoá cache"
rm -rf "${XDG_CACHE_HOME:-$HOME/.cache}/ibus/bus"/*.registry \
       "${XDG_CACHE_HOME:-$HOME/.cache}/ibus/bus/registry" 2>/dev/null || true

if [ -n "$KEEP_CONFIG" ]; then
  echo "==> [4/4] GIỮ lại cấu hình cá nhân (~/.config/ibus-vikey) theo yêu cầu (--keep-config)."
else
  echo "==> [4/4] Xoá cấu hình cá nhân (~/.config/ibus-vikey: config.json + bảng gõ tắt)"
  rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/ibus-vikey"
fi

ibus restart >/dev/null 2>&1 || true

echo
echo "✔ Đã gỡ ViKey sạch sẽ, không còn file nào để lại."
[ -z "$KEEP_CONFIG" ] || echo "  (Cấu hình còn ở ~/.config/ibus-vikey do bạn chọn --keep-config)"
