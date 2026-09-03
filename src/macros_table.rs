// macros_table.rs - Bảng gõ tắt ~/.config/ibus-vikey/macros.txt (cùng định dạng bản Python).

use std::collections::HashMap;
use std::path::PathBuf;
use std::time::{Duration, Instant, SystemTime};

pub const DEFAULT_MACROS: &str = "\
# Bảng gõ tắt ViKey - mỗi dòng:  viết_tắt:nội_dung_đầy_đủ
# Viết tắt chỉ gồm chữ cái, không phân biệt hoa/thường. Dòng bắt đầu bằng # bị bỏ qua.
# Sửa xong lưu file là dùng được ngay (không cần khởi động lại IBus).
# Xem nhanh:  vikey --macro        thêm:  vikey --macro add tphcm \"Thành phố Hồ Chí Minh\"
vn:Việt Nam
hn:Hà Nội
hcm:Hồ Chí Minh
tphcm:Thành phố Hồ Chí Minh
# ko:không
# dc:được
# ng:người
# email:ten.cua.ban@gmail.com
";

pub fn macro_file() -> PathBuf {
    crate::config::config_dir().join("macros.txt")
}

pub fn parse(text: &str) -> HashMap<String, String> {
    let mut table = HashMap::new();
    for line in text.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let Some((key, value)) = line.split_once(':') else { continue };
        let key = key.trim().to_lowercase();
        let value = value.trim();
        if key.is_empty() || value.is_empty() || !key.chars().all(|c| c.is_ascii_lowercase()) {
            continue;
        }
        table.insert(key, value.to_string());
    }
    table
}

/// Điều chỉnh hoa/thường của nội dung theo cách gõ viết tắt.
pub fn adapt_case(typed: &str, expansion: &str) -> String {
    let has_lower = typed.chars().any(|c| c.is_ascii_lowercase());
    let first_upper = typed.chars().next().map(|c| c.is_ascii_uppercase()).unwrap_or(false);
    if typed.chars().count() > 1 && !has_lower && typed.chars().all(|c| c.is_ascii_uppercase()) {
        return expansion.to_uppercase();
    }
    if first_upper {
        let mut cs = expansion.chars();
        return match cs.next() {
            Some(f) => f.to_uppercase().collect::<String>() + cs.as_str(),
            None => String::new(),
        };
    }
    expansion.to_string()
}

pub struct MacroTable {
    pub path: PathBuf,
    pub table: HashMap<String, String>,
    mtime: Option<SystemTime>,
    last_check: Instant,
}

impl MacroTable {
    pub fn new() -> MacroTable {
        let mut m = MacroTable {
            path: macro_file(),
            table: HashMap::new(),
            mtime: None,
            last_check: Instant::now(),
        };
        m.reload();
        m
    }

    pub fn ensure_file(&self) -> &PathBuf {
        if !self.path.exists() {
            let _ = std::fs::create_dir_all(self.path.parent().unwrap());
            let _ = std::fs::write(&self.path, DEFAULT_MACROS);
        }
        &self.path
    }

    fn stat(&self) -> Option<SystemTime> {
        std::fs::metadata(&self.path).and_then(|m| m.modified()).ok()
    }

    pub fn reload(&mut self) {
        self.mtime = self.stat();
        self.last_check = Instant::now();
        match std::fs::read_to_string(&self.path) {
            Ok(s) => self.table = parse(&s),
            Err(_) => self.table = parse(DEFAULT_MACROS),
        }
    }

    /// Nạp lại nếu file đổi (kiểm tra tối đa mỗi giây một lần).
    pub fn maybe_reload(&mut self, min_interval: Duration) {
        if self.last_check.elapsed() < min_interval {
            return;
        }
        self.last_check = Instant::now();
        if self.stat() != self.mtime {
            self.reload();
        }
    }

    /// typed: dãy phím thô của từ -> nội dung đã chỉnh hoa/thường.
    pub fn lookup(&self, typed: &str) -> Option<String> {
        if typed.is_empty() {
            return None;
        }
        self.table.get(&typed.to_lowercase()).map(|exp| adapt_case(typed, exp))
    }

    // ---- sửa bảng (dùng cho CLI)
    fn read_lines(&self) -> Vec<String> {
        std::fs::read_to_string(&self.path)
            .map(|s| s.lines().map(|l| l.to_string()).collect())
            .unwrap_or_default()
    }

    fn write_lines(&mut self, lines: Vec<String>) -> std::io::Result<()> {
        std::fs::create_dir_all(self.path.parent().unwrap())?;
        let mut s = lines.join("\n");
        while s.ends_with('\n') {
            s.pop();
        }
        s.push('\n');
        std::fs::write(&self.path, s)?;
        self.reload();
        Ok(())
    }

    fn line_key(line: &str) -> Option<String> {
        let s = line.trim();
        if s.is_empty() || s.starts_with('#') {
            return None;
        }
        s.split_once(':').map(|(k, _)| k.trim().to_lowercase())
    }

    pub fn add(&mut self, key: &str, value: &str) -> Result<(), String> {
        let key = key.trim().to_lowercase();
        let value = value.trim();
        if key.is_empty() || value.is_empty() || !key.chars().all(|c| c.is_ascii_lowercase()) {
            return Err("Viết tắt chỉ gồm chữ cái a-z và nội dung không được rỗng".into());
        }
        self.ensure_file();
        let mut out = Vec::new();
        let mut replaced = false;
        for line in self.read_lines() {
            if Self::line_key(&line).as_deref() == Some(key.as_str()) {
                if !replaced {
                    out.push(format!("{}:{}", key, value));
                    replaced = true;
                }
                continue;
            }
            out.push(line);
        }
        if !replaced {
            out.push(format!("{}:{}", key, value));
        }
        self.write_lines(out).map_err(|e| e.to_string())
    }

    pub fn remove(&mut self, key: &str) -> bool {
        let key = key.trim().to_lowercase();
        let mut out = Vec::new();
        let mut found = false;
        for line in self.read_lines() {
            if Self::line_key(&line).as_deref() == Some(key.as_str()) {
                found = true;
                continue;
            }
            out.push(line);
        }
        if found {
            let _ = self.write_lines(out);
        }
        found
    }
}
