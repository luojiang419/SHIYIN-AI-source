fn main() {
    tauri_build::try_build(tauri_build::Attributes::new().app_manifest(
        tauri_build::AppManifest::new().commands(&[
            "get_update_settings",
            "save_update_settings",
            "check_for_update",
            "download_update",
            "defer_downloaded_update",
            "apply_downloaded_update",
        ]),
    ))
    .expect("failed to generate desktop update command permissions");
}
