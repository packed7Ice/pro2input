// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
use std::path::PathBuf;
use std::process::Child;
#[cfg(debug_assertions)]
use std::process::Command;
use std::sync::Mutex;

use tauri::menu::{Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Manager};

#[cfg(not(debug_assertions))]
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
#[cfg(not(debug_assertions))]
use tauri_plugin_shell::ShellExt;

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

/// Either the dev-mode `python -m service.core_service` child or (in release
/// builds) the bundled `core_service` sidecar binary. Holding both variants
/// behind one enum lets kill/restart logic stay agnostic of which mode is
/// active.
enum ManagedChild {
    #[cfg_attr(not(debug_assertions), allow(dead_code))]
    Dev(Child),
    #[cfg(not(debug_assertions))]
    Sidecar(CommandChild),
}

impl ManagedChild {
    fn kill(self) {
        match self {
            ManagedChild::Dev(mut child) => {
                let _ = child.kill();
                let _ = child.wait();
            }
            #[cfg(not(debug_assertions))]
            ManagedChild::Sidecar(child) => {
                let _ = child.kill();
            }
        }
    }
}

/// Holds the running core service child so it can be killed/restarted from
/// the tray menu or on real quit. The Python core is a completely separate
/// process from this UI on purpose — see the slice-1/2 plans for the
/// status/control separation design.
struct CoreServiceProcess(Mutex<Option<ManagedChild>>);

/// Set only by the tray "Quit" item. Closing the window via the titlebar X
/// just hides it (the core service keeps running in the background); only
/// this flag lets CloseRequested's handler fall through to a real exit.
struct QuitRequested(Mutex<bool>);

/// Repo root, resolved at compile time relative to this crate
/// (ui-app/src-tauri) so it doesn't depend on the process's working
/// directory at launch. Only used by the dev-mode spawn path.
#[cfg(debug_assertions)]
fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..").join("..")
}

/// Where config.json lives -- same directory core_service.py uses (repo
/// root in dev, next to the sidecar exe in release; see spawn_core_service).
fn config_json_path() -> PathBuf {
    #[cfg(debug_assertions)]
    {
        repo_root().join("config.json")
    }
    #[cfg(not(debug_assertions))]
    {
        std::env::current_exe()
            .ok()
            .and_then(|p| p.parent().map(|d| d.join("config.json")))
            .unwrap_or_else(|| PathBuf::from("config.json"))
    }
}

/// Reads config.json fresh (Python is the sole writer, via the Settings
/// tab's existing set_settings WebSocket flow) to check the user's close
/// button preference. Read-only from Rust's side, so no synchronization
/// with core_service.py's writes is needed.
fn close_action_is_quit() -> bool {
    let Ok(text) = std::fs::read_to_string(config_json_path()) else {
        return false;
    };
    let Ok(json) = serde_json::from_str::<serde_json::Value>(&text) else {
        return false;
    };
    json.get("app")
        .and_then(|a| a.get("close_action"))
        .and_then(|v| v.as_str())
        == Some("quit")
}

#[cfg(debug_assertions)]
fn spawn_core_service(_app: &AppHandle) -> Option<ManagedChild> {
    use std::io::{BufRead, BufReader};
    use std::os::windows::process::CommandExt;
    use std::process::Stdio;

    // Without this, spawning a console-subsystem child (python.exe) pops up
    // its own visible console window alongside the app.
    const CREATE_NO_WINDOW: u32 = 0x08000000;

    // Dev mode: run the interpreter directly against the repo's source, no
    // build step required. `-m service.core_service` (not the bare script
    // path) so Python puts the repo root on sys.path[0], letting
    // `from core...` / `from mapping...` / `from config...` resolve.
    let result = Command::new("python")
        .args(["-m", "service.core_service"])
        .current_dir(repo_root())
        .creation_flags(CREATE_NO_WINDOW)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn();
    match result {
        Ok(mut child) => {
            println!("[core_service] spawned (dev/python) pid={}", child.id());
            if let Some(stdout) = child.stdout.take() {
                std::thread::spawn(move || {
                    for line in BufReader::new(stdout).lines().map_while(Result::ok) {
                        println!("[core_service] {line}");
                    }
                });
            }
            if let Some(stderr) = child.stderr.take() {
                std::thread::spawn(move || {
                    for line in BufReader::new(stderr).lines().map_while(Result::ok) {
                        eprintln!("[core_service] {line}");
                    }
                });
            }
            Some(ManagedChild::Dev(child))
        }
        Err(err) => {
            eprintln!("[core_service] failed to spawn service/core_service.py: {err}");
            None
        }
    }
}

