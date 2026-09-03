// ibus_main.rs - Kết nối tới ibus-daemon, phục vụ Factory/Engine (chế độ --ibus).

use crate::engine_service::{EngineLifecycle, EngineService};
use futures_util::StreamExt;
use std::path::PathBuf;
use zbus::{Connection, ObjectServer};
use zvariant::OwnedObjectPath;

/// Tìm địa chỉ D-Bus của ibus-daemon: $IBUS_ADDRESS hoặc file trong
/// $XDG_CONFIG_HOME/ibus/bus/ (chọn file khớp DISPLAY/WAYLAND_DISPLAY, nếu
/// không thì file mới nhất).
pub fn find_address() -> Option<String> {
    if let Ok(a) = std::env::var("IBUS_ADDRESS") {
        if !a.is_empty() {
            return Some(strip_guid(&a));
        }
    }
    let dir = crate::config::config_dir().parent()?.join("ibus").join("bus");
    let entries: Vec<PathBuf> = std::fs::read_dir(&dir)
        .ok()?
        .flatten()
        .map(|e| e.path())
        .filter(|p| p.is_file())
        .collect();
    if entries.is_empty() {
        return None;
    }
    let mut suffixes = Vec::new();
    if let Ok(d) = std::env::var("WAYLAND_DISPLAY") {
        if !d.is_empty() {
            suffixes.push(format!("-unix-{}", d));
        }
    }
    if let Ok(d) = std::env::var("DISPLAY") {
        let num = d.rsplit(':').next().unwrap_or("0");
        let num = num.split('.').next().unwrap_or("0");
        suffixes.push(format!("-unix-{}", num));
        suffixes.push(format!("-unix-wayland-{}", num));
    }
    let pick = entries
        .iter()
        .find(|p| {
            let name = p.file_name().unwrap_or_default().to_string_lossy().to_string();
            suffixes.iter().any(|s| name.ends_with(s.as_str()))
        })
        .cloned()
        .or_else(|| {
            let mut es = entries.clone();
            es.sort_by_key(|p| std::fs::metadata(p).and_then(|m| m.modified()).ok());
            es.last().cloned()
        })?;
    let content = std::fs::read_to_string(pick).ok()?;
    for line in content.lines() {
        if let Some(rest) = line.trim().strip_prefix("IBUS_ADDRESS=") {
            return Some(strip_guid(rest));
        }
    }
    None
}

fn strip_guid(addr: &str) -> String {
    addr.split(',')
        .filter(|part| !part.trim_start().starts_with("guid="))
        .collect::<Vec<_>>()
        .join(",")
}

pub struct Factory {
    counter: u32,
}

#[zbus::interface(name = "org.freedesktop.IBus.Factory")]
impl Factory {
    async fn create_engine(
        &mut self,
        #[zbus(connection)] conn: &Connection,
        #[zbus(object_server)] server: &ObjectServer,
        name: String,
    ) -> zbus::fdo::Result<OwnedObjectPath> {
        if name != "vikey" {
            return Err(zbus::fdo::Error::Failed(format!("Không có engine '{}'", name)));
        }
        self.counter += 1;
        let path: OwnedObjectPath = format!("/org/freedesktop/IBus/Engine/ViKey/{}", self.counter)
            .try_into()
            .map_err(|e| zbus::fdo::Error::Failed(format!("{:?}", e)))?;
        let engine = EngineService::new(conn.clone(), path.clone());
        server
            .at(&path, engine)
            .await
            .map_err(|e| zbus::fdo::Error::Failed(e.to_string()))?;
        let _ = server.at(&path, EngineLifecycle { path: path.clone() }).await;
        Ok(path)
    }
}

pub async fn run() -> Result<(), Box<dyn std::error::Error>> {
    let addr = find_address().ok_or("Không tìm thấy địa chỉ ibus-daemon (IBUS_ADDRESS / ~/.config/ibus/bus). ibus-daemon có đang chạy không?")?;
    let conn = zbus::connection::Builder::address(addr.as_str())?
        .serve_at("/org/freedesktop/IBus/Factory", Factory { counter: 0 })?
        .build()
        .await?;
    conn.request_name("org.freedesktop.IBus.ViKey").await?;

    // Chạy tới khi ibus-daemon đóng kết nối (đăng xuất / ibus restart) hoặc bị kill.
    let mut stream = zbus::MessageStream::from(&conn);
    let wait_close = async {
        while let Some(msg) = stream.next().await {
            if msg.is_err() {
                break;
            }
        }
    };
    tokio::select! {
        _ = wait_close => {},
        _ = tokio::signal::ctrl_c() => {},
    }
    Ok(())
}
