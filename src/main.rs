// ViKey (Rust) - Bộ gõ tiếng Việt (Telex/VNI) cho IBus.
//
//   vikey-engine --ibus         được ibus-daemon gọi (qua file component XML)
//   vikey-engine --test "..."   gõ thử trong terminal, không cần IBus
//   vikey-engine --config ...   xem/đổi cấu hình
//   vikey-engine --macro ...    xem/sửa bảng gõ tắt
//   vikey-engine --setup        mở cửa sổ Cài đặt (GTK4, phần Python đi kèm)

use vikey_engine::{config, hotkey, ibus_main, macros_table, vnengine};

fn cmd_test(args: &[String]) -> i32 {
    let cfg = config::load();
    let method = vnengine::Method::from_str(&cfg.method);
    let words: Vec<String> = args.join(" ").split_whitespace().map(|s| s.to_string()).collect();
    if words.is_empty() {
        eprintln!("Dùng: vikey --test \"tieesng vieejt\"");
        return 2;
    }
    let out: Vec<String> = words
        .iter()
        .map(|w| vnengine::type_word_ex(w, cfg.spell_check, cfg.modern_tone, method, cfg.free_marking))
        .collect();
    println!("{}", out.join(" "));
    0
}

fn cmd_config(args: &[String]) -> i32 {
    let mut cfg = config::load();
    if args.is_empty() {
        println!("File: {}", config::config_file().display());
        let rows: Vec<(&str, String, &str)> = vec![
            ("method", cfg.method.clone(), "telex | vni | both"),
            ("toggle_key", cfg.toggle_key.clone(), "ctrl_shift | alt_z | custom | none"),
            (
                "toggle_custom",
                format!("{}  ({})", cfg.toggle_custom, hotkey::label(&cfg.toggle_custom)),
                "vd \"<Control><Shift>space\"",
            ),
            ("charset", cfg.charset.clone(), "precomposed | decomposed"),
            ("enabled", onoff(cfg.enabled), ""),
            ("spell_check", onoff(cfg.spell_check), ""),
            ("modern_tone", onoff(cfg.modern_tone), ""),
            ("free_marking", onoff(cfg.free_marking), "bỏ dấu tự do: dend → đen"),
            ("macros", onoff(cfg.macros), ""),
            ("macros_when_off", onoff(cfg.macros_when_off), ""),
            ("direct_mode", onoff(cfg.direct_mode), ""),
        ];
        for (k, v, extra) in rows {
            if extra.is_empty() {
                println!("  {:<16} {}", k, v);
            } else {
                println!("  {:<16} {:<28} ({})", k, v, extra);
            }
        }
        return 0;
    }
    if args.len() != 2 {
        eprintln!("Dùng: vikey --config KEY GIÁ_TRỊ");
        return 2;
    }
    let (key, val) = (args[0].as_str(), args[1].trim());
    let ok = match key {
        "method" if config::METHODS.contains(&val) => {
            cfg.method = val.into();
            true
        }
        "toggle_key" if config::TOGGLE_KEYS.contains(&val) => {
            cfg.toggle_key = val.into();
            true
        }
        "charset" if config::CHARSETS.contains(&val) => {
            cfg.charset = val.into();
            true
        }
        "toggle_custom" => {
            if hotkey::parse(val).is_none() {
                eprintln!("Tổ hợp không hợp lệ. Ví dụ: \"<Control><Shift>space\", \"<Alt>grave\", \"<Shift>F12\"");
                return 2;
            }
            cfg.toggle_custom = val.into();
            true
        }
        k if config::BOOL_KEYS.contains(&k) => {
            let b = matches!(val.to_ascii_lowercase().as_str(), "1" | "true" | "on" | "yes");
            if !matches!(val.to_ascii_lowercase().as_str(), "1" | "true" | "on" | "yes" | "0" | "false" | "off" | "no") {
                eprintln!("Giá trị cho {} phải là on|off", k);
                return 2;
            }
            match k {
                "enabled" => cfg.enabled = b,
                "spell_check" => cfg.spell_check = b,
                "modern_tone" => cfg.modern_tone = b,
                "free_marking" => cfg.free_marking = b,
                "macros" => cfg.macros = b,
                "macros_when_off" => cfg.macros_when_off = b,
                "direct_mode" => cfg.direct_mode = b,
                _ => unreachable!(),
            }
            true
        }
        _ => false,
    };
    if !ok {
        eprintln!("Khoá/giá trị không hợp lệ. Chạy 'vikey --config' để xem danh sách.");
        return 2;
    }
    if config::save(&cfg).is_err() {
        eprintln!("Không ghi được {}", config::config_file().display());
        return 1;
    }
    println!("Đã lưu {} = {} (áp dụng khi focus vào ô nhập tiếp theo)", key, val);
    0
}

