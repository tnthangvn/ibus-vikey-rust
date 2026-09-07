// hotkey.rs - Phân tích tổ hợp phím dạng accelerator GTK ("<Control><Shift>space").

pub const SHIFT_MASK: u32 = 1 << 0;
pub const CONTROL_MASK: u32 = 1 << 2;
pub const MOD1_MASK: u32 = 1 << 3; // Alt
pub const MOD4_MASK: u32 = 1 << 6; // Super (xkb)
pub const SUPER_MASK: u32 = 1 << 26;
pub const HYPER_MASK: u32 = 1 << 27;
pub const META_MASK: u32 = 1 << 28;
pub const RELEASE_MASK: u32 = 1 << 30;

pub const RELEVANT_MASK: u32 =
    SHIFT_MASK | CONTROL_MASK | MOD1_MASK | MOD4_MASK | SUPER_MASK | HYPER_MASK | META_MASK;

fn mod_mask(name: &str) -> Option<u32> {
    Some(match name {
        "shift" | "shft" => SHIFT_MASK,
        "control" | "ctrl" | "ctl" | "primary" => CONTROL_MASK,
        "alt" | "mod1" => MOD1_MASK,
        "super" | "mod4" | "win" => SUPER_MASK,
        "hyper" => HYPER_MASK,
        "meta" => META_MASK,
        _ => return None,
    })
}

fn key_name_val(name: &str) -> Option<u32> {
    Some(match name {
        "space" => 0x20,
        "tab" => 0xFF09,
        "return" | "enter" => 0xFF0D,
        "escape" => 0xFF1B,
        "backspace" => 0xFF08,
        "delete" => 0xFFFF,
        "insert" => 0xFF63,
        "home" => 0xFF50,
        "end" => 0xFF57,
        "page_up" | "prior" => 0xFF55,
        "page_down" | "next" => 0xFF56,
        "left" => 0xFF51,
        "up" => 0xFF52,
        "right" => 0xFF53,
        "down" => 0xFF54,
        "pause" => 0xFF13,
        "print" => 0xFF61,
        "menu" => 0xFF67,
        "grave" => 0x60,
        "asciitilde" => 0x7E,
        "minus" => 0x2D,
        "equal" => 0x3D,
        "plus" => 0x2B,
        "bracketleft" => 0x5B,
        "bracketright" => 0x5D,
        "backslash" => 0x5C,
        "bar" => 0x7C,
        "semicolon" => 0x3B,
        "colon" => 0x3A,
        "apostrophe" => 0x27,
        "quotedbl" => 0x22,
        "comma" => 0x2C,
        "period" => 0x2E,
        "slash" => 0x2F,
        "less" => 0x3C,
        "greater" => 0x3E,
        "question" => 0x3F,
        "exclam" => 0x21,
        "at" => 0x40,
        "numbersign" => 0x23,
        "dollar" => 0x24,
        "percent" => 0x25,
        "asciicircum" => 0x5E,
        "ampersand" => 0x26,
        "asterisk" => 0x2A,
        "parenleft" => 0x28,
        "parenright" => 0x29,
        "underscore" => 0x5F,
        "kp_space" => 0xFF80,
        "kp_enter" => 0xFF8D,
        "kp_add" => 0xFFAB,
        "kp_subtract" => 0xFFAD,
        _ => {
            if let Some(rest) = name.strip_prefix('f') {
                if let Ok(n) = rest.parse::<u32>() {
                    if (1..=24).contains(&n) {
                        return Some(0xFFBE + n - 1);
                    }
                }
            }
            return None;
        }
    })
}

fn is_modifier_keyval(v: u32) -> bool {
    (0xFFE1..0xFFEF).contains(&v) || v == 0xFE03 || v == 0xFF7F || v == 0xFFE5
}

#[derive(Clone, Debug)]
pub struct Hotkey {
    pub mods: u32,
    pub keyval: u32,
    pub name: String,
}

impl Hotkey {
    pub fn matches(&self, keyval: u32, state: u32) -> bool {
        let mut st = state & RELEVANT_MASK;
        if st & MOD4_MASK != 0 {
            st = (st & !MOD4_MASK) | SUPER_MASK; // Super theo xkb -> gộp về SUPER_MASK
        }
        if st != self.mods {
            return false;
        }
        if keyval == self.keyval {
            return true;
        }
        // chữ cái: Shift/CapsLock làm keyval thành chữ hoa
        if (0x20..0x7F).contains(&keyval) && (0x20..0x7F).contains(&self.keyval) {
            let a = (keyval as u8 as char).to_ascii_lowercase();
            let b = (self.keyval as u8 as char).to_ascii_lowercase();
            return a == b;
        }
        false
    }

