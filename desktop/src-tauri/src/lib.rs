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
    queued_title: &'static str,
    queued_body: &'static str,
}

const TR: L10n = L10n {
    show: "Göster",
    quit: "Çıkış",
    done_title: "PkgForge: Dönüştürme tamamlandı",
    fail_title: "PkgForge: Dönüştürme başarısız",
    ok_body: "Paket başarıyla işlendi.",
    err_body: "İşlem sırasında bir hata oluştu.",
    queued_title: "PkgForge: kuyruğa eklendi",
    queued_body: "Dosyalar zaten açık olan pencerenin iş kuyruğuna eklendi (Toplu sekmesi).",
};

const EN: L10n = L10n {
    show: "Show",
    quit: "Quit",
    done_title: "PkgForge: Conversion complete",
    fail_title: "PkgForge: Conversion failed",
    ok_body: "Package processed successfully.",
    err_body: "An error occurred during the operation.",
    queued_title: "PkgForge: added to queue",
    queued_body: "Files were queued in the window that was already open (Batch tab).",
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

/// argv'den dönüştürmek için verilen paket dosyalarını çıkarır.
///
/// Tauri kabuğu argv'yi webview'a kendi geçirmez; `pkgforge --file X.deb` ve
/// dosya yöneticisinin "Birlikte aç"ı (`Exec=pkgforge desktop %f`) böyle ulaşıyor.
/// Bayraklar (`-f`, `--lang tr`) atlanır, yalnızca gerçek dosyalar ve mutlak
/// yollar döner; sıira ve tekillik korunur.
fn initial_files_from_args(args: &[String]) -> Vec<String> {
    const EN_FAZLA: usize = 64;
    let mut out: Vec<String> = Vec::new();
    for arg in args.iter().skip(1) {
        if arg.starts_with('-') || arg.is_empty() {
            continue;
        }
        let Ok(path) = std::fs::canonicalize(std::path::Path::new(arg)) else {
            continue;
        };
        if !path.is_file() {
            continue;
        }
        let text = path.to_string_lossy().into_owned();
        if !out.contains(&text) {
            out.push(text);
        }
        if out.len() >= EN_FAZLA {
            break;
        }
    }
    out
}

/// Webview'ın açılışta sorduğu CLI/dosya-yöneticisi girdi listesi.
#[tauri::command]
fn initial_files() -> Vec<String> {
    initial_files_from_args(&std::env::args().collect::<Vec<String>>())
}

/// Uygulama açıkken gelen ikinci "Birlikte aç" örneğini birleştirir.
///
/// Ölçülen (2026-10-16): kilitsiz her tıklama yeni kabuk + yeni sidecar
/// açıyordu. Dosyalar webview olayıyla DEĞİL, kanıtlı sidecar RPC'si ve kalıcı
/// `queue.db` üzerinden devredilir; pencere öne alınır ve bildirim gönderilir.
/// (Not: 2026-10-16'daki "webview olayı ulaşmadı" gözlemi 2026-10-17'de
/// deneme düzeniğine bağlandı — `window.__TAURI__` globali ve `core:event`
/// ACL yetkisi eksikmiş; ürün yapılandırması doğru, sidecar `event/*`
/// itmeleri gerçek webview'de uçtan uca kanıtlandı, bkz.
/// `docs/DEAD_CODE_AUDIT.md` → "Bilinmeyen → ÇÖZÜLDÜ".) RPC kanalı yine de
/// burada daha güçlüdür: `queue.db` kalıcıdır, ikinci dosya hiçbir koşulda
/// sessizce düşmez.
fn forward_new_instance(app: &tauri::AppHandle, args: Vec<String>, _cwd: String) {
    if let Some(win) = app.get_webview_window("main") {
        let _ = win.unminimize();
        let _ = win.show();
        let _ = win.set_focus();
    }
    let files = initial_files_from_args(&args);
    if files.is_empty() {
        return;
    }
    let count = files.len();
    sidecar::queue_files(app, files);
    let l10n = *load_language();
    if notifications_enabled() {
        let _ = app
            .notification()
            .builder()
            .title(l10n.queued_title)
            .body(format!("{} ({count})", l10n.queued_body))
            .show();
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(sidecar::Sidecar::new())
        .plugin(tauri_plugin_single_instance::init(forward_new_instance))
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
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            sidecar::rpc_call,
            initial_files
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if let tauri::RunEvent::Exit = event {
                let state = app_handle.state::<sidecar::Sidecar>();
                state.kill();
            }
        });
}

#[cfg(test)]
mod tests {
    use super::initial_files_from_args;

    fn v(args: &[&str]) -> Vec<String> {
        args.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn argv_ilk_eleman_atlanir() {
        assert_eq!(initial_files_from_args(&v(&["/usr/bin/pkgforge-desktop"])), Vec::<String>::new());
    }

    #[test]
    fn bayraklar_ve_olmayan_yollar_elenir() {
        let got = initial_files_from_args(&v(&["pkgforge-desktop", "--lang", "tr", "-f",
                                               "/nope/x.deb", "/etc/hostname"]));
        assert_eq!(got, vec!["/etc/hostname".to_string()]);
    }

    #[test]
    fn dizin_ve_cift_girdi_tekilleşir() {
        let tmp = std::env::temp_dir().join("pf_argtest_file.txt");
        std::fs::write(&tmp, b"x").unwrap();
        let s = tmp.to_string_lossy().into_owned();
        let dir = std::env::temp_dir().to_string_lossy().into_owned();
        let got = initial_files_from_args(&v(&["pf", &s, &s, &dir]));
        assert_eq!(got, vec![s]);
        std::fs::remove_file(&tmp).ok();
    }

    #[test]
    fn uc_dosya_sirasi_ve_tekilliği_korunur() {
        let dir = std::env::temp_dir();
        let names = ["pf_multi_a.deb", "pf_multi_b.deb", "pf_multi_c.deb"];
        let paths: Vec<String> = names
            .iter()
            .map(|n| {
                let p = dir.join(n);
                std::fs::write(&p, b"x").unwrap();
                p.to_string_lossy().into_owned()
            })
            .collect();
        let mut argv = vec!["pf-desktop".to_string()];
        // a, a, b, bir dizin, c -> sirali ve tekilleştirilmiş [a, b, c] beklenir.
        argv.extend_from_slice(&[paths[0].clone(), paths[0].clone(), paths[1].clone(),
                                 dir.to_string_lossy().into_owned(), paths[2].clone()]);
        let got = initial_files_from_args(&argv);
        assert_eq!(got, paths);
        for n in names {
            std::fs::remove_file(dir.join(n)).ok();
        }
    }

    #[test]
    fn goreceli_yol_mutlaga_donusur() {
        let got = initial_files_from_args(&v(&["pf", "/etc/../etc/hostname"]));
        assert_eq!(got, vec!["/etc/hostname".to_string()]);
    }
}
