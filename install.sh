#!/bin/bash
# =============================================================================
#  ViKey (Rust) - CÀI ĐẶT TRỌN GÓI
#  Chạy KHÔNG kèm sudo:   ./setup.sh      (script tự hỏi mật khẩu khi cần)
#
#  Làm tất cả trong một lệnh:
#    - cài gói phụ thuộc (ibus; GTK4-Python cho cửa sổ Cài đặt)
#    - cài engine + lệnh `vikey` + cửa sổ Cài đặt
#    - icon hệ thống (hicolor) + shortcut "ViKey" trong Activities
#    - xoá cache cũ (registry của IBus, __pycache__, bản cài cũ) để engine
#      hiện ra ngay, không dính cache bẩn
#    - đặt IBus làm khung nhập liệu, thêm vào Input Sources của GNOME
# =============================================================================
set -e
cd "$(dirname "$0")"

PREFIX=/usr/share/ibus-vikey
COMPONENT=/usr/share/ibus/component/vikey.xml
DESKTOP=/usr/share/applications/vikey-settings.desktop
HICOLOR=/usr/share/icons/hicolor/scalable/apps
BIN=bin/vikey-engine

if [ "$(id -u)" = 0 ] && [ -z "$VIKEY_ALLOW_ROOT" ]; then
  echo "Vui lòng chạy ./setup.sh bằng user thường (không sudo)."
  exit 1
fi

echo "==> [1/6] Cài gói phụ thuộc"
sudo apt-get install -y ibus >/dev/null
sudo apt-get install -y python3-gi gir1.2-gtk-4.0 >/dev/null 2>&1 || \
  echo "    (không cài được GTK4 Python - engine vẫn chạy, chỉ thiếu cửa sổ Cài đặt)"

echo "==> [2/6] Chuẩn bị binary vikey-engine"
if [ -x "$BIN" ] && "$BIN" --version >/dev/null 2>&1; then
  echo "    Dùng binary dựng sẵn ($("$BIN" --version))."
else
  echo "    Binary dựng sẵn không chạy được trên máy này -> tự biên dịch từ mã nguồn Rust."
  if ! command -v cargo >/dev/null 2>&1; then
    echo "    Chưa có Rust. Cài bằng:  sudo apt install cargo   (hoặc rustup: https://rustup.rs)"
    exit 1
  fi
  cargo build --release
  mkdir -p bin
  cp target/release/vikey-engine "$BIN"
fi

echo "==> [3/6] Dọn bản cũ + cache"
sudo rm -rf "$PREFIX"                                   # bản cài cũ (Python hoặc Rust)
sudo rm -f "$COMPONENT" "$DESKTOP" /usr/local/bin/vikey
rm -rf "${XDG_CACHE_HOME:-$HOME/.cache}/ibus/bus"/*.registry \
       "${XDG_CACHE_HOME:-$HOME/.cache}/ibus/bus/registry" 2>/dev/null || true
sudo rm -rf /root/.cache/ibus/bus/*.registry 2>/dev/null || true

echo "==> [4/6] Cài file vào $PREFIX + icon + shortcut"
sudo mkdir -p "$PREFIX"
sudo cp "$BIN" "$PREFIX/vikey-engine"
sudo cp -r icons setup "$PREFIX"/
sudo find "$PREFIX" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
sudo chmod 755 "$PREFIX/vikey-engine" "$PREFIX/setup/main.py"
sudo ln -sf "$PREFIX/vikey-engine" /usr/local/bin/vikey
sed "s|@PREFIX@|$PREFIX|g" vikey.xml.in | sudo tee "$COMPONENT" >/dev/null
# icon hệ thống (theme hicolor) để shortcut/desktop hiện icon chuẩn
sudo mkdir -p "$HICOLOR"
sudo cp icons/vikey.svg "$HICOLOR/vikey.svg"
sudo gtk-update-icon-cache -f /usr/share/icons/hicolor >/dev/null 2>&1 || true
sed "s|@PREFIX@|$PREFIX|g; s|^Icon=.*|Icon=vikey|" vikey-settings.desktop.in | sudo tee "$DESKTOP" >/dev/null
sudo update-desktop-database /usr/share/applications >/dev/null 2>&1 || true

echo "==> [5/6] Đặt IBus làm khung nhập liệu + khởi động lại IBus"
command -v im-config >/dev/null 2>&1 && im-config -n ibus >/dev/null 2>&1 || true
if pgrep -x ibus-daemon >/dev/null 2>&1; then
  ibus restart >/dev/null 2>&1 || true
else
  ibus-daemon -drx >/dev/null 2>&1 || true
fi
sleep 1

echo "==> [6/6] Thêm 'Tiếng Việt (ViKey)' vào Input Sources của GNOME (nếu có)"
if command -v gsettings >/dev/null 2>&1 && gsettings list-schemas 2>/dev/null | grep -q '^org.gnome.desktop.input-sources$'; then
  python3 - <<'PYEOF'
import ast, subprocess
SCHEMA = "org.gnome.desktop.input-sources"
try:
    out = subprocess.check_output(["gsettings", "get", SCHEMA, "sources"], text=True).strip()
    if out.startswith("@"):
        out = out.split(" ", 1)[1].strip()
    src = [tuple(x) for x in ast.literal_eval(out)] if out not in ("", "[]") else []
    if ("ibus", "vikey") not in src:
        if not any(t == "xkb" for t, _ in src):
            src.insert(0, ("xkb", "us"))
        src.append(("ibus", "vikey"))
        val = "[" + ", ".join("('%s', '%s')" % s for s in src) + "]"
        subprocess.check_call(["gsettings", "set", SCHEMA, "sources", val])
        print("    Đã thêm:", val)
    else:
        print("    Đã có sẵn trong Input Sources.")
    subprocess.call(["gsettings", "set", SCHEMA, "show-all-sources", "true"])
except Exception as e:  # noqa
    print("    Không tự thêm được (%s). Thêm thủ công: Settings > Keyboard > Input Sources > + > Vietnamese > Tiếng Việt (ViKey)" % e)
PYEOF
else
  echo "    Không phải GNOME. Với KDE Plasma: System Settings > Keyboard > Virtual Keyboard > 'IBus Wayland', rồi ibus-setup thêm 'Tiếng Việt (ViKey)'."
fi

# Bảng gõ tắt mẫu cho user hiện tại (nếu chưa có)
"$PREFIX/vikey-engine" --macro init >/dev/null 2>&1 || true

cat <<EOF

✔ Cài xong ViKey (Rust)!
  * Chuyển bộ gõ: Super+Space; bật/tắt tiếng Việt nhanh: Ctrl+Shift (đổi được trong Cài đặt).
  * Cửa sổ Cài đặt: gõ "ViKey" trong Activities, menu Vi/En > "Cài đặt ViKey…", hoặc:  vikey --setup
  * Dòng lệnh:  vikey --test "tieesng vieejt"  |  vikey --config  |  vikey --macro
  * Chưa thấy trong danh sách nguồn nhập? Đăng xuất rồi đăng nhập lại.
  * Gỡ sạch hoàn toàn:  ./uninstall.sh
EOF
