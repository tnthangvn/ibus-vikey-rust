// keyhandler.rs - Xử lý phím / preedit / commit, độc lập với IBus (port từ keyhandler.py).
//
// Quy tắc chống duplicate text:
//   * KHÔNG gửi Backspace giả hay forward_key_event ký tự đã gõ.
//   * Từ đang soạn chỉ nằm trong preedit; kết thúc từ -> commit ĐÚNG MỘT LẦN.
//   * Ký tự kết thúc từ được commit chung với từ trong cùng một lần commit.
//   * Phím không in được (Enter, Esc, Ctrl+...) : commit từ rồi trả phím cho ứng dụng.

use crate::hotkey::{self, Hotkey};
use crate::macros_table::MacroTable;
use crate::vnengine::{Method, VnEngine};
use std::time::Duration;
use unicode_normalization::UnicodeNormalization;

pub const KEY_BACKSPACE: u32 = 0xFF08;
pub const KEY_TAB: u32 = 0xFF09;
pub const KEY_RETURN: u32 = 0xFF0D;
pub const KEY_ESCAPE: u32 = 0xFF1B;
pub const KEY_KP_ENTER: u32 = 0xFF8D;
pub const KEY_DELETE: u32 = 0xFFFF;

/// Phím di chuyển con trỏ / sửa văn bản ở xa: Home Left Up Right Down
/// Page_Up Page_Down End Begin, và bản bàn phím số (KP_Home..KP_Begin, KP_Delete).
fn is_cursor_key(v: u32) -> bool {
    matches!(v, 0xFF50..=0xFF58 | 0xFF95..=0xFF9D | 0xFF9F | KEY_DELETE)
}

pub const SHIFT_MASK: u32 = hotkey::SHIFT_MASK;
pub const CONTROL_MASK: u32 = hotkey::CONTROL_MASK;
pub const MOD1_MASK: u32 = hotkey::MOD1_MASK;
pub const MOD4_MASK: u32 = hotkey::MOD4_MASK;
pub const SUPER_MASK: u32 = hotkey::SUPER_MASK;
pub const HYPER_MASK: u32 = hotkey::HYPER_MASK;
pub const META_MASK: u32 = hotkey::META_MASK;
pub const RELEASE_MASK: u32 = hotkey::RELEASE_MASK;

const SHORTCUT_MASK: u32 = CONTROL_MASK | MOD1_MASK | MOD4_MASK | SUPER_MASK | HYPER_MASK | META_MASK;

fn is_shift_key(v: u32) -> bool {
    v == 0xFFE1 || v == 0xFFE2
}
fn is_ctrl_key(v: u32) -> bool {
    v == 0xFFE3 || v == 0xFFE4
}
fn is_modifier_key(v: u32) -> bool {
    (0xFFE1..=0xFFEE).contains(&v) || v == 0xFE03 || v == 0xFF7F
}

/// Kết quả xử lý một phím.
#[derive(Default, Debug)]
pub struct HandleResult {
    pub handled: bool,            // true: engine đã "ăn" phím; false: trả phím cho ứng dụng
    pub commit: Option<String>,   // chuỗi cần commit
    pub preedit: Option<String>,  // preedit mới ("" = ẩn; None: không đổi)
    pub toggled: bool,            // vừa bật/tắt tiếng Việt bằng phím chuyển
    pub delete: usize,            // (gõ trực tiếp) số ký tự cần xoá trước con trỏ TRƯỚC khi commit
}

impl HandleResult {
    fn pass() -> Self {
        Self::default()
    }
}

pub struct KeyHandler {
    pub engine: VnEngine,
    pub enabled: bool,
    pub toggle_key: String, // ctrl_shift | alt_z | custom | none
    pub toggle_custom: String,
    pub macros_enabled: bool,
    pub macros_when_off: bool,
    pub direct_mode: bool,
    pub charset_decomposed: bool,
    pub macros: MacroTable,
    hotkey: Option<Hotkey>,
    sent: String,   // (direct_mode) phần của từ hiện tại đã gửi vào ứng dụng
    shadow: String, // (khi tắt tiếng Việt) các chữ cái vừa gõ, để nhận diện viết tắt
    pending_toggle: bool,
    last_boundary: Option<char>, // ký tự đã kết thúc từ trước (chặn gõ tắt giữa "file.vn")
}

