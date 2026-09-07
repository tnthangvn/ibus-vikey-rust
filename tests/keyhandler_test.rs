// Port các unit test của keyhandler Python: mô phỏng ứng dụng + IBus để phát hiện duplicate.
use vikey_engine::config::Config;
use vikey_engine::keyhandler::*;

struct FakeApp {
    h: KeyHandler,
    text: String,
    preedit: String,
}

const KEY_SHIFT_L: u32 = 0xFFE1;
const KEY_CONTROL_L: u32 = 0xFFE3;

impl FakeApp {
    fn new(f: impl FnOnce(&mut Config)) -> FakeApp {
        let mut cfg = Config::default();
        f(&mut cfg);
        let mut h = KeyHandler::new(&cfg);
        h.macros.table = [
            ("vn", "Việt Nam"), ("hn", "Hà Nội"), ("ko", "không"), ("email", "ten@gmail.com"),
        ]
        .iter()
        .map(|(k, v)| (k.to_string(), v.to_string()))
        .collect();
        FakeApp { h, text: String::new(), preedit: String::new() }
    }

    fn key(&mut self, keyval: u32, state: u32, ch: char) -> HandleResult {
        let r = self.h.handle(keyval, state, ch);
        if r.delete > 0 {
            self.preedit.clear();
            let n: usize = self.text.chars().count() - r.delete;
            self.text = self.text.chars().take(n).collect();
        }
        if let Some(c) = &r.commit {
            self.preedit.clear();
            self.text.push_str(c);
        }
        if let Some(p) = &r.preedit {
            self.preedit = p.clone();
        }
        if !r.handled && state & RELEASE_MASK == 0 {
            if keyval == KEY_RETURN {
                self.text.push('\n');
            } else if keyval == KEY_BACKSPACE {
                self.text.pop();
            } else if ch != '\0' && ch as u32 >= 0x20 && state & CONTROL_MASK == 0 {
                self.text.push(ch);
            }
        }
        r
    }

    fn type_str(&mut self, s: &str) {
        for c in s.chars() {
            if c == '\n' {
                self.key(KEY_RETURN, 0, '\0');
            } else {
                let st = if c.is_ascii_uppercase() { SHIFT_MASK } else { 0 };
                self.key(c as u32, st, c);
            }
        }
    }

    fn focus_out(&mut self) {
        // IBus (preedit COMMIT) tự commit preedit, rồi engine.clear()
        let p = std::mem::take(&mut self.preedit);
        self.text.push_str(&p);
        self.h.clear();
    }
}

#[test]
fn sentence_and_terminal() {
    let mut app = FakeApp::new(|_| {});
    app.type_str("Tieesng Vieejt raats hay.\n");
    assert_eq!(app.text, "Tiếng Việt rất hay.\n");
    assert_eq!(app.preedit, "");
    app.text.clear();
    app.type_str("sudo apt install git\nls -la /home\n");
    assert_eq!(app.text, "sudo apt install git\nls -la /home\n");
}

#[test]
fn backspace_in_and_out_of_word() {
    let mut app = FakeApp::new(|_| {});
    app.type_str("vieets");
    assert_eq!(app.preedit, "viết");
    app.key(KEY_BACKSPACE, 0, '\0');
    assert_eq!(app.preedit, "viêt");
    app.type_str(" ");
    assert_eq!(app.text, "viêt ");
    let r = app.key(KEY_BACKSPACE, 0, '\0');
    assert!(!r.handled);
    assert_eq!(app.text, "viêt");
}

#[test]
fn focus_out_no_duplicate() {
    let mut app = FakeApp::new(|_| {});
    app.type_str("xin chaof");
    assert_eq!(app.text, "xin ");
    assert_eq!(app.preedit, "chào");
    app.focus_out();
    assert_eq!(app.text, "xin chào");
    app.type_str(" banj");
    app.focus_out();
    assert_eq!(app.text, "xin chào bạn");
}

#[test]
fn escape_and_ctrl() {
    let mut app = FakeApp::new(|_| {});
    app.type_str("abc");
    let r = app.key(KEY_ESCAPE, 0, '\0');
    assert!(!r.handled);
    assert_eq!(r.commit.as_deref(), Some("abc"));
    app.type_str("xyz");
    let r = app.key('c' as u32, CONTROL_MASK, 'c');
    assert!(!r.handled);
    assert_eq!(app.text, "abcxyz");
}

