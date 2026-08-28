mod sidecar;

use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Listener, Manager,
};
use tauri_plugin_notification::NotificationExt;

/// Faz 9 (1.12): tray + bildirim metinleri icin yerel dizeler.
/// Rust tarafinda ayri bir i18n sozlugu yok; tr/en sabitleri yeterli.
#[derive(Clone, Copy)]
struct L10n {
    show: &'static str,
    quit: &'static str,
    done_title: &'static str,
    fail_title: &'static str,
    ok_body: &'static str,
    err_body: &'static str,
}

const TR: L10n = L10n {
    show: "Göster",
    quit: "Çıkış",
    done_title: "PkgForge: Dönüştürme tamamlandı",
    fail_title: "PkgForge: Dönüştürme başarısız",
    ok_body: "Paket başarıyla işlendi.",
    err_body: "İşlem sırasında bir hata oluştu.",
};

const EN: L10n = L10n {
    show: "Show",
    quit: "Quit",
    done_title: "PkgForge: Conversion complete",
    fail_title: "PkgForge: Conversion failed",
    ok_body: "Package processed successfully.",
    err_body: "An error occurred during the operation.",
};

/// Aktif profilin settings.json'ini okur (profil farkindali); best-effort.
fn read_settings() -> Option<serde_json::Value> {
    let home = std::env::var("HOME").ok()?;
    let base = std::path::PathBuf::from(home).join(".config").join("pkgforge");
    let mut settings_path = base.join("settings.json");
    if let Ok(profile) = std::fs::read_to_string(base.join("active_profile")) {
        let p = profile.trim();
        if !p.is_empty() && p != "default" {
            let candidate = base.join("profiles").join(p).join("settings.json");
            if candidate.exists() {
                settings_path = candidate;
            }
        }
    }
    let raw = std::fs::read_to_string(settings_path).ok()?;
    serde_json::from_str(&raw).ok()
}

/// Secili UI dilini settings.json'dan okur; okunamazsa Turkce'ye duser.
fn load_language() -> &'static L10n {
    let v = match read_settings() {
        Some(v) => v,
        None => return &TR,
    };
    match v.get("language").and_then(|l| l.as_str()) {
        Some("en") => &EN,
        _ => &TR,
    }
}

/// Faz 10 (5.5): masaustu bildirimleri acik mi? Varsayilan true. Her olayda
/// yeniden okunur, boylece ayar degisikligi yeniden baslatma gerektirmez.
fn notifications_enabled() -> bool {
    match read_settings() {
        Some(v) => v.get("notifications").and_then(|n| n.as_bool()).unwrap_or(true),
        None => true,
    }
}

/// Build the system tray icon with a small menu.
fn setup_tray(app: &tauri::AppHandle, l10n: &L10n) -> Result<(), Box<dyn std::error::Error>> {
    let show = MenuItem::with_id(app, "show", l10n.show, true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", l10n.quit, true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&show, &quit])?;

    let icon = app.default_window_icon().cloned().unwrap();

    TrayIconBuilder::new()
        .icon(icon)
        .tooltip("PkgForge")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| match event.id.as_ref() {
            "show" => {
                if let Some(win) = app.get_webview_window("main") {
                    let _ = win.show();
                    let _ = win.unminimize();
                    let _ = win.set_focus();
                }
            }
            "quit" => {
                app.exit(0);
            }
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                let app = tray.app_handle();
                if let Some(win) = app.get_webview_window("main") {
                    let _ = win.show();
                    let _ = win.unminimize();
                    let _ = win.set_focus();
                }
            }
        })
        .build(app)?;

    Ok(())
}

/// Forward pipeline completion events to desktop notifications.
fn setup_notifications(app: &tauri::AppHandle, l10n: L10n) {
    let handle = app.clone();
    app.listen("event/finished", move |event| {
        if !notifications_enabled() {
            return;
        }
        let payload: serde_json::Value = match serde_json::from_str(event.payload()) {
            Ok(v) => v,
            Err(_) => return,
        };
        let success = payload.get("success").and_then(|s| s.as_bool()).unwrap_or(false);
        let message = payload
            .get("message")
            .and_then(|m| m.as_str())
            .unwrap_or("")
            .to_string();
        let title = if success { l10n.done_title } else { l10n.fail_title };
        let body = if message.is_empty() {
            if success { l10n.ok_body } else { l10n.err_body }
        } else {
            &message
        };
        let _ = handle
            .notification()
            .builder()
            .title(title)
            .body(body)
            .show();
    });
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(sidecar::Sidecar::new())
        .setup(|app| {
            sidecar::spawn(app.handle())?;
            let l10n = *load_language();
            if let Err(e) = setup_tray(app.handle(), &l10n) {
                eprintln!("tray setup failed: {e}");
            }
            setup_notifications(app.handle(), l10n);
            Ok(())
        })
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_notification::init())
        .invoke_handler(tauri::generate_handler![sidecar::rpc_call])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if let tauri::RunEvent::Exit = event {
                let state = app_handle.state::<sidecar::Sidecar>();
                state.kill();
            }
        });
}
