// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;

use tauri::Manager;

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

/// Holds the running `service/core_service.py` child process so it can be
/// killed when the UI window closes. The Python core is a completely
/// separate process from this UI on purpose — see docs/... status/control
/// separation plan.
struct CoreServiceProcess(Mutex<Option<Child>>);

/// Repo root, resolved at compile time relative to this crate
/// (ui-app/src-tauri) so it doesn't depend on the process's working
/// directory at launch.
fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..").join("..")
}

fn spawn_core_service() -> std::io::Result<Child> {
    // Run as `-m service.core_service` (not the bare script path) so Python
    // puts the repo root on sys.path[0] instead of service/, letting
    // `from core...` / `from mapping...` / `from config...` resolve.
    Command::new("python")
        .args(["-m", "service.core_service"])
        .current_dir(repo_root())
        .spawn()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(CoreServiceProcess(Mutex::new(None)))
        .setup(|app| {
            match spawn_core_service() {
                Ok(child) => {
                    println!("[core_service] spawned pid={}", child.id());
                    *app.state::<CoreServiceProcess>().0.lock().unwrap() = Some(child);
                }
                Err(err) => {
                    eprintln!("[core_service] failed to spawn service/core_service.py: {err}");
                }
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                let state = window.state::<CoreServiceProcess>();
                let mut guard = state.0.lock().unwrap();
                if let Some(mut child) = guard.take() {
                    let _ = child.kill();
                    let _ = child.wait();
                }
            }
        })
        .invoke_handler(tauri::generate_handler![greet])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