#[test]
fn ctrl_shift_toggle() {
    let mut app = FakeApp::new(|_| {});
    app.type_str("vieet");
    app.key(KEY_CONTROL_L, 0, '\0');
    app.key(KEY_SHIFT_L, CONTROL_MASK, '\0');
    app.key(KEY_SHIFT_L, CONTROL_MASK | SHIFT_MASK | RELEASE_MASK, '\0');
    app.key(KEY_CONTROL_L, CONTROL_MASK | RELEASE_MASK, '\0');
    assert!(!app.h.enabled);
    assert_eq!(app.text, "viêt");
    app.type_str(" vieets");
    assert_eq!(app.text, "viêt vieets");
    app.key(KEY_SHIFT_L, 0, '\0');
    app.key(KEY_CONTROL_L, SHIFT_MASK, '\0');
    app.key(KEY_CONTROL_L, SHIFT_MASK | CONTROL_MASK | RELEASE_MASK, '\0');
    assert!(app.h.enabled);
    app.type_str(" vieets ");
    assert_eq!(app.text, "viêt vieets viết ");
}

#[test]
fn ctrl_shift_with_other_key_does_not_toggle() {
    let mut app = FakeApp::new(|_| {});
    app.key(KEY_CONTROL_L, 0, '\0');
    app.key(KEY_SHIFT_L, CONTROL_MASK, '\0');
    app.key('C' as u32, CONTROL_MASK | SHIFT_MASK, 'C');
    app.key('C' as u32, CONTROL_MASK | SHIFT_MASK | RELEASE_MASK, 'C');
    app.key(KEY_SHIFT_L, CONTROL_MASK | SHIFT_MASK | RELEASE_MASK, '\0');
    app.key(KEY_CONTROL_L, CONTROL_MASK | RELEASE_MASK, '\0');
    assert!(app.h.enabled);
}

#[test]
fn punctuation_and_digits() {
    let mut app = FakeApp::new(|_| {});
    app.type_str("chaof, banj! 123 a1b\n");
    assert_eq!(app.text, "chào, bạn! 123 a1b\n");
}

#[test]
fn direct_mode() {
    let mut app = FakeApp::new(|c| c.direct_mode = true);
    app.type_str("Tieesng Vieejt raats hay.\n");
    assert_eq!(app.text, "Tiếng Việt rất hay.\n");
    assert_eq!(app.preedit, "");
    app.text.clear();
    app.type_str("nguowif");
    assert_eq!(app.text, "người");
    app.key(KEY_BACKSPACE, 0, '\0');
    assert_eq!(app.text, "ngươi");
    app.key(KEY_BACKSPACE, 0, '\0');
    assert_eq!(app.text, "ngươ");
    app.key(KEY_BACKSPACE, 0, '\0');
    assert_eq!(app.text, "nguo");
    app.type_str(" tools status\n");
    assert_eq!(app.text, "nguo tools status\n");
}

#[test]
fn vni_and_both() {
    let mut app = FakeApp::new(|c| c.method = "vni".into());
    app.type_str("Tie61ng Vie65t 123 a1 x2\n");
    assert_eq!(app.text, "Tiếng Việt 123 á x2\n");
    app.text.clear();
    app.type_str("vieets ");
    assert_eq!(app.text, "vieets ");
    let mut app2 = FakeApp::new(|c| c.method = "both".into());
    app2.type_str("vieets ngu7o72i ");
    assert_eq!(app2.text, "viết người ");
}

#[test]
fn alt_z_toggle() {
    let mut app = FakeApp::new(|c| c.toggle_key = "alt_z".into());
    app.type_str("vieet");
    let r = app.key('z' as u32, MOD1_MASK, 'z');
    assert!(r.handled && r.toggled);
    assert!(!app.h.enabled);
    assert_eq!(app.text, "viêt");
    app.type_str(" vieets");
    assert_eq!(app.text, "viêt vieets");
    app.key('z' as u32, MOD1_MASK, 'z');
    app.type_str(" vieets ");
    assert_eq!(app.text, "viêt vieets viết ");
}

