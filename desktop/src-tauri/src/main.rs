// Prevents an extra console window on Windows in release builds.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    // webkit2gtk'nin DMABUF renderleyicisi bazı Wayland kurulumlarında ya boş
    // pencere ya da SIGABRT üretiyor. `pkgforge desktop` bunu launcher
    // ortamında ayarlıyor, ama kabuk DOĞRUDAN çalıştırıldığında (terminal,
    // paket dosya bağıntısı, test harness'ı) o ayar yok — ölçülen hata:
    //   Gdk-Message: Error 71 (Protocol error) dispatching to Wayland display
    // Bu ayar GTK/WebKit tarafından okunmadan önce, çağıranın verdiği değere
    // dokunmadan yerleştirilir.
    if std::env::var_os("WEBKIT_DISABLE_DMABUF_RENDERER").is_none() {
        std::env::set_var("WEBKIT_DISABLE_DMABUF_RENDERER", "1");
    }
    pkgforge_desktop_lib::run()
}
