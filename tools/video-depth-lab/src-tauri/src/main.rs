#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    if shiyin_video_depth_lab::run_depth_batch_update_session_from_args() {
        return;
    }
    if shiyin_video_depth_lab::apply_depth_batch_update_from_args() {
        return;
    }
    shiyin_video_depth_lab::run();
}