#[test]
fn custom_hotkey_ctrl_shift_space() {
    let mut app = FakeApp::new(|c| c.toggle_key = "custom".into());
    app.type_str("vieet");
    let r = app.key(0x20, CONTROL_MASK | SHIFT_MASK, ' ');
    assert!(r.handled && r.toggled);
    assert!(!app.h.enabled);
    assert_eq!(app.text, "viêt");
    app.key(0x20, CONTROL_MASK | SHIFT_MASK | RELEASE_MASK, ' ');
    app.type_str(" vieets");
    assert_eq!(app.text, "viêt vieets");
    app.key(0x20, CONTROL_MASK | SHIFT_MASK, ' ');
    app.type_str(" vieets ");
    assert_eq!(app.text, "viêt vieets viết ");
    // Ctrl+Shift rồi thả không còn tác dụng
    app.key(KEY_CONTROL_L, 0, '\0');
    app.key(KEY_SHIFT_L, CONTROL_MASK, '\0');
    app.key(KEY_SHIFT_L, CONTROL_MASK | SHIFT_MASK | RELEASE_MASK, '\0');
    app.key(KEY_CONTROL_L, CONTROL_MASK | RELEASE_MASK, '\0');
    assert!(app.h.enabled);
}

#[test]
fn macros_expand() {
    let mut app = FakeApp::new(|_| {});
    app.type_str("vn, hn! ko\n");
    assert_eq!(app.text, "Việt Nam, Hà Nội! không\n");
    app.text.clear();
    app.type_str("VN");
    app.key(KEY_TAB, 0, '\0');
    assert_eq!(app.text, "VIỆT NAM");
    app.text.clear();
    app.type_str("file.vn a-vn (vn) ");
    assert_eq!(app.text, "file.vn a-vn (Việt Nam) ");
    // preedit hiển thị từ đang gõ, không phải nội dung bung
    app.type_str("vn");
    assert_eq!(app.preedit, "vn");
    app.type_str(" ");
    assert!(app.text.ends_with("Việt Nam "));
}

#[test]
fn macros_when_off() {
    let mut app = FakeApp::new(|c| c.macros_when_off = true);
    app.h.set_enabled(false);
    app.type_str("vn ");
    assert_eq!(app.text, "Việt Nam ");
    app.type_str("hello vn");
    app.key(KEY_RETURN, 0, '\0');
    assert_eq!(app.text, "Việt Nam hello Việt Nam\n");
    app.type_str("file.vn ");
    assert_eq!(app.text, "Việt Nam hello Việt Nam\nfile.vn ");
    let mut app2 = FakeApp::new(|_| {});
    app2.h.set_enabled(false);
    app2.type_str("vn ");
    assert_eq!(app2.text, "vn ");
}

#[test]
fn decomposed_charset() {
    use unicode_normalization::UnicodeNormalization;
    let nfd = |s: &str| s.nfd().collect::<String>();
    let mut app = FakeApp::new(|c| c.charset = "decomposed".into());
    app.type_str("vieets ");
    assert_eq!(app.text, nfd("viết "));
    assert_ne!(app.text, "viết ");
    let mut app2 = FakeApp::new(|c| {
        c.charset = "decomposed".into();
        c.direct_mode = true;
    });
    app2.type_str("vieets ");
    app2.type_str("nguowif");
    app2.key(KEY_BACKSPACE, 0, '\0');
    app2.type_str(" ");
    assert_eq!(app2.text, nfd("viết ngươi "));
}

const KEY_RIGHT: u32 = 0xFF53;
const KEY_LEFT: u32 = 0xFF51;
const KEY_UP: u32 = 0xFF52;
const KEY_HOME: u32 = 0xFF50;
const KEY_DELETE_: u32 = 0xFFFF;
const KEY_F5: u32 = 0xFFC2;

/// Đang gõ dở + mũi tên: chốt từ và NUỐT phím. Thả phím xuống ứng dụng ngay sau
/// khi commit sẽ khiến zsh-autosuggestions dán lại gợi ý cũ ("pnpm ddb:migrate").
#[test]
fn cursor_key_commits_and_swallows_while_composing() {
    for k in [KEY_RIGHT, KEY_LEFT, KEY_UP, KEY_HOME, KEY_DELETE_] {
        let mut app = FakeApp::new(|_| {});
        app.type_str("pnpm d");
        assert_eq!(app.preedit, "d");
        assert_eq!(app.text, "pnpm ");
        let r = app.key(k, 0, '\0');
        assert!(r.handled, "keyval={k:#x} phải nuốt phím");
        assert_eq!(app.text, "pnpm d");
        assert_eq!(app.preedit, "");
    }
}

