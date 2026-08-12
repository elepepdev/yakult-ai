use serde::{Deserialize, Serialize};
use std::sync::Mutex;
use tauri::{
    AppHandle, Emitter, Manager, State, WindowEvent,
    menu::{Menu, MenuBuilder, MenuItemBuilder, SubmenuBuilder},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
};

// ── Shared state ──

struct AppState {
    hovered_components: Vec<String>,
    force_ignore_mouse: bool,
    config_files: Vec<ConfigFile>,
}

#[derive(Clone, Serialize, Deserialize)]
struct ConfigFile {
    filename: String,
    name: String,
}

#[derive(Serialize)]
struct DirectoryEntry {
    name: String,
    path: String,
    is_dir: bool,
}

#[derive(Serialize)]
struct DirectoryResult {
    success: bool,
    entries: Vec<DirectoryEntry>,
    error: Option<String>,
}

#[derive(Serialize)]
struct FileResult {
    success: bool,
    content: Option<String>,
    error: Option<String>,
}

// ── Commands ──

#[tauri::command]
fn set_ignore_mouse_events(app: AppHandle, ignore: bool) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.set_ignore_cursor_events(ignore);
    }
}

#[tauri::command]
fn toggle_force_ignore_mouse(app: AppHandle, state: State<Mutex<AppState>>) {
    let mut s = state.lock().unwrap();
    s.force_ignore_mouse = !s.force_ignore_mouse;

    if let Some(window) = app.get_webview_window("main") {
        let ignore = s.force_ignore_mouse || s.hovered_components.is_empty();
        let _ = window.set_ignore_cursor_events(ignore);
    }

    let _ = app.emit("force-ignore-mouse-changed", s.force_ignore_mouse);
}

#[tauri::command]
fn update_component_hover(
    app: AppHandle,
    state: State<Mutex<AppState>>,
    component_id: String,
    is_hovering: bool,
) {
    let mut s = state.lock().unwrap();
    if is_hovering {
        if !s.hovered_components.contains(&component_id) {
            s.hovered_components.push(component_id);
        }
    } else {
        s.hovered_components.retain(|c| c != &component_id);
    }

    if !s.force_ignore_mouse {
        if let Some(window) = app.get_webview_window("main") {
            let should_ignore = s.hovered_components.is_empty();
            let _ = window.set_ignore_cursor_events(should_ignore);
        }
    }
}

#[tauri::command]
fn show_context_menu(app: AppHandle, state: State<Mutex<AppState>>) {
    use tauri::menu::PredefinedMenuItem;

    let s = state.lock().unwrap();

    let toggle_mic = MenuItemBuilder::with_id("toggle_mic", "Toggle Microphone")
        .build(&app)
        .unwrap();
    let interrupt = MenuItemBuilder::with_id("interrupt", "Interrupt")
        .build(&app)
        .unwrap();
    let toggle_passthrough = MenuItemBuilder::with_id("toggle_passthrough", "Toggle Mouse Passthrough")
        .build(&app)
        .unwrap();
    let toggle_scroll = MenuItemBuilder::with_id("toggle_scroll", "Toggle Scrolling to Resize")
        .build(&app)
        .unwrap();
    let toggle_input = MenuItemBuilder::with_id("toggle_input", "Toggle InputBox and Subtitle")
        .build(&app)
        .unwrap();

    let mut switch_items = Vec::new();
    for cf in &s.config_files {
        if let Ok(item) = MenuItemBuilder::with_id(format!("switch_{}", cf.filename), &cf.name)
            .build(&app)
        {
            switch_items.push(item);
        }
    }

    let switch_submenu = if switch_items.is_empty() {
        None
    } else {
        SubmenuBuilder::new(&app, "Switch Character")
            .items(&switch_items)
            .build()
            .ok()
    };

    let hide = MenuItemBuilder::with_id("hide", "Hide").build(&app).unwrap();
    let exit = MenuItemBuilder::with_id("exit", "Exit").build(&app).unwrap();
    let separator = PredefinedMenuItem::separator(&app).unwrap();

    let mut items: Vec<&dyn tauri::menu::IsMenuItem<tauri::Wry>> = vec![
        &toggle_mic,
        &interrupt,
        &separator,
        &toggle_passthrough,
        &toggle_scroll,
        &toggle_input,
        &separator,
    ];

    if let Some(ref sub) = switch_submenu {
        items.push(sub);
        items.push(&separator);
    }

    items.push(&hide);
    items.push(&exit);

    if let Ok(menu) = MenuBuilder::new(&app).items(&items).build() {
        if let Some(window) = app.get_webview_window("main") {
            let _ = window.popup_menu(&menu);
        }
    }
}

#[tauri::command]
fn get_home_dir() -> String {
    dirs::home_dir()
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_default()
}