fn onoff(b: bool) -> String {
    (if b { "on" } else { "off" }).to_string()
}

fn cmd_macro(args: &[String]) -> i32 {
    let mut m = macros_table::MacroTable::new();
    if args.is_empty() || args[0] == "list" || args[0] == "ls" {
        let exists = m.path.exists();
        println!(
            "File: {}{}",
            m.path.display(),
            if exists { "" } else { "  (chưa có, đang dùng bảng mẫu)" }
        );
        let mut keys: Vec<&String> = m.table.keys().collect();
        keys.sort();
        for k in keys {
            println!("  {:<12} -> {}", k, m.table[k]);
        }
        return 0;
    }
    match args[0].as_str() {
        "init" => {
            println!("Bảng gõ tắt: {}", m.ensure_file().display());
            0
        }
        "add" if args.len() >= 3 => {
            let value = args[2..].join(" ");
            match m.add(&args[1], &value) {
                Ok(_) => {
                    println!("Đã thêm: {} -> {}", args[1].to_lowercase(), value);
                    0
                }
                Err(e) => {
                    eprintln!("Lỗi: {}", e);
                    2
                }
            }
        }
        "del" | "rm" | "remove" if args.len() == 2 => {
            if m.remove(&args[1]) {
                println!("Đã xoá.");
            } else {
                println!("Không thấy viết tắt '{}'.", args[1]);
            }
            0
        }
        "edit" => {
            let path = m.ensure_file().clone();
            let _ = std::process::Command::new("xdg-open").arg(&path).spawn();
            println!("Đang mở {}", path.display());
            0
        }
        _ => {
            eprintln!("Dùng: vikey --macro [list | add VIẾT_TẮT NỘI_DUNG... | del VIẾT_TẮT | edit | init]");
            2
        }
    }
}

fn cmd_setup() -> i32 {
    // Cửa sổ Cài đặt là ứng dụng GTK4 bằng Python đi kèm trong gói.
    for dir in [
        std::env::var("VIKEY_SETUP_DIR").unwrap_or_default(),
        "/usr/share/ibus-vikey/setup".to_string(),
    ] {
        if dir.is_empty() {
            continue;
        }
        let main_py = std::path::Path::new(&dir).join("main.py");
        if main_py.exists() {
            let py = std::env::var("VIKEY_PYTHON").unwrap_or_else(|_| "python3".into());
            let st = std::process::Command::new(py).arg(main_py).arg("--setup").status();
            return st.map(|s| s.code().unwrap_or(1)).unwrap_or(1);
        }
    }
    eprintln!(
        "Không tìm thấy cửa sổ Cài đặt (cần python3-gi + gir1.2-gtk-4.0).\n\
         Vẫn chỉnh được bằng lệnh:  vikey --config   |   vikey --macro"
    );
    1
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let first = args.first().map(|s| s.as_str()).unwrap_or("--ibus");
    let rest = if args.is_empty() { &[] } else { &args[1..] };
    let code = match first {
        "--test" => cmd_test(rest),
        "--config" => cmd_config(rest),
        "--macro" => cmd_macro(rest),
        "--setup" => cmd_setup(),
        "--version" => {
            println!("ViKey (Rust) {}", env!("CARGO_PKG_VERSION"));
            0
        }
        "--help" | "-h" => {
            println!("vikey-engine --ibus | --test \"...\" | --config [KEY GIÁ_TRỊ] | --macro ... | --setup | --version");
            0
        }
        _ => {
            let rt = tokio::runtime::Builder::new_current_thread().enable_all().build().unwrap();
            match rt.block_on(ibus_main::run()) {
                Ok(_) => 0,
                Err(e) => {
                    eprintln!("ViKey: {}", e);
                    1
                }
            }
        }
    };
    std::process::exit(code);
}