/// Không gõ dở thì mũi tên đi thẳng xuống ứng dụng như cũ.
#[test]
fn cursor_key_passes_through_when_idle() {
    let mut app = FakeApp::new(|_| {});
    app.type_str("pnpm ");
    let r = app.key(KEY_RIGHT, 0, '\0');
    assert!(!r.handled);
    assert_eq!(app.text, "pnpm ");
}

/// Ấn lần hai: từ đã chốt nên phím xuống ứng dụng bình thường.
#[test]
fn second_cursor_key_press_passes_through() {
    let mut app = FakeApp::new(|_| {});
    app.type_str("chaof");
    assert_eq!(app.preedit, "chào");
    assert!(app.key(KEY_RIGHT, 0, '\0').handled);
    assert_eq!(app.text, "chào");
    assert!(!app.key(KEY_RIGHT, 0, '\0').handled);
    assert_eq!(app.text, "chào");
}

/// direct_mode: chữ đã nằm trong ứng dụng, không có gì để commit -> nhường phím.
#[test]
fn cursor_key_passes_through_in_direct_mode() {
    let mut app = FakeApp::new(|c| c.direct_mode = true);
    app.type_str("chaof");
    assert_eq!(app.text, "chào");
    let r = app.key(KEY_RIGHT, 0, '\0');
    assert!(!r.handled);
    assert_eq!(app.text, "chào");
}

/// Phím chức năng khác (F1..F12) vẫn commit rồi nhường phím như trước.
#[test]
fn function_key_still_commits_and_passes() {
    let mut app = FakeApp::new(|_| {});
    app.type_str("chaof");
    let r = app.key(KEY_F5, 0, '\0');
    assert!(!r.handled);
    assert_eq!(app.text, "chào");
    assert_eq!(app.preedit, "");
}

/// "mate" (không dấu, có 'e' cuối) không được sinh chữ thừa.
#[test]
fn plain_english_word_no_duplicate() {
    for on in [false, true] {
        let mut app = FakeApp::new(|c| c.free_marking = on);
        app.type_str("mate ");
        assert_eq!(app.text, "mate ", "free_marking={on}");
        assert_eq!(app.preedit, "");
    }
}

/// Mất focus giữa chừng: IBus tự commit preedit, engine không commit lại.
#[test]
fn focus_out_midword_no_duplicate() {
    let mut app = FakeApp::new(|_| {});
    app.type_str("mate");
    assert_eq!(app.preedit, "mate");
    assert_eq!(app.text, "");
    app.focus_out();
    assert_eq!(app.text, "mate");
}

const KEY_D: u32 = 'd' as u32;

/// Phím tắt "Không gạch chân" chỉ đổi chế độ cho ô nhập ĐANG focus: bật cho
/// Chrome không được kéo theo terminal, và không ghi vào config.json.
#[test]
fn direct_key_toggles_only_current_focus() {
    let mut app = FakeApp::new(|c| c.direct_key = "<Control><Shift>d".into());
    app.type_str("chaof");
    assert_eq!(app.preedit, "chào");
    assert_eq!(app.text, "");

    // bật: từ đang dở được chốt, phím tắt bị nuốt
    let r = app.key(KEY_D, CONTROL_MASK | SHIFT_MASK, 'd');
    assert!(r.handled && r.toggled);
    assert_eq!(app.text, "chào");
    assert_eq!(app.preedit, "");
    assert!(app.h.use_direct());
    assert!(app.h.direct_is_temp());
    assert!(!app.h.direct_mode, "không được ghi đè tuỳ chọn đã lưu");

    // chữ đi thẳng vào ứng dụng, không còn preedit
    app.type_str("banj");
    assert_eq!(app.preedit, "");
    assert_eq!(app.text, "chàobạn");

    // đổi cửa sổ -> quên đặt tạm, quay lại preedit
    app.focus_out();
    assert!(!app.h.use_direct());
    assert!(!app.h.direct_is_temp());
    app.text.clear();
    app.type_str("chaof");
    assert_eq!(app.preedit, "chào");
}

/// Bấm phím tắt lần hai trong cùng ô nhập thì về đúng tuỳ chọn đã lưu.
#[test]
fn direct_key_second_press_returns_to_config() {
    let mut app = FakeApp::new(|c| c.direct_key = "<Control><Shift>d".into());
    assert!(app.key(KEY_D, CONTROL_MASK | SHIFT_MASK, 'd').handled);
    assert!(app.h.use_direct());
    assert!(app.key(KEY_D, CONTROL_MASK | SHIFT_MASK, 'd').handled);
    assert!(!app.h.use_direct());
    assert!(!app.h.direct_is_temp(), "về đúng cấu hình thì bỏ hẳn đặt tạm");
}

