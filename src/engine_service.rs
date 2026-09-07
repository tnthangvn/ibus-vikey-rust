// engine_service.rs - Đối tượng D-Bus của engine: org.freedesktop.IBus.Engine
// (kèm org.freedesktop.IBus.Service). Nói chuyện trực tiếp với ibus-daemon,
// không phụ thuộc libibus/GObject.

use crate::config::{self, Config};
use crate::ibus_serde::{self as ser, PropSpec};
use crate::keyhandler::{HandleResult, KeyHandler};
use crate::keyval::keyval_to_char;
use std::time::{Duration, SystemTime};
use zbus::object_server::SignalEmitter;
use zbus::Connection;
use zvariant::{OwnedValue, Structure, Value};

const IFACE: &str = "org.freedesktop.IBus.Engine";

pub struct EngineService {
    conn: Connection,
    path: zvariant::OwnedObjectPath,
    handler: KeyHandler,
    cfg: Config,
    cfg_mtime: Option<SystemTime>,
    preedit_visible: bool,
}

fn icon_dir() -> String {
    std::env::var("VIKEY_ICON_DIR").unwrap_or_else(|_| "/usr/share/ibus-vikey/icons".into())
}

impl EngineService {
    pub fn new(conn: Connection, path: zvariant::OwnedObjectPath) -> EngineService {
        let cfg = config::load();
        let handler = KeyHandler::new(&cfg);
        EngineService {
            conn,
            path,
            handler,
            cfg,
            cfg_mtime: config::mtime(),
            preedit_visible: false,
        }
    }

    // ------------------------------------------------------------ signals
    async fn emit<B>(&self, name: &str, body: &B)
    where
        B: serde::ser::Serialize + zvariant::DynamicType,
    {
        let _ = self
            .conn
            .emit_signal(None::<zbus::names::BusName>, &self.path, IFACE, name, body)
            .await;
    }

    async fn commit_text(&self, s: &str) {
        self.emit("CommitText", &(Value::Structure(ser::text(s, false)),)).await;
    }

    async fn show_preedit(&mut self, s: &str) {
        if s.is_empty() {
            if self.preedit_visible {
                self.emit("HidePreeditText", &()).await;
                self.preedit_visible = false;
            }
            return;
        }
        let n = s.chars().count() as u32;
        // COMMIT: khi mất focus / reset, IBus (hoặc GNOME Shell) tự commit phần
        // đang gõ đúng một lần; engine không commit lại -> không duplicate.
        // Chú ý: signal vẫn tên "UpdatePreeditText", mode là đối số thứ 4 ("(vubu)")
        self.emit(
            "UpdatePreeditText",
            &(Value::Structure(ser::text(s, true)), n, true, ser::PREEDIT_FOCUS_MODE_COMMIT),
        )
        .await;
        self.preedit_visible = true;
    }

    /// Ẩn preedit TRƯỚC rồi mới xoá/commit, để không còn preedit nào có thể bị
    /// commit lần nữa khi đổi focus.
    async fn apply_commit(&mut self, text: Option<&str>, delete: usize) {
        if self.preedit_visible {
            self.emit("HidePreeditText", &()).await;
            self.preedit_visible = false;
        }
        if delete > 0 {
            self.emit("DeleteSurroundingText", &(-(delete as i32), delete as u32)).await;
        }
        if let Some(t) = text {
            if !t.is_empty() {
                self.commit_text(t).await;
            }
        }
    }

    fn log(&self, line: &str) {
        if self.cfg.debug_log {
            config::log_line(line);
        }
    }

    async fn apply_result(&mut self, r: &HandleResult) {
        if r.commit.is_some() || r.delete > 0 {
            self.apply_commit(r.commit.as_deref(), r.delete).await;
        }
        if let Some(p) = &r.preedit {
            self.show_preedit(p).await;
        }
        if r.toggled {
            self.save_cfg();
            self.update_props().await;
        }
    }

