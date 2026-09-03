// config.rs - Đọc/ghi ~/.config/ibus-vikey/config.json (cùng định dạng với bản Python).

use serde_json::{json, Map, Value};
use std::path::PathBuf;
use std::time::SystemTime;

#[derive(Clone, Debug, PartialEq)]
pub struct Config {
    pub method: String,        // telex | vni | both
    pub toggle_key: String,    // ctrl_shift | alt_z | custom | none
    pub toggle_custom: String, // accelerator GTK, vd "<Control><Shift>space"
    pub charset: String,       // precomposed | decomposed
    pub enabled: bool,
    pub spell_check: bool,
    pub modern_tone: bool,
    pub macros: bool,
    pub macros_when_off: bool,
    pub direct_mode: bool,
}

impl Default for Config {
    fn default() -> Self {
        Config {
            method: "telex".into(),
            toggle_key: "ctrl_shift".into(),
            toggle_custom: "<Control><Shift>space".into(),
            charset: "precomposed".into(),
            enabled: true,
            spell_check: true,
            modern_tone: false,
            macros: true,
            macros_when_off: false,
            direct_mode: false,
        }
    }
}

pub const METHODS: [&str; 3] = ["telex", "vni", "both"];
pub const TOGGLE_KEYS: [&str; 4] = ["ctrl_shift", "alt_z", "custom", "none"];
pub const CHARSETS: [&str; 2] = ["precomposed", "decomposed"];
pub const BOOL_KEYS: [&str; 6] = [
    "enabled", "spell_check", "modern_tone", "macros", "macros_when_off", "direct_mode",
];

pub fn config_dir() -> PathBuf {
    let base = std::env::var("XDG_CONFIG_HOME").ok().filter(|s| !s.is_empty()).map(PathBuf::from)
        .unwrap_or_else(|| {
            let home = std::env::var("HOME").unwrap_or_else(|_| ".".into());
            PathBuf::from(home).join(".config")
        });
    base.join("ibus-vikey")
}

pub fn config_file() -> PathBuf {
    config_dir().join("config.json")
}

fn choice(v: Option<&Value>, allowed: &[&str], default: &str) -> String {
    match v.and_then(|x| x.as_str()) {
        Some(s) if allowed.contains(&s) => s.to_string(),
        _ => default.to_string(),
    }
}

fn boolean(v: Option<&Value>, default: bool) -> bool {
    match v {
        Some(Value::Bool(b)) => *b,
        Some(Value::String(s)) => matches!(s.trim().to_ascii_lowercase().as_str(), "1" | "true" | "on" | "yes"),
        Some(Value::Number(n)) => n.as_f64().map(|f| f != 0.0).unwrap_or(default),
        _ => default,
    }
}

pub fn load() -> Config {
    let d = Config::default();
    let data = match std::fs::read_to_string(config_file()) {
        Ok(s) => s,
        Err(_) => return d,
    };
    let v: Value = match serde_json::from_str(&data) {
        Ok(v) => v,
        Err(_) => return d,
    };
    let o = match v.as_object() {
        Some(o) => o,
        None => return d,
    };
    let mut cfg = Config {
        method: choice(o.get("method"), &METHODS, &d.method),
        toggle_key: choice(o.get("toggle_key"), &TOGGLE_KEYS, &d.toggle_key),
        toggle_custom: o
            .get("toggle_custom")
            .and_then(|x| x.as_str())
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty())
            .unwrap_or(d.toggle_custom),
        charset: choice(o.get("charset"), &CHARSETS, &d.charset),
        enabled: boolean(o.get("enabled"), d.enabled),
        spell_check: boolean(o.get("spell_check"), d.spell_check),
        modern_tone: boolean(o.get("modern_tone"), d.modern_tone),
        macros: boolean(o.get("macros"), d.macros),
        macros_when_off: boolean(o.get("macros_when_off"), d.macros_when_off),
        direct_mode: boolean(o.get("direct_mode"), d.direct_mode),
    };
    // tương thích bản cũ: ctrl_shift_toggle (bool) -> toggle_key
    if !o.contains_key("toggle_key") {
        if let Some(v) = o.get("ctrl_shift_toggle") {
            cfg.toggle_key = if boolean(Some(v), true) { "ctrl_shift".into() } else { "none".into() };
        }
    }
    cfg
}

pub fn save(cfg: &Config) -> std::io::Result<()> {
    let mut m = Map::new();
    m.insert("method".into(), json!(cfg.method));
    m.insert("toggle_key".into(), json!(cfg.toggle_key));
    m.insert("toggle_custom".into(), json!(cfg.toggle_custom));
    m.insert("charset".into(), json!(cfg.charset));
    m.insert("enabled".into(), json!(cfg.enabled));
    m.insert("spell_check".into(), json!(cfg.spell_check));
    m.insert("modern_tone".into(), json!(cfg.modern_tone));
    m.insert("macros".into(), json!(cfg.macros));
    m.insert("macros_when_off".into(), json!(cfg.macros_when_off));
    m.insert("direct_mode".into(), json!(cfg.direct_mode));
    std::fs::create_dir_all(config_dir())?;
    let mut s = serde_json::to_string_pretty(&Value::Object(m)).unwrap();
    s.push('\n');
    std::fs::write(config_file(), s)
}

pub fn mtime() -> Option<SystemTime> {
    std::fs::metadata(config_file()).and_then(|m| m.modified()).ok()
}

pub fn toggle_label(cfg: &Config) -> String {
    match cfg.toggle_key.as_str() {
        "ctrl_shift" => "Ctrl+Shift".into(),
        "alt_z" => "Alt+Z".into(),
        "none" => "Không dùng".into(),
        _ => crate::hotkey::label(&cfg.toggle_custom),
    }
}