    pub fn label(&self) -> String {
        let mut parts: Vec<String> = Vec::new();
        for (m, l) in [
            (CONTROL_MASK, "Ctrl"),
            (MOD1_MASK, "Alt"),
            (SUPER_MASK, "Super"),
            (HYPER_MASK, "Hyper"),
            (META_MASK, "Meta"),
            (SHIFT_MASK, "Shift"),
        ] {
            if self.mods & m != 0 {
                parts.push(l.to_string());
            }
        }
        let n = &self.name;
        if !n.is_empty() {
            let mut cs = n.chars();
            let first = cs.next().unwrap().to_ascii_uppercase();
            if n.chars().count() > 1 {
                parts.push(format!("{}{}", first, cs.as_str()));
            } else {
                parts.push(first.to_string());
            }
        }
        parts.join("+")
    }
}

/// "<Control><Shift>space" -> Hotkey; None nếu không hợp lệ (kể cả tổ hợp chỉ có modifier).
pub fn parse(text: &str) -> Option<Hotkey> {
    let mut s = text.trim();
    let mut mods = 0u32;
    while let Some(rest) = s.strip_prefix('<') {
        let end = rest.find('>')?;
        mods |= mod_mask(&rest[..end].trim().to_ascii_lowercase())?;
        s = rest[end + 1..].trim_start();
    }
    let key = s.trim();
    if key.is_empty() {
        return None;
    }
    let kl = key.to_ascii_lowercase();
    let keyval = if key.chars().count() == 1 {
        kl.chars().next().unwrap() as u32
    } else {
        key_name_val(&kl)?
    };
    if is_modifier_keyval(keyval) {
        return None;
    }
    Some(Hotkey { mods, keyval, name: key.to_string() })
}

pub fn label(text: &str) -> String {
    parse(text).map(|h| h.label()).unwrap_or_else(|| text.to_string())
}

/// Tổ hợp đã bị trình duyệt / desktop / ô nhập GTK chiếm. So theo nhãn chuẩn
/// hoá ("Ctrl+Shift+D") nên không phụ thuộc cách viết accelerator.
const TAKEN: [(&str, &str); 26] = [
    ("Ctrl+Shift+A", "Chrome: tìm thẻ"),
    ("Ctrl+Shift+B", "Chrome: thanh dấu trang"),
    ("Ctrl+Shift+C", "Chrome: chọn phần tử để kiểm tra"),
    ("Ctrl+Shift+D", "Chrome: lưu tất cả thẻ vào dấu trang"),
    ("Ctrl+Shift+G", "Chrome: tìm ngược"),
    ("Ctrl+Shift+I", "Chrome: DevTools"),
    ("Ctrl+Shift+J", "Chrome: DevTools Console"),
    ("Ctrl+Shift+M", "Chrome: đổi hồ sơ người dùng"),
    ("Ctrl+Shift+N", "Chrome: cửa sổ ẩn danh"),
    ("Ctrl+Shift+O", "Chrome: trình quản lý dấu trang"),
    ("Ctrl+Shift+P", "Chrome: in bằng hộp thoại hệ thống"),
    ("Ctrl+Shift+R", "Chrome: tải lại bỏ qua cache"),
    ("Ctrl+Shift+T", "Chrome: mở lại thẻ vừa đóng"),
    ("Ctrl+Shift+V", "Chrome: dán không định dạng"),
    ("Ctrl+Shift+W", "Chrome: đóng cửa sổ"),
    ("Ctrl+Shift+Delete", "Chrome: xoá dữ liệu duyệt web"),
    ("Ctrl+Shift+Tab", "Chrome: thẻ trước đó"),
    ("Ctrl+Shift+U", "GTK/IBus: nhập ký tự Unicode"),
    ("Ctrl+Shift+E", "GTK/IBus: bảng emoji"),
    ("Ctrl+Shift+Z", "ô nhập: làm lại (redo)"),
    ("Ctrl+Alt+T", "GNOME: mở terminal"),
    ("Ctrl+Alt+D", "GNOME: hiện màn hình nền"),
    ("Ctrl+Alt+Delete", "GNOME: đăng xuất"),
    ("Ctrl+Shift+Alt+R", "GNOME: quay màn hình"),
    ("Alt+F2", "GNOME: chạy lệnh"),
    ("Alt+Space", "GNOME: menu cửa sổ"),
];

/// Tổ hợp này có đụng phím tắt phổ biến không? Trả về tên hành động bị đụng.
pub fn conflict(text: &str) -> Option<&'static str> {
    let l = label(text);
    TAKEN.iter().find(|(k, _)| *k == l).map(|(_, what)| *what)
}

#[cfg(test)]
mod tests {
    #[test]
    fn known_conflicts_are_detected() {
        assert!(super::conflict("<Control><Shift>d").is_some());
        assert!(super::conflict("<Primary><Shift>D").is_some()); // khác cách viết
        assert!(super::conflict("<Control><Shift>F9").is_none());
        assert!(super::conflict("<Control><Shift>space").is_none());
    }
}