    // ---------------------------------------------------------- properties
    fn checked(b: bool) -> u32 {
        if b {
            ser::PROP_STATE_CHECKED
        } else {
            ser::PROP_STATE_UNCHECKED
        }
    }

    fn build_props(&self) -> Vec<PropSpec> {
        let h = &self.handler;
        let on = h.enabled;
        let tl = config::toggle_label(&Config {
            toggle_key: h.toggle_key.clone(),
            toggle_custom: h.toggle_custom.clone(),
            ..Config::default()
        });
        let hint = if h.toggle_key == "none" { String::new() } else { format!(" – {}", tl) };

        let mut props = Vec::new();

        let mut mode = PropSpec::new(
            "InputMode",
            ser::PROP_TYPE_NORMAL,
            &if on {
                format!("Tiếng Việt: BẬT{}", hint)
            } else {
                format!("Tiếng Việt: TẮT (đang gõ tiếng Anh){}", hint)
            },
        )
        .tooltip("Bấm để bật/tắt tiếng Việt");
        mode.symbol = if on { "Vi".into() } else { "En".into() };
        mode.icon = format!("{}/{}", icon_dir(), if on { "vikey-vi.svg" } else { "vikey-en.svg" });
        props.push(mode);

        let method = h.engine_method_str();
        let method_label = |v: &str| match v {
            "vni" => "VNI",
            "both" => "Telex + VNI",
            _ => "Telex",
        };
        let mut m = PropSpec::new(
            "method",
            ser::PROP_TYPE_MENU,
            &format!("Kiểu gõ: {}", method_label(&method)),
        );
        for v in config::METHODS {
            let mut p = PropSpec::new(&format!("method:{}", v), ser::PROP_TYPE_RADIO, method_label(v));
            p.state = Self::checked(v == method);
            m.sub_props.push(p);
        }
        props.push(m);

        let mut t = PropSpec::new("toggle_key", ser::PROP_TYPE_MENU, &format!("Phím chuyển Việt/Anh: {}", tl));
        for v in config::TOGGLE_KEYS {
            let label = match v {
                "ctrl_shift" => "Ctrl+Shift".to_string(),
                "alt_z" => "Alt+Z".to_string(),
                "custom" => format!("Tuỳ chỉnh ({})", crate::hotkey::label(&h.toggle_custom)),
                _ => "Không dùng".to_string(),
            };
            let mut p = PropSpec::new(&format!("toggle_key:{}", v), ser::PROP_TYPE_RADIO, &label);
            p.state = Self::checked(v == h.toggle_key);
            t.sub_props.push(p);
        }
        props.push(t);

        let toggles: [(&str, &str, &str, bool); 5] = [
            (
                "spell_check",
                "Kiểm tra chính tả (khôi phục phím với từ sai)",
                "Từ không phải tiếng Việt (windows, status...) sẽ giữ nguyên phím gõ",
                h.engine.spell_check,
            ),
            ("modern_tone", "Đặt dấu kiểu mới (hoà, khoẻ, thuý)", "Tắt: hòa, khỏe, thúy", h.engine.modern_tone),
            (
                "free_marking",
                "Bỏ dấu tự do (gõ dấu ở cuối từ: dend → đen)",
                "Phím dd / aa ee oo (6 9 với VNI) đặt được ở cuối từ, không cần đứng ngay sau chữ gốc. Tắt: phải gõ ddeen, tieengs",
                h.engine.free_marking,
            ),
            (
                "macros",
                "Gõ tắt (vn → Việt Nam...)",
                "Bung viết tắt khi bấm space/dấu câu/Enter. Bảng: ~/.config/ibus-vikey/macros.txt",
                h.macros_enabled,
            ),
            (
                "direct_mode",
                &{
                    let mut s = "Không gạch chân (gõ trực tiếp)".to_string();
                    if !h.direct_key.is_empty() {
                        s.push_str(&format!(" – {}", crate::hotkey::label(&h.direct_key)));
                    }
                    if h.direct_is_temp() {
                        s.push_str(" [tạm cho ô này]");
                    }
                    s
                },
                "Không dùng preedit; sửa chữ bằng delete_surrounding_text. Cần bật với ô contenteditable có tô màu cú pháp (Adminer…); có thể lặp chữ ở terminal/app không hỗ trợ",
                h.use_direct(),
            ),
        ];
        for (key, label, tip, val) in toggles {
            let mut p = PropSpec::new(key, ser::PROP_TYPE_TOGGLE, label).tooltip(tip);
            p.state = Self::checked(val);
            props.push(p);
        }

        props.push(
            PropSpec::new("setup", ser::PROP_TYPE_NORMAL, "Cài đặt ViKey…")
                .tooltip("Mở cửa sổ cài đặt: tuỳ chọn và bảng gõ tắt"),
        );
        props
    }

