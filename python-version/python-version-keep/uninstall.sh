#!/bin/bash
# Gỡ ViKey. Chạy KHÔNG kèm sudo: ./uninstall.sh
set -e
PREFIX=/usr/share/ibus-vikey
COMPONENT=/usr/share/ibus/component/vikey.xml

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
        print("Đã bỏ ViKey khỏi Input Sources.")
except Exception as e:  # noqa
    print("Không sửa được Input Sources:", e)
PYEOF
fi

sudo rm -f "$COMPONENT" /usr/local/bin/vikey /usr/share/applications/vikey-settings.desktop
sudo rm -rf "$PREFIX"
ibus restart >/dev/null 2>&1 || true
echo "Đã gỡ ViKey. Cấu hình cá nhân còn ở ~/.config/ibus-vikey (xoá nếu muốn)."