impl KeyHandler {
    pub fn new(cfg: &crate::config::Config) -> KeyHandler {
        let mut h = KeyHandler {
            engine: {
                let mut e = VnEngine::new(cfg.spell_check, cfg.modern_tone, Method::from_str(&cfg.method));
                e.free_marking = cfg.free_marking;
                e
            },
            enabled: cfg.enabled,
            toggle_key: cfg.toggle_key.clone(),
            toggle_custom: cfg.toggle_custom.clone(),
            macros_enabled: cfg.macros,
            macros_when_off: cfg.macros_when_off,
            direct_mode: cfg.direct_mode,
            charset_decomposed: cfg.charset == "decomposed",
            macros: MacroTable::new(),
            hotkey: None,
            sent: String::new(),
            shadow: String::new(),
            pending_toggle: false,
            last_boundary: None,
        };
        h.hotkey = hotkey::parse(&h.toggle_custom);
        h
    }

    /// Áp cấu hình mới; trả về chuỗi cần commit nếu buộc phải kết thúc từ đang dở.
    pub fn configure(&mut self, cfg: &crate::config::Config) -> String {
        let mut pending = String::new();
        self.macros_enabled = cfg.macros;
        if self.macros_when_off != cfg.macros_when_off {
            self.macros_when_off = cfg.macros_when_off;
            self.shadow.clear();
        }
        self.engine.spell_check = cfg.spell_check;
        self.engine.modern_tone = cfg.modern_tone;
        self.engine.free_marking = cfg.free_marking;
        self.toggle_key = cfg.toggle_key.clone();
        if self.toggle_custom != cfg.toggle_custom {
            self.toggle_custom = cfg.toggle_custom.clone();
            self.hotkey = hotkey::parse(&self.toggle_custom);
        }
        let method = Method::from_str(&cfg.method);
        if method != self.engine.method {
            pending = self.flush();
            self.engine.method = method;
        }
        let dec = cfg.charset == "decomposed";
        if dec != self.charset_decomposed {
            if pending.is_empty() {
                pending = self.flush();
            }
            self.charset_decomposed = dec;
        }
        if cfg.direct_mode != self.direct_mode {
            if pending.is_empty() {
                pending = self.flush();
            }
            self.direct_mode = cfg.direct_mode;
        }
        pending
    }

    /// Bật/tắt tiếng Việt. Trả về chuỗi cần commit (từ đang dở), có thể rỗng.
    pub fn set_enabled(&mut self, enabled: bool) -> String {
        let pending = self.flush();
        self.shadow.clear();
        self.enabled = enabled;
        pending
    }

    pub fn engine_method_str(&self) -> String {
        match self.engine.method {
            Method::Vni => "vni",
            Method::Both => "both",
            Method::Telex => "telex",
        }
        .to_string()
    }

    pub fn is_composing(&self) -> bool {
        !self.engine.is_empty()
    }

    /// Bỏ từ đang soạn KHÔNG commit (focus_out/reset: IBus đã commit preedit).
    pub fn clear(&mut self) {
        self.engine.reset();
        self.sent.clear();
        self.shadow.clear();
        self.last_boundary = None;
    }

    fn out(&self, text: String) -> String {
        if self.charset_decomposed {
            text.nfd().collect()
        } else {
            text
        }
    }

    // ------------------------------------------------------------- gõ tắt
    fn macro_ok_before(&self) -> bool {
        matches!(self.last_boundary, None | Some(' ') | Some('\n') | Some('\t') | Some('(')
            | Some('[') | Some('{') | Some('"') | Some('\'') | Some('\u{201c}') | Some('\u{2018}'))
    }

    fn macro_expansion(&mut self, typed: &str) -> Option<String> {
        if !self.macros_enabled || typed.is_empty() || !self.macro_ok_before() {
            return None;
        }
        self.macros.maybe_reload(Duration::from_secs(1));
        self.macros.lookup(typed).map(|e| self.out(e))
    }

    /// Kết thúc từ đang soạn -> (số ký tự cần xoá, chuỗi cần commit).
    fn finish_word(&mut self, allow_macro: bool) -> (usize, String) {
        let expansion = if allow_macro && !self.engine.is_empty() {
            let typed = self.engine.raw();
            self.macro_expansion(&typed)
        } else {
            None
        };
        if self.direct_mode {
            let sent_len = self.sent.chars().count();
            self.engine.reset();
            self.sent.clear();
            return match expansion {
                Some(exp) => (sent_len, exp),
                None => (0, String::new()),
            };
        }
        let text = match expansion {
            Some(exp) => exp,
            None => self.out(self.engine.text()),
        };
        self.engine.reset();
        self.sent.clear();
        (0, text)
    }

    fn flush(&mut self) -> String {
        let text = if self.direct_mode { String::new() } else { self.out(self.engine.text()) };
        self.engine.reset();
        self.sent.clear();
        text
    }