    async fn register_props(&self) {
        let list: Vec<Structure> = self.build_props().iter().map(ser::property).collect();
        self.emit("RegisterProperties", &(Value::Structure(ser::prop_list(list)),)).await;
    }

    async fn update_props(&self) {
        for p in self.build_props() {
            self.emit("UpdateProperty", &(Value::Structure(ser::property(&p)),)).await;
        }
    }

    // --------------------------------------------------------------- config
    fn save_cfg(&mut self) {
        let h = &self.handler;
        self.cfg = Config {
            method: h.engine_method_str(),
            toggle_key: h.toggle_key.clone(),
            toggle_custom: h.toggle_custom.clone(),
            charset: if h.charset_decomposed { "decomposed".into() } else { "precomposed".into() },
            enabled: h.enabled,
            spell_check: h.engine.spell_check,
            modern_tone: h.engine.modern_tone,
            free_marking: h.engine.free_marking,
            macros: h.macros_enabled,
            macros_when_off: h.macros_when_off,
            direct_mode: h.direct_mode,
            direct_key: h.direct_key.clone(),
            debug_log: self.cfg.debug_log,
        };
        let _ = config::save(&self.cfg);
        self.cfg_mtime = config::mtime();
    }

    async fn reload_cfg_if_changed(&mut self) {
        let m = config::mtime();
        if m == self.cfg_mtime {
            return;
        }
        self.cfg_mtime = m;
        self.cfg = config::load();
        let pending = self.handler.configure(&self.cfg);
        if !pending.is_empty() {
            self.apply_commit(Some(&pending), 0).await;
        }
        // trạng thái Việt/Anh dùng chung cho mọi cửa sổ
        if self.cfg.enabled != self.handler.enabled {
            let p = self.handler.set_enabled(self.cfg.enabled);
            self.apply_commit(if p.is_empty() { None } else { Some(&p) }, 0).await;
        }
        self.update_props().await;
    }
}

#[zbus::interface(name = "org.freedesktop.IBus.Engine")]
impl EngineService {
    async fn process_key_event(&mut self, keyval: u32, _keycode: u32, state: u32) -> bool {
        let ch = keyval_to_char(keyval);
        let r = self.handler.handle(keyval, state, ch);
        self.apply_result(&r).await;
        r.handled
    }

    async fn focus_in(&mut self) {
        self.reload_cfg_if_changed().await;
        self.log("focus_in");
        self.handler.macros.maybe_reload(Duration::from_millis(0));
        self.register_props().await;
    }

    async fn focus_out(&mut self) {
        self.log("focus_out");
        // IBus đã commit preedit (chế độ COMMIT); chỉ cần quên từ đang soạn.
        self.handler.clear();
        self.preedit_visible = false;
    }

    async fn reset(&mut self) {
        self.handler.clear();
        self.preedit_visible = false;
    }

    async fn enable(&mut self) {
        self.reload_cfg_if_changed().await;
    }

    async fn disable(&mut self) {
        self.handler.clear();
        self.preedit_visible = false;
    }

