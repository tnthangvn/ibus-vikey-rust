#!/bin/bash
# Cài ViKey (bộ gõ tiếng Việt Telex cho IBus) trên Ubuntu 22.04 trở lên.
# Chạy KHÔNG kèm sudo:   ./install.sh
# (script tự gọi sudo khi cần; phần cấu hình GNOME phải chạy bằng user thường)
set -e
cd "$(dirname "$0")"

PREFIX=/usr/share/ibus-vikey
COMPONENT=/usr/share/ibus/component/vikey.xml
PYTHON=${PYTHON:-$(command -v python3)}

if [ "$(id -u)" = 0 ] && [ -z "$VIKEY_ALLOW_ROOT" ]; then
  echo "Vui lòng chạy ./install.sh bằng user thường (không sudo)."
  exit 1
fi

echo "==> [1/5] Cài gói phụ thuộc (ibus, python3-gi, gir1.2-ibus-1.0)"
sudo apt-get install -y ibus python3-gi gir1.2-ibus-1.0 gir1.2-glib-2.0 gir1.2-gtk-4.0 >/dev/null

echo "==> [2/5] Chép file vào $PREFIX"
sudo rm -rf "$PREFIX"
sudo mkdir -p "$PREFIX"
sudo cp -r vikey/. "$PREFIX"/
sudo find "$PREFIX" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
sudo chmod 755 "$PREFIX/main.py"
sed "s|@PYTHON@|$PYTHON|g; s|@PREFIX@|$PREFIX|g" vikey.xml.in | sudo tee "$COMPONENT" >/dev/null
sudo ln -sf "$PREFIX/main.py" /usr/local/bin/vikey
sed "s|@PYTHON@|$PYTHON|g; s|@PREFIX@|$PREFIX|g" vikey-settings.desktop.in | sudo tee /usr/share/applications/vikey-settings.desktop >/dev/null
sudo update-desktop-database /usr/share/applications >/dev/null 2>&1 || true

echo "==> [3/5] Đặt IBus làm khung nhập liệu mặc định (im-config)"
if command -v im-config >/dev/null 2>&1; then
  im-config -n ibus >/dev/null 2>&1 || true
fi

echo "==> [4/5] Khởi động lại IBus"
if pgrep -x ibus-daemon >/dev/null 2>&1; then
  ibus restart >/dev/null 2>&1 || true
else
  ibus-daemon -drx >/dev/null 2>&1 || true
fi
sleep 1

echo "==> [5/5] Thêm 'Tiếng Việt (ViKey)' vào Input Sources của GNOME (nếu có)"
if command -v gsettings >/dev/null 2>&1 && gsettings list-schemas 2>/dev/null | grep -q '^org.gnome.desktop.input-sources$'; then
  python3 - <<'PYEOF'
import ast, subprocess
SCHEMA = "org.gnome.desktop.input-sources"
def get_sources():
    out = subprocess.check_output(["gsettings", "get", SCHEMA, "sources"], text=True).strip()
    if out.startswith("@"):
        out = out.split(" ", 1)[1].strip()
    if out in ("", "[]"):
        return []
    return [tuple(x) for x in ast.literal_eval(out)]
try:
    src = get_sources()
    if ("ibus", "vikey") in src:
        print("    Đã có sẵn trong Input Sources.")
    else:
        if not any(t == "xkb" for t, _ in src):
            src.insert(0, ("xkb", "us"))
        src.append(("ibus", "vikey"))
        val = "[" + ", ".join("('%s', '%s')" % s for s in src) + "]"
        subprocess.check_call(["gsettings", "set", SCHEMA, "sources", val])
        print("    Đã thêm. Danh sách hiện tại: " + val)
    subprocess.call(["gsettings", "set", SCHEMA, "show-all-sources", "true"])
except Exception as e:  # noqa
    print("    Không tự thêm được (%s). Hãy thêm thủ công: Settings > Keyboard > Input Sources > + > Vietnamese > Tiếng Việt (ViKey)" % e)
PYEOF
else
  echo "    Không phải GNOME. Với KDE Plasma: System Settings > Keyboard > Virtual Keyboard > chọn 'IBus Wayland', rồi ibus-setup để thêm 'Tiếng Việt (ViKey)'."
fi

# Tạo bảng gõ tắt mẫu cho user hiện tại (nếu chưa có)
"$PYTHON" "$PREFIX/main.py" --macro init 2>/dev/null || true

cat <<EOF

Cài xong!
  * Chuyển bộ gõ: Super+Space (GNOME) hoặc bấm biểu tượng bàn phím trên thanh trên cùng.
  * Trong ViKey: bấm Ctrl+Shift (không kèm phím khác) để bật/tắt tiếng Việt tạm thời.
  * Gõ thử ngay trong terminal (không cần IBus):   vikey --test "tieesng vieejt"
  * Cửa sổ cài đặt: menu Vi/En > "Cài đặt ViKey…", hoặc gõ "ViKey" trong Activities, hoặc:  vikey --setup
  * Xem/đổi cấu hình bằng lệnh:                    vikey --config
  * Gõ tắt: sửa ~/.config/ibus-vikey/macros.txt hoặc  vikey --macro add vn "Việt Nam"
  * Nếu chưa thấy 'Tiếng Việt (ViKey)' trong danh sách: đăng xuất rồi đăng nhập lại.
EOF