    /// (direct_mode) So sánh từ mới với phần đã gửi -> xoá/commit phần khác biệt.
    fn direct_update(&mut self) -> HandleResult {
        let new = self.out(self.engine.text());
        let old = std::mem::take(&mut self.sent);
        let oldc: Vec<char> = old.chars().collect();
        let newc: Vec<char> = new.chars().collect();
        let mut n = 0;
        while n < oldc.len() && n < newc.len() && oldc[n] == newc[n] {
            n += 1;
        }
        self.sent = new;
        let delete = oldc.len() - n;
        let insert: String = newc[n..].iter().collect();
        if delete == 1 && insert.is_empty() {
            return HandleResult::pass(); // chỉ cần xoá 1 ký tự: để ứng dụng tự xử lý Backspace
        }
        HandleResult {
            handled: true,
            commit: if insert.is_empty() { None } else { Some(insert) },
            delete,
            ..Default::default()
        }
    }

    // -------------------------------------------------------------- xử lý
    /// keyval: keysym; state: modifier mask; ch: ký tự unicode ('\0' nếu không có).
    pub fn handle(&mut self, keyval: u32, state: u32, ch: char) -> HandleResult {
        let released = state & RELEASE_MASK != 0;

        // --- Alt+Z bật/tắt tiếng Việt
        if self.toggle_key == "alt_z"
            && !released
            && (keyval == 'z' as u32 || keyval == 'Z' as u32)
            && state & MOD1_MASK != 0
            && state & (CONTROL_MASK | SUPER_MASK | MOD4_MASK) == 0
        {
            self.pending_toggle = false;
            let commit = self.set_enabled(!self.enabled);
            return HandleResult {
                handled: true,
                commit: if commit.is_empty() { None } else { Some(commit) },
                preedit: Some(String::new()),
                toggled: true,
                ..Default::default()
            };
        }

        // --- tổ hợp tuỳ chỉnh (vd Ctrl+Shift+Space)
        if self.toggle_key == "custom" && !is_modifier_key(keyval) {
            if let Some(hk) = &self.hotkey {
                if hk.matches(keyval, state & !RELEASE_MASK) {
                    self.pending_toggle = false;
                    if released {
                        return HandleResult { handled: true, ..Default::default() }; // nuốt cả nhả phím
                    }
                    let commit = self.set_enabled(!self.enabled);
                    return HandleResult {
                        handled: true,
                        commit: if commit.is_empty() { None } else { Some(commit) },
                        preedit: Some(String::new()),
                        toggled: true,
                        ..Default::default()
                    };
                }
            }
        }

        // --- Ctrl+Shift (không kèm phím khác), giống Unikey
        if is_modifier_key(keyval) {
            if self.toggle_key != "ctrl_shift" {
                return HandleResult::pass();
            }
            if !released {
                if is_shift_key(keyval) && state & CONTROL_MASK != 0 {
                    self.pending_toggle = true;
                } else if is_ctrl_key(keyval) && state & SHIFT_MASK != 0 {
                    self.pending_toggle = true;
                } else {
                    self.pending_toggle = false;
                }
            } else if self.pending_toggle && (is_shift_key(keyval) || is_ctrl_key(keyval)) {
                self.pending_toggle = false;
                let commit = self.set_enabled(!self.enabled);
                return HandleResult {
                    handled: false,
                    commit: if commit.is_empty() { None } else { Some(commit) },
                    preedit: Some(String::new()),
                    toggled: true,
                    ..Default::default()
                };
            }
            return HandleResult::pass();
        }
        self.pending_toggle = false;

        if released {
            return HandleResult::pass();
        }
        if !self.enabled {
            return self.handle_disabled(keyval, state, ch);
        }

        // --- tổ hợp phím tắt (Ctrl/Alt/Super + ...): commit từ dở rồi nhường phím
        if state & SHORTCUT_MASK != 0 {
            return self.commit_and_pass(false, None);
        }

        if keyval == KEY_BACKSPACE {
            if !self.is_composing() {
                return HandleResult::pass();
            }
            self.engine.backspace();
            if self.direct_mode {
                let r = self.direct_update();
                if self.engine.is_empty() {
                    self.sent.clear();
                }
                return r;
            }
            return HandleResult {
                handled: true,
                preedit: Some(self.engine.text()),
                ..Default::default()
            };
        }

        if keyval == KEY_RETURN || keyval == KEY_KP_ENTER || keyval == KEY_TAB {
            return self.commit_and_pass(true, Some('\n'));
        }
        if keyval == KEY_ESCAPE {
            return self.commit_and_pass(false, None);
        }

        if ch.is_ascii_alphabetic() || (ch.is_ascii_digit() && self.engine.accepts_digit()) {
            self.engine.process_key(ch);
            if self.direct_mode {
                return self.direct_update();
            }
            return HandleResult {
                handled: true,
                preedit: Some(self.engine.text()),
                ..Default::default()
            };
        }

        if ch != '\0' && ch as u32 >= 0x20 && ch != '\u{7f}' {
            // ký tự in được khác (space, số, dấu câu, unicode...)
            if !self.is_composing() {
                self.last_boundary = Some(ch);
                return HandleResult::pass();
            }
            let (delete, text) = self.finish_word(true);
            self.last_boundary = Some(ch);
            if self.direct_mode && text.is_empty() {
                return HandleResult::pass(); // chữ đã trong ứng dụng, nhường phím này
            }
            let mut commit = text;
            commit.push(ch);
            return HandleResult {
                handled: true,
                commit: Some(commit),
                preedit: Some(String::new()),
                delete,
                ..Default::default()
            };
        }

        // Mũi tên / Home / End / PageUp / PageDown / Delete: chốt từ đang dở rồi
        // NUỐT phím. Nếu thả phím xuống ứng dụng ngay sau khi commit, chữ vừa
        // commit và phím này tới nơi trong cùng một nhịp; zsh-autosuggestions
        // (fetch gợi ý bất đồng bộ) chưa kịp cập nhật nên mũi tên dán lại gợi ý
        // cũ, sinh chữ thừa: "pnpm d" + →  ->  "pnpm ddb:migrate...".
        // Ấn lần nữa thì không còn từ dở, phím đi thẳng như thường.
        if is_cursor_key(keyval) && self.is_composing() {
            let (delete, text) = self.finish_word(false);
            self.last_boundary = None;
            if delete == 0 && text.is_empty() {
                // direct_mode: chữ đã nằm sẵn trong ứng dụng, không commit gì
                // -> không có nhịp nào để đua, nhường phím như cũ.
                return HandleResult {
                    handled: false,
                    preedit: Some(String::new()),
                    ..Default::default()
                };
            }
            return HandleResult {
                handled: true,
                commit: Some(text),
                preedit: Some(String::new()),
                delete,
                ..Default::default()
            };
        }

        // phím chức năng khác (F1..F12, Insert, ...)
        self.commit_and_pass(false, None)
    }