    async fn property_activate(&mut self, prop_name: String, state: u32) {
        let checked = state == ser::PROP_STATE_CHECKED;
        let mut cfg = self.cfg.clone();
        match prop_name.as_str() {
            "InputMode" => {
                let p = self.handler.set_enabled(!self.handler.enabled);
                self.apply_commit(if p.is_empty() { None } else { Some(&p) }, 0).await;
                self.save_cfg();
                self.update_props().await;
                return;
            }
            "setup" => {
                if let Ok(exe) = std::env::current_exe() {
                    let _ = std::process::Command::new(exe)
                        .arg("--setup")
                        .stdout(std::process::Stdio::null())
                        .stderr(std::process::Stdio::null())
                        .spawn();
                }
                return;
            }
            "spell_check" => cfg.spell_check = checked,
            "modern_tone" => cfg.modern_tone = checked,
            "free_marking" => cfg.free_marking = checked,
            "macros" => cfg.macros = checked,
            "direct_mode" => {
                self.handler.clear_direct_temp();
                cfg.direct_mode = checked;
            }
            other => {
                if let Some(v) = other.strip_prefix("method:") {
                    if !checked || !config::METHODS.contains(&v) {
                        return;
                    }
                    cfg.method = v.to_string();
                } else if let Some(v) = other.strip_prefix("toggle_key:") {
                    if !checked || !config::TOGGLE_KEYS.contains(&v) {
                        return;
                    }
                    cfg.toggle_key = v.to_string();
                } else {
                    return;
                }
            }
        }
        cfg.enabled = self.handler.enabled;
        let pending = self.handler.configure(&cfg);
        if !pending.is_empty() {
            self.apply_commit(Some(&pending), 0).await;
        }
        self.save_cfg();
        self.update_props().await;
    }

    // ------- các phương thức còn lại của giao diện: không cần xử lý
    /// IBus báo khả năng của ô nhập. Client không có IBUS_CAP_PREEDIT_TEXT thì
    /// gửi preedit là vô nghĩa -> tự lùi về lối gõ trực tiếp (không ghi config).
    async fn set_capabilities(&mut self, caps: u32) {
        self.log(&format!(
            "caps=0x{caps:02x} preedit={} auxtext={} lookup={} property={} surrounding={}",
            caps & 0x01 != 0,
            caps & 0x02 != 0,
            caps & 0x04 != 0,
            caps & 0x08 != 0,
            caps & 0x40 != 0,
        ));
        let pending = self.handler.set_client_caps(caps);
        if !pending.is_empty() {
            self.apply_commit(Some(&pending), 0).await;
        }
    }
    async fn set_cursor_location(&mut self, _x: i32, _y: i32, _w: i32, _h: i32) {}
    async fn set_surrounding_text(&mut self, _text: OwnedValue, _cursor: u32, _anchor: u32) {}
    async fn page_up(&mut self) {}
    async fn page_down(&mut self) {}
    async fn cursor_up(&mut self) {}
    async fn cursor_down(&mut self) {}
    async fn candidate_clicked(&mut self, _index: u32, _button: u32, _state: u32) {}
    async fn property_show(&mut self, _prop_name: String) {}
    async fn property_hide(&mut self, _prop_name: String) {}

    /// Thuộc tính ContentType (daemon Set khi đổi loại ô nhập) - không cần xử lý.
    #[zbus(property)]
    async fn content_type(&self) -> (u32, u32) {
        (0, 0)
    }
    #[zbus(property)]
    async fn set_content_type(&mut self, v: (u32, u32)) {
        self.log(&format!("content_type purpose={} hints=0x{:x}", v.0, v.1));
    }
}

/// org.freedesktop.IBus.Service (daemon gọi Destroy khi bỏ engine).
pub struct EngineLifecycle {
    pub path: zvariant::OwnedObjectPath,
}

#[zbus::interface(name = "org.freedesktop.IBus.Service")]
impl EngineLifecycle {
    async fn destroy(
        &mut self,
        #[zbus(object_server)] server: &zbus::ObjectServer,
        #[zbus(signal_emitter)] _emitter: SignalEmitter<'_>,
    ) {
        let path = self.path.clone();
        let _ = server.remove::<EngineService, _>(&path).await;
        let _ = server.remove::<EngineLifecycle, _>(&path).await;
    }
}
