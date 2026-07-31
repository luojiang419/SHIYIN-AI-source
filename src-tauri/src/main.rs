#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    if canvas_desktop_lib::run_update_session_window_from_args() {
        return;
    }
    canvas_desktop_lib::run();
}