#[tauri::command]
async fn resolve_directory(dir_path: String) -> DirectoryResult {
    let homedir = dirs::home_dir().unwrap_or_default();
    let resolved = if dir_path.trim().is_empty() {
        homedir.clone()
    } else {
        let trimmed = dir_path.trim();
        if let Some(rest) = trimmed.strip_prefix('~') {
            let mut p = homedir;
            p.push(rest.trim_start_matches('/'));
            p
        } else {
            std::path::PathBuf::from(trimmed)
        }
    };

    let (search_dir, filter_prefix) = if resolved.is_dir() {
        (resolved.clone(), None)
    } else if let Some(parent) = resolved.parent() {
        let base = resolved.file_name().map(|n| n.to_string_lossy().to_string());
        (parent.to_path_buf(), base)
    } else {
        return DirectoryResult {
            success: false,
            entries: vec![],
            error: Some("Invalid path".into()),
        };
    };

    let mut entries = Vec::new();
    if let Ok(read_dir) = std::fs::read_dir(&search_dir) {
        for entry in read_dir.flatten() {
            let name = entry.file_name().to_string_lossy().to_string();
            if name.starts_with('.') {
                continue;
            }
            if let Some(ref prefix) = filter_prefix {
                if !name.to_lowercase().starts_with(&prefix.to_lowercase()) {
                    continue;
                }
            }
            entries.push(DirectoryEntry {
                name: name.clone(),
                path: entry.path().to_string_lossy().to_string(),
                is_dir: entry.file_type().map(|t| t.is_dir()).unwrap_or(false),
            });
        }
    }

    entries.sort_by(|a, b| {
        if a.is_dir && !b.is_dir {
            return std::cmp::Ordering::Less;
        }
        if !a.is_dir && b.is_dir {
            return std::cmp::Ordering::Greater;
        }
        a.name.cmp(&b.name)
    });

    DirectoryResult {
        success: true,
        entries,
        error: None,
    }
}

#[tauri::command]
async fn read_file(file_path: String) -> FileResult {
    match std::fs::read_to_string(&file_path) {
        Ok(content) => FileResult {
            success: true,
            content: Some(content),
            error: None,
        },
        Err(e) => FileResult {
            success: false,
            content: None,
            error: Some(e.to_string()),
        },
    }
}

#[tauri::command]
fn update_config_files(app: AppHandle, state: State<Mutex<AppState>>, files: Vec<ConfigFile>) {
    let mut s = state.lock().unwrap();
    s.config_files = files;
}

// ── App entry ──

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_shell::init())
        .manage(Mutex::new(AppState {
            hovered_components: Vec::new(),
            force_ignore_mouse: false,
            config_files: Vec::new(),
        }))
        .setup(|app| {
            // Build and register the system tray
            let toggle_mic = MenuItemBuilder::with_id("toggle_mic", "Toggle Microphone")
                .build(app)?;
            let interrupt = MenuItemBuilder::with_id("interrupt", "Interrupt").build(app)?;
            let toggle_passthrough = MenuItemBuilder::with_id("toggle_passthrough", "Toggle Mouse Passthrough")
                .build(app)?;
            let toggle_scroll = MenuItemBuilder::with_id("toggle_scroll", "Toggle Scrolling to Resize")
                .build(app)?;
            let toggle_input = MenuItemBuilder::with_id("toggle_input", "Toggle InputBox and Subtitle")
                .build(app)?;
            let show = MenuItemBuilder::with_id("show", "Show").build(app)?;
            let hide = MenuItemBuilder::with_id("hide", "Hide").build(app)?;
            let exit = MenuItemBuilder::with_id("exit", "Exit").build(app)?;

            let tray_menu = MenuBuilder::new(app)
                .items(&[
                    &toggle_mic,
                    &interrupt,
                    &tauri::menu::PredefinedMenuItem::separator(app)?,
                    &toggle_passthrough,
                    &toggle_scroll,
                    &toggle_input,
                    &tauri::menu::PredefinedMenuItem::separator(app)?,
                    &show,
                    &hide,
                    &tauri::menu::PredefinedMenuItem::separator(app)?,
                    &exit,
                ])
                .build()?;

            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&tray_menu)
                .on_menu_event(move |app, event| {
                    match event.id().0.as_str() {
                        "toggle_mic" => { let _ = app.emit("mic-toggle", ()); }
                        "interrupt" => { let _ = app.emit("interrupt", ()); }
                        "toggle_passthrough" => { let _ = app.emit("toggle-force-ignore-mouse", ()); }
                        "toggle_scroll" => { let _ = app.emit("toggle-scroll-to-resize", ()); }
                        "toggle_input" => { let _ = app.emit("toggle-input-subtitle", ()); }
                        "show" => {
                            if let Some(w) = app.get_webview_window("main") {
                                let _ = w.show();
                            }
                        }
                        "hide" => {
                            if let Some(w) = app.get_webview_window("main") {
                                let _ = w.hide();
                            }
                        }
                        "exit" => {
                            app.exit(0);
                        }
                        _ => {}
                    }
                })
                .build(app)?;

            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .invoke_handler(tauri::generate_handler![
            set_ignore_mouse_events,
            toggle_force_ignore_mouse,
            update_component_hover,
            show_context_menu,
            get_home_dir,
            resolve_directory,
            read_file,
            update_config_files,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
