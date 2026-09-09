use crate::DesktopState;
use serde::{Deserialize, Serialize};
use std::fs;
use tauri::{AppHandle, State};

const AUTOMATIC: &str = "automatic";
const MANUAL: &str = "manual";
const DISABLED: &str = "disabled";
const AUTOMATIC_PROXY: &str = "automaticProxy";
const MANUAL_PROXY: &str = "manualProxy";
const DIRECT: &str = "direct";

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UpdateSettings {
    pub update_policy: String,
    pub network_mode: String,
    pub manual_proxy_url: String,
}

impl Default for UpdateSettings {
    fn default() -> Self {
        Self {
            update_policy: MANUAL.into(),
            network_mode: AUTOMATIC_PROXY.into(),
            manual_proxy_url: "http://127.0.0.1:7890".into(),
        }
    }
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct UpdateInfo {
    pub current_version: String,
    pub latest_version: String,
    pub available: bool,
    pub downloaded: bool,
    pub asset_name: String,
    pub asset_size: u64,
    pub release_notes: String,
    pub message: String,
}

fn settings_path(state: &DesktopState) -> std::path::PathBuf {
    state.data_root.join("config").join("update.json")
}

fn load_settings(state: &DesktopState) -> UpdateSettings {
    fs::read_to_string(settings_path(state))
        .ok()
        .and_then(|raw| serde_json::from_str(&raw).ok())
        .unwrap_or_default()
}

fn normalize_settings(settings: UpdateSettings) -> Result<UpdateSettings, String> {
    if !matches!(
        settings.update_policy.as_str(),
        AUTOMATIC | MANUAL | DISABLED
    ) {
        return Err("更新策略无效。".into());
    }
    if !matches!(
        settings.network_mode.as_str(),
        AUTOMATIC_PROXY | MANUAL_PROXY | DIRECT
    ) {
        return Err("更新网络模式无效。".into());
    }
    Ok(settings)
}

#[tauri::command]
pub fn get_update_settings(state: State<'_, DesktopState>) -> UpdateSettings {
    load_settings(&state)
}

#[tauri::command]
pub fn save_update_settings(
    settings: UpdateSettings,
    state: State<'_, DesktopState>,
) -> Result<UpdateSettings, String> {
    let settings = normalize_settings(settings)?;
    let path = settings_path(&state);
    fs::create_dir_all(
        path.parent()
            .ok_or_else(|| "无法定位更新设置目录。".to_string())?,
    )
    .map_err(|error| error.to_string())?;
    fs::write(
        path,
        serde_json::to_string_pretty(&settings).map_err(|error| error.to_string())? + "\n",
    )
    .map_err(|error| error.to_string())?;
    Ok(settings)
}

fn unsupported_info() -> UpdateInfo {
    UpdateInfo {
        current_version: env!("CARGO_PKG_VERSION").into(),
        latest_version: env!("CARGO_PKG_VERSION").into(),
        available: false,
        downloaded: false,
        asset_name: String::new(),
        asset_size: 0,
        release_notes: String::new(),
        message: "macOS 版本请从 GitHub Actions 或 Release 下载对应架构安装包。".into(),
    }
}

#[tauri::command]
pub async fn check_for_update(_state: State<'_, DesktopState>) -> Result<UpdateInfo, String> {
    Ok(unsupported_info())
}

#[tauri::command]
pub async fn download_update(_state: State<'_, DesktopState>) -> Result<UpdateInfo, String> {
    Err("macOS 暂不支持应用内自动替换，请下载对应架构的新版本安装包。".into())
}

#[tauri::command]
pub fn defer_downloaded_update(_state: State<'_, DesktopState>) -> Result<(), String> {
    Err("macOS 当前没有待安装的应用内更新。".into())
}

#[tauri::command]
pub fn apply_downloaded_update(
    _app: AppHandle,
    _state: State<'_, DesktopState>,
) -> Result<(), String> {
    Err("macOS 暂不支持应用内自动替换，请下载对应架构的新版本安装包。".into())
}

pub fn apply_pending_update_on_startup() -> bool {
    false
}

pub fn run_update_session_window_from_args() -> bool {
    false
}
