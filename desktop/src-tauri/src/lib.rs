mod sidecar;

use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Listener, Manager,
};
use tauri_plugin_notification::NotificationExt;

/// Build the system tray icon with a small menu.
fn setup_tray(app: &tauri::AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    let show = MenuItem::with_id(app, "show", "Göster", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Çıkış", true, None::<&str>)?;
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
fn setup_notifications(app: &tauri::AppHandle) {
    let handle = app.clone();
    app.listen("event/finished", move |event| {
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
        let title = if success { "PkgForge: Dönüştürme tamamlandı" } else { "PkgForge: Dönüştürme başarısız" };
        let body = if message.is_empty() {
            if success { "Paket başarıyla işlendi." } else { "İşlem sırasında bir hata oluştu." }
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
            if let Err(e) = setup_tray(app.handle()) {
                eprintln!("tray setup failed: {e}");
            }
            setup_notifications(app.handle());
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