/// direct_mode bật sẵn trong config: phím tắt tắt tạm cho ô này (dùng ngược lại).
#[test]
fn direct_key_can_disable_for_one_field() {
    let mut app = FakeApp::new(|c| {
        c.direct_mode = true;
        c.direct_key = "<Control><Shift>d".into();
    });
    assert!(app.h.use_direct());
    app.key(KEY_D, CONTROL_MASK | SHIFT_MASK, 'd');
    assert!(!app.h.use_direct());
    assert!(app.h.direct_mode, "cấu hình đã lưu không đổi");
    app.focus_out();
    assert!(app.h.use_direct());
}

/// Không đặt phím tắt thì Ctrl+Shift+D vẫn là tổ hợp bình thường của ứng dụng.
#[test]
fn direct_key_unset_passes_shortcut_through() {
    let mut app = FakeApp::new(|_| {});
    app.type_str("chaof");
    let r = app.key(KEY_D, CONTROL_MASK | SHIFT_MASK, 'd');
    assert!(!r.handled);
    assert!(!r.toggled);
    assert_eq!(app.text, "chào");
}

/// Cờ khả năng đo thật trên GNOME Wayland (xem ~/.cache/ibus-vikey/vikey.log):
///   Adminer, ô contenteditable trong Chrome  caps=0x29  PREEDIT|FOCUS|SURROUNDING
///   terminal VTE                             caps=0x09  PREEDIT|FOCUS
/// Ô có SURROUNDING nhận được DeleteSurroundingText nên gõ trực tiếp an toàn, và
/// tránh được preedit vốn bị script của trang web phá. Terminal không có cờ đó
/// nên giữ preedit.
const CAPS_BROWSER: u32 = 0x29;
const CAPS_TERMINAL: u32 = 0x09;

#[test]
fn auto_direct_in_browser_preedit_in_terminal() {
    let mut app = FakeApp::new(|_| {});

    app.h.set_client_caps(CAPS_BROWSER);
    assert!(app.h.use_direct(), "ô của trình duyệt phải gõ trực tiếp");
    assert!(app.h.client_has_surrounding());
    app.type_str("tieengs");
    assert_eq!(app.preedit, "", "không được tạo composition trong trình duyệt");
    assert_eq!(app.text, "tiếng");

    // đổi sang terminal: quay lại preedit
    app.focus_out();
    app.text.clear();
    app.h.set_client_caps(CAPS_TERMINAL);
    assert!(!app.h.use_direct(), "terminal phải giữ preedit");
    assert!(!app.h.client_has_surrounding());
    app.type_str("tieengs");
    assert_eq!(app.preedit, "tiếng");
    assert_eq!(app.text, "");

    // và tuỳ chọn đã lưu không bị đụng tới
    assert!(!app.h.direct_mode);
}

/// Tắt auto_direct thì mọi ô nhập đều dùng preedit như trước.
#[test]
fn auto_direct_can_be_disabled() {
    let mut app = FakeApp::new(|c| c.auto_direct = false);
    app.h.set_client_caps(CAPS_BROWSER);
    assert!(!app.h.use_direct());
    app.type_str("chaof");
    assert_eq!(app.preedit, "chào");
}

/// Client không khai báo hỗ trợ preedit -> gõ trực tiếp kể cả khi tắt auto_direct.
#[test]
fn no_preedit_capability_forces_direct() {
    let mut app = FakeApp::new(|c| c.auto_direct = false);
    assert!(!app.h.use_direct());
    app.h.set_client_caps(0x0A); // focus + auxtext, KHÔNG preedit, KHÔNG surrounding
    assert!(app.h.use_direct());
    assert!(!app.h.direct_mode, "không được ghi đè tuỳ chọn của người dùng");
    app.type_str("chaof");
    assert_eq!(app.preedit, "");
    assert_eq!(app.text, "chào");
}

/// caps = 0 nghĩa là chưa biết, không được đổi gì.
#[test]
fn unknown_capability_keeps_preedit() {
    let mut app = FakeApp::new(|_| {});
    app.h.set_client_caps(0);
    assert!(!app.h.use_direct());
    assert!(app.h.client_has_surrounding(), "chưa biết thì đừng gửi Backspace giả");
}