#[cfg(not(debug_assertions))]
fn spawn_core_service(app: &AppHandle) -> Option<ManagedChild> {
    // Release mode: run the PyInstaller-frozen sidecar bundled via
    // `bundle.externalBin` (see tauri.conf.json). Its stdout/stderr must be
    // drained continuously — an unread CommandEvent channel can eventually
    // block the child if its OS pipe buffer fills up.
    let mut sidecar = match app.shell().sidecar("core_service") {
        Ok(cmd) => cmd,
        Err(err) => {
            eprintln!("[core_service] failed to resolve sidecar: {err}");
            return None;
        }
    };
    // Pin the working directory to the installed app's own folder (where
    // config.json lives, next to the sidecar exe) rather than whatever CWD
    // happened to launch ui-app.exe -- without this, config.json's
    // relative path (config/settings.py) would resolve unpredictably.
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            sidecar = sidecar.current_dir(dir);
        }
    }
    match sidecar.spawn() {
        Ok((mut rx, child)) => {
            println!("[core_service] spawned (release/sidecar) pid={}", child.pid());
            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    if let CommandEvent::Stdout(line) | CommandEvent::Stderr(line) = event {
                        print!("[core_service] {}", String::from_utf8_lossy(&line));
                    }
                }
            });
            Some(ManagedChild::Sidecar(child))
        }
        Err(err) => {
            eprintln!("[core_service] failed to spawn sidecar: {err}");
            None
        }
    }
}

fn kill_core_service(app: &AppHandle) {
    let state = app.state::<CoreServiceProcess>();
    let mut guard = state.0.lock().unwrap();
    if let Some(child) = guard.take() {
        child.kill();
    }
}

fn restart_core_service(app: &AppHandle) {
    kill_core_service(app);
    let child = spawn_core_service(app);
    *app.state::<CoreServiceProcess>().0.lock().unwrap() = child;
}

fn toggle_main_window(app: &AppHandle) {
    let Some(window) = app.get_webview_window("main") else {
        return;
    };
    if window.is_visible().unwrap_or(false) {
        let _ = window.hide();
    } else {
        let _ = window.show();
        let _ = window.set_focus();
    }
}

fn show_main_window(app: &AppHandle) {
    let Some(window) = app.get_webview_window("main") else {
        return;
    };
    let _ = window.show();
    let _ = window.set_focus();
}

/// Full teardown: used by the tray "Quit" item and by CloseRequested when
/// the user's close_action setting is "quit".
fn perform_quit(app: &AppHandle) {
    *app.state::<QuitRequested>().0.lock().unwrap() = true;
    kill_core_service(app);
    app.exit(0);
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    #[allow(unused_mut)]
    let mut builder = tauri::Builder::default()
        // Must be registered first: if another instance is already running,
        // this exits the new process immediately (before .setup() runs, so
        // spawn_core_service() never fires a second time and can't collide
        // on the status server's port) and instead runs this callback in
        // the *original* instance to bring its window forward.
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            show_main_window(app);
        }))
        .plugin(tauri_plugin_opener::init());

    #[cfg(not(debug_assertions))]
    {
        builder = builder.plugin(tauri_plugin_shell::init());
    }

    builder
        .manage(CoreServiceProcess(Mutex::new(None)))
        .manage(QuitRequested(Mutex::new(false)))
        .setup(|app| {
            let handle = app.handle().clone();
            let child = spawn_core_service(&handle);
            *app.state::<CoreServiceProcess>().0.lock().unwrap() = child;

            let show_hide = MenuItem::with_id(app, "toggle_window", "Show/Hide", true, None::<&str>)?;
            let restart = MenuItem::with_id(app, "restart_core", "Restart Core Service", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(
                app,
                &[
                    &show_hide,
                    &PredefinedMenuItem::separator(app)?,
                    &restart,
                    &PredefinedMenuItem::separator(app)?,
                    &quit,
                ],
            )?;

            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .show_menu_on_left_click(false)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "toggle_window" => toggle_main_window(app),
                    "restart_core" => restart_core_service(app),
                    "quit" => perform_quit(app),
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        toggle_main_window(tray.app_handle());
                    }
                })
                .build(app)?;

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                let app = window.app_handle();
                let quit_requested = *app.state::<QuitRequested>().0.lock().unwrap();
                if quit_requested {
                    // Already being torn down via the tray "Quit" path;
                    // allow the default close to proceed.
                } else if close_action_is_quit() {
                    // User's close_action setting (Settings tab) is "quit".
                    perform_quit(app);
                } else {
                    // Default: minimize to tray, keep the core service running.
                    api.prevent_close();
                    let _ = window.hide();
                }
            }
        })
        .invoke_handler(tauri::generate_handler![greet])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