    /// Đang tắt tiếng Việt: mọi phím đi thẳng vào ứng dụng; nếu bật "gõ tắt khi
    /// tắt tiếng Việt" thì theo dõi các chữ cái vừa gõ để bung viết tắt.
    fn handle_disabled(&mut self, keyval: u32, state: u32, ch: char) -> HandleResult {
        if !(self.macros_when_off && self.macros_enabled) {
            return HandleResult::pass();
        }
        if state & SHORTCUT_MASK != 0 {
            self.shadow.clear();
            self.last_boundary = None;
            return HandleResult::pass();
        }
        if ch.is_ascii_alphabetic() {
            self.shadow.push(ch);
            return HandleResult::pass();
        }
        if keyval == KEY_BACKSPACE {
            self.shadow.pop();
            return HandleResult::pass();
        }
        let boundary: char;
        if keyval == KEY_RETURN || keyval == KEY_KP_ENTER || keyval == KEY_TAB {
            boundary = '\n';
        } else if ch != '\0' && ch as u32 >= 0x20 && ch != '\u{7f}' {
            boundary = ch;
        } else {
            self.shadow.clear();
            self.last_boundary = None;
            return HandleResult::pass();
        }
        let typed = std::mem::take(&mut self.shadow);
        let exp = self.macro_expansion(&typed);
        self.last_boundary = Some(boundary);
        let Some(exp) = exp else { return HandleResult::pass() };
        let n = typed.chars().count();
        if boundary == '\n' {
            return HandleResult {
                handled: false,
                commit: Some(exp),
                delete: n,
                ..Default::default()
            };
        }
        let mut commit = exp;
        commit.push(ch);
        HandleResult { handled: true, commit: Some(commit), delete: n, ..Default::default() }
    }

    /// Kết thúc từ đang dở (nếu có) rồi nhường phím cho ứng dụng.
    fn commit_and_pass(&mut self, allow_macro: bool, boundary: Option<char>) -> HandleResult {
        if !self.is_composing() {
            self.last_boundary = boundary;
            return HandleResult::pass();
        }
        let (delete, text) = self.finish_word(allow_macro);
        self.last_boundary = boundary;
        HandleResult {
            handled: false,
            commit: if text.is_empty() { None } else { Some(text) },
            preedit: Some(String::new()),
            delete,
            ..Default::default()
        }
    }
}
