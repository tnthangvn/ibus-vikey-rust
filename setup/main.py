#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ViKey - Bộ gõ tiếng Việt (Telex) cho IBus.

Cách dùng:
  main.py --ibus            được ibus-daemon gọi (qua file component XML)
  main.py --standalone      chạy thử tay, tự đăng ký component với ibus-daemon
  main.py --setup           mở cửa sổ Cài đặt (GTK4)
  main.py --config          xem cấu hình
  main.py --config KEY GIÁ_TRỊ   (vd: method vni | toggle_key custom | toggle_custom "<Control><Shift>space")
  main.py --test "tieesng vieejt"   gõ thử trong terminal, không cần IBus
  main.py --macro                   xem bảng gõ tắt
  main.py --macro add vn "Việt Nam" thêm/sửa một viết tắt
  main.py --macro del vn            xoá một viết tắt
  main.py --macro edit              mở file bảng gõ tắt bằng trình soạn thảo
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

VERSION = "1.4.0"


def cmd_test(args):
    from vnengine import type_word
    import config as cfgmod
    cfg = cfgmod.load()
    kw = dict(spell_check=cfg["spell_check"], modern_tone=cfg["modern_tone"], method=cfg["method"])
    words = " ".join(args).split() if args else []
    if not words:
        print("Gõ phím (%s) rồi Enter (Ctrl+D để thoát):" % cfgmod.describe("method", cfg["method"]))
        for line in sys.stdin:
            print("  ".join(type_word(w, **kw) for w in line.split()))
        return 0
    print(" ".join(type_word(w, **kw) for w in words))
    return 0


def cmd_macro(args):
    from macros import MacroTable
    m = MacroTable()
    if not args or args[0] in ("list", "ls"):
        print("File: %s%s" % (m.path, "" if os.path.exists(m.path) else "  (chưa có, đang dùng bảng mẫu)"))
        if not m.table:
            print("  (trống)")
        for k in sorted(m.table):
            print("  %-12s -> %s" % (k, m.table[k]))
        return 0
    cmd = args[0]
    if cmd == "add" and len(args) >= 3:
        try:
            m.add(args[1], " ".join(args[2:]))
        except ValueError as e:
            print("Lỗi:", e)
            return 2
        print("Đã thêm: %s -> %s" % (args[1].lower(), " ".join(args[2:])))
        return 0
    if cmd in ("del", "rm", "remove") and len(args) == 2:
        print("Đã xoá." if m.remove(args[1]) else "Không thấy viết tắt '%s'." % args[1])
        return 0
    if cmd == "init":
        print("Bảng gõ tắt:", m.ensure_file())
        return 0
    if cmd == "edit":
        import subprocess
        path = m.ensure_file()
        editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
        if sys.stdout.isatty() and editor:
            return subprocess.call([editor, path])
        subprocess.Popen(["xdg-open", path])
        print("Đang mở", path)
        return 0
    print('Dùng: vikey --macro [list | add VIẾT_TẮT NỘI_DUNG... | del VIẾT_TẮT | edit]')
    return 2


def cmd_config(args):
    import config as cfgmod
    cfg = cfgmod.load()
    if not args:
        print("File: %s" % cfgmod.CONFIG_FILE)
        for k in cfgmod.DEFAULTS:
            extra = ""
            if k in cfgmod.CHOICES:
                extra = "   (%s)" % " | ".join(cfgmod.CHOICES[k])
            shown = cfgmod.describe(k, cfg[k])
            if k == "toggle_custom":
                shown = "%s  (%s)" % (cfg[k], cfgmod.toggle_label({"toggle_key": "custom", "toggle_custom": cfg[k]}))
            print("  %-16s %-18s%s" % (k, shown, extra))
        return 0
    if len(args) != 2 or args[0] not in cfgmod.DEFAULTS:
        print("Dùng: vikey --config KEY GIÁ_TRỊ")
        print("  KEY bật/tắt : %s  (on|off)" % ", ".join(cfgmod.BOOL_KEYS))
        for k, choices in cfgmod.CHOICES.items():
            print("  %-12s: %s" % (k, " | ".join(choices)))
        return 2
    key, val = args[0], args[1].strip()
    if key in cfgmod.STRING_KEYS:
        if key == "toggle_custom":
            import hotkey
            if hotkey.parse(val) is None or hotkey.parse(val).keyval is None:
                print('Tổ hợp không hợp lệ. Ví dụ: "<Control><Shift>space", "<Alt>grave", "<Super>z", "<Shift>F12"')
                return 2
        cfg[key] = val
        cfgmod.save(cfg)
        print("Đã lưu %s = %s (%s)" % (key, val, cfgmod.toggle_label({"toggle_key": "custom", "toggle_custom": val})))
        return 0
    val = val.lower()
    if key in cfgmod.CHOICES:
        if val not in cfgmod.CHOICES[key]:
            print("Giá trị cho %s phải là: %s" % (key, " | ".join(cfgmod.CHOICES[key])))
            return 2
        cfg[key] = val
    else:
        if val not in ("on", "off", "true", "false", "1", "0", "yes", "no"):
            print("Giá trị cho %s phải là on|off" % key)
            return 2
        cfg[key] = val in ("on", "true", "1", "yes")
    cfgmod.save(cfg)
    print("Đã lưu %s = %s (áp dụng khi focus vào ô nhập tiếp theo)" % (key, cfgmod.describe(key, cfg[key])))
    return 0


def run_engine(exec_by_ibus):
    import gi
    gi.require_version("IBus", "1.0")
    gi.require_version("GLib", "2.0")
    from gi.repository import GLib, IBus

    import engine as eng

    IBus.init()
    bus = IBus.Bus()
    if not bus.is_connected():
        sys.stderr.write("ViKey: không kết nối được ibus-daemon. Hãy chạy: ibus-daemon -drx\n")
        return 1

    mainloop = GLib.MainLoop()
    bus.connect("disconnected", lambda *_a: mainloop.quit())

    factory = eng.ViKeyFactory(bus)
    _keep = factory  # noqa: F841  (giữ tham chiếu)

    if exec_by_ibus:
        bus.request_name("org.freedesktop.IBus.ViKey", 0)
    else:
        bus.register_component(eng.make_component(VERSION, HERE))
        print("ViKey đang chạy ở chế độ standalone. Chọn 'Tiếng Việt (ViKey)' trong IBus để gõ thử.")

    mainloop.run()
    return 0


def cmd_setup():
    try:
        import settings
    except (ImportError, ValueError) as e:
        sys.stderr.write("Không mở được cửa sổ cài đặt (cần gir1.2-gtk-4.0): %s\n"
                         "Bạn vẫn có thể dùng: vikey --config / vikey --macro\n" % e)
        return 1
    return settings.run()


def cmd_tray():
    try:
        import tray
    except (ImportError, ValueError) as e:
        sys.stderr.write("Không mở được biểu tượng khay (cần AppIndicator): %s\n" % e)
        return 1
    return tray.run()


def main(argv):
    if "--tray" in argv:
        return cmd_tray()
    if "--setup" in argv:
        return cmd_setup()
    if "--test" in argv:
        i = argv.index("--test")
        return cmd_test(argv[i + 1:])
    if "--macro" in argv:
        i = argv.index("--macro")
        return cmd_macro(argv[i + 1:])
    if "--config" in argv:
        i = argv.index("--config")
        return cmd_config(argv[i + 1:])
    if "--version" in argv:
        print("ViKey %s" % VERSION)
        return 0
    if "--help" in argv or "-h" in argv:
        print(__doc__)
        return 0
    return run_engine(exec_by_ibus="--ibus" in argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
