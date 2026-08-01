use crate::{discover_portable_root, stop_backend, DesktopState};
use rfd::{MessageButtons, MessageDialog, MessageLevel};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    ffi::OsStr,
    fs::{self, File, OpenOptions},
    io::{self, Read, Write},
    net::{SocketAddr, TcpStream},
    os::windows::process::CommandExt,
    path::{Path, PathBuf},
    process::{Command, Stdio},
    sync::{Arc, Mutex, MutexGuard},
    thread,
    time::{Duration, Instant},
};
use tauri::{AppHandle, Emitter, Manager, State, WebviewUrl, WebviewWindowBuilder};
use uuid::Uuid;

const RELEASE_API_URL: &str = "https://api.github.com/repos/luojiang419/SHIYIN-AI/releases/latest";
const INSTALLER_PREFIX: &str = "SHIYIN-AI-Setup-";
const AUTOMATIC: &str = "automatic";
const MANUAL: &str = "manual";
const DISABLED: &str = "disabled";
const AUTOMATIC_PROXY: &str = "automaticProxy";
const MANUAL_PROXY: &str = "manualProxy";
const DIRECT: &str = "direct";
const DOWNLOAD_ATTEMPTS: usize = 3;
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

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
            update_policy: AUTOMATIC.into(),
            network_mode: AUTOMATIC_PROXY.into(),
            manual_proxy_url: "http://127.0.0.1:7890".into(),
        }
    }
}

#[derive(Debug, Deserialize)]
struct GitHubRelease {
    tag_name: String,
    #[serde(default)]
    draft: bool,
    #[serde(default)]
    prerelease: bool,
    #[serde(default)]
    body: String,
    #[serde(default)]
    assets: Vec<GitHubAsset>,
}

#[derive(Debug, Clone, Deserialize)]
struct GitHubAsset {
    name: String,
    browser_download_url: String,
    size: u64,
    #[serde(default)]
    digest: String,
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

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct PendingUpdate {
    version: String,
    asset_name: String,
    asset_path: String,
    sha256: String,
    size: u64,
    deferred: bool,
}

struct ResolvedRelease {
    version: String,
    asset: GitHubAsset,
    checksum: GitHubAsset,
    notes: String,
    agent: ureq::Agent,
}

fn update_dir(data: &Path) -> PathBuf {
    data.join("update")
}
fn settings_path(data: &Path) -> PathBuf {
    data.join("config").join("update.json")
}
fn pending_path(data: &Path) -> PathBuf {
    update_dir(data).join("pending.json")
}

fn normalize_proxy(value: &str) -> String {
    let input = value.trim();
    let normalized = if input.contains("://") {
        input.to_string()
    } else {
        format!("http://{input}")
    };
    ureq::Proxy::new(&normalized)
        .map(|_| normalized)
        .unwrap_or_default()
}

fn normalize_settings(mut settings: UpdateSettings) -> Result<UpdateSettings, String> {
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
    settings.manual_proxy_url = normalize_proxy(&settings.manual_proxy_url);
    if settings.network_mode == MANUAL_PROXY && settings.manual_proxy_url.is_empty() {
        return Err("手动代理地址必须是 http:// 或 https:// URL。".into());
    }
    Ok(settings)
}

fn load_settings(data: &Path) -> UpdateSettings {
    fs::read_to_string(settings_path(data))
        .ok()
        .and_then(|raw| serde_json::from_str(&raw).ok())
        .and_then(|settings| normalize_settings(settings).ok())
        .unwrap_or_default()
}

fn save_settings_file(data: &Path, settings: &UpdateSettings) -> Result<(), String> {
    let target = settings_path(data);
    fs::create_dir_all(
        target
            .parent()
            .ok_or_else(|| "无法定位更新设置目录。".to_string())?,
    )
    .map_err(|e| e.to_string())?;
    let part = target.with_extension("json.part");
    fs::write(
        &part,
        serde_json::to_string_pretty(settings).map_err(|e| e.to_string())? + "\n",
    )
    .map_err(|e| e.to_string())?;
    fs::rename(part, target).map_err(|e| e.to_string())
}

fn load_pending(data: &Path) -> Option<PendingUpdate> {
    fs::read_to_string(pending_path(data))
        .ok()
        .and_then(|raw| serde_json::from_str(&raw).ok())
}

fn save_pending(data: &Path, pending: &PendingUpdate) -> Result<(), String> {
    let target = pending_path(data);
    fs::create_dir_all(update_dir(data)).map_err(|e| e.to_string())?;
    let part = target.with_extension("json.part");
    fs::write(
        &part,
        serde_json::to_string_pretty(pending).map_err(|e| e.to_string())? + "\n",
    )
    .map_err(|e| e.to_string())?;
    fs::rename(part, target).map_err(|e| e.to_string())
}

fn clear_pending(data: &Path) {
    let _ = fs::remove_file(pending_path(data));
}

fn normalize_version(value: &str) -> Option<String> {
    let parts: Vec<&str> = value.trim().trim_start_matches('v').split('.').collect();
    (parts.len() == 3
        && parts
            .iter()
            .all(|part| !part.is_empty() && part.chars().all(|c| c.is_ascii_digit())))
    .then(|| parts.join("."))
}

fn version_is_newer(candidate: &str, current: &str) -> bool {
    let (Some(candidate), Some(current)) =
        (normalize_version(candidate), normalize_version(current))
    else {
        return false;
    };
    let parts = |value: &str| {
        value
            .split('.')
            .map(|part| part.parse::<u64>().unwrap_or(0))
            .collect::<Vec<_>>()
    };
    parts(&candidate) > parts(&current)
}

fn installer_asset_name(version: &str) -> String {
    format!("{INSTALLER_PREFIX}{version}.exe")
}

fn local_proxy() -> Option<String> {
    let address: SocketAddr = "127.0.0.1:7890".parse().ok()?;
    TcpStream::connect_timeout(&address, Duration::from_millis(180))
        .ok()
        .map(|_| "http://127.0.0.1:7890".to_string())
}

fn build_update_agent(proxy_url: Option<&str>) -> Result<ureq::Agent, String> {
    let proxy = proxy_url
        .map(|url| ureq::Proxy::new(url).map_err(|_| "更新代理地址无效。".to_string()))
        .transpose()?;
    Ok(ureq::Agent::new_with_config(
        ureq::Agent::config_builder()
            .https_only(true)
            .timeout_global(Some(Duration::from_secs(20)))
            .proxy(proxy)
            .build(),
    ))
}

fn update_agents(settings: &UpdateSettings) -> Result<Vec<ureq::Agent>, String> {
    match settings.network_mode.as_str() {
        DIRECT => Ok(vec![build_update_agent(None)?]),
        MANUAL_PROXY => Ok(vec![build_update_agent(Some(&settings.manual_proxy_url))?]),
        AUTOMATIC_PROXY => {
            let mut proxies = Vec::new();
            if let Some(proxy) = ["HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"]
                .iter()
                .find_map(|name| std::env::var(name).ok())
                .map(|value| normalize_proxy(&value))
                .filter(|value| !value.is_empty())
            {
                proxies.push(proxy);
            }
            if let Some(proxy) = local_proxy() {
                if !proxies
                    .iter()
                    .any(|value| value.eq_ignore_ascii_case(&proxy))
                {
                    proxies.push(proxy);
                }
            }
            let mut agents = proxies
                .iter()
                .map(|proxy| build_update_agent(Some(proxy)))
                .collect::<Result<Vec<_>, _>>()?;
            agents.push(build_update_agent(None)?);
            Ok(agents)
        }
        _ => Err("更新网络模式无效。".into()),
    }
}

fn fetch_text(agent: &ureq::Agent, url: &str) -> Result<String, String> {
    let response = agent
        .get(url)
        .header("Accept", "application/vnd.github+json")
        .header("User-Agent", "SHIYIN-AI-Updater")
        .call()
        .map_err(|e| format!("请求更新服务器失败：{e}"))?;
    let mut text = String::new();
    response
        .into_parts()
        .1
        .into_reader()
        .read_to_string(&mut text)
        .map_err(|e| format!("读取更新响应失败：{e}"))?;
    Ok(text)
}

fn resolve_release(data: &Path, settings: &UpdateSettings) -> Result<ResolvedRelease, String> {
    let mut last_error = None;
    for agent in update_agents(settings)? {
        let raw = match fetch_text(&agent, RELEASE_API_URL) {
            Ok(raw) => raw,
            Err(error) => {
                last_error = Some(error);
                continue;
            }
        };
        let release: GitHubRelease = serde_json::from_str(&raw)
            .map_err(|_| "更新服务器返回了无效的 Release 数据。".to_string())?;
        if release.draft || release.prerelease {
            return Err("最新 Release 不是正式版本。".into());
        }
        let version = normalize_version(&release.tag_name)
            .ok_or_else(|| "Release 标签必须为 vX.Y.Z。".to_string())?;
        let expected = installer_asset_name(&version);
        let mut assets = release
            .assets
            .iter()
            .filter(|asset| asset.name == expected)
            .cloned();
        let asset = assets
            .next()
            .ok_or_else(|| format!("Release 缺少唯一的 EXE 更新包：{expected}"))?;
        if assets.next().is_some() || asset.size == 0 || asset.browser_download_url.is_empty() {
            return Err(format!("Release 的 EXE 更新资产无效或重复：{expected}"));
        }
        let checksum_name = format!("{expected}.sha256");
        let mut checksums = release
            .assets
            .iter()
            .filter(|asset| asset.name == checksum_name)
            .cloned();
        let checksum = checksums
            .next()
            .filter(|asset| {
                checksums.next().is_none()
                    && asset.size > 0
                    && !asset.browser_download_url.is_empty()
            })
            .ok_or_else(|| format!("Release 缺少唯一的校验文件：{checksum_name}"))?;
        return Ok(ResolvedRelease {
            version,
            asset,
            checksum,
            notes: release.body,
            agent,
        });
    }
    if let Some(error) = last_error {
        log(data, &format!("更新服务器连接失败：{error}"));
    }
    Err("无法连接更新服务器。请检查网络或代理设置后重试。".into())
}

fn sha256(path: &Path) -> Result<String, String> {
    let mut file = File::open(path).map_err(|e| format!("无法读取更新文件：{e}"))?;
    let mut hash = Sha256::new();
    let mut buffer = [0u8; 131072];
    loop {
        let count = file.read(&mut buffer).map_err(|e| e.to_string())?;
        if count == 0 {
            break;
        }
        hash.update(&buffer[..count]);
    }
    Ok(format!("{:x}", hash.finalize()))
}

fn checksum_value(raw: &str, expected_name: &str) -> Result<String, String> {
    let fields: Vec<&str> = raw.split_whitespace().collect();
    if fields.len() != 2
        || fields[1] != expected_name
        || fields[0].len() != 64
        || !fields[0].chars().all(|c| c.is_ascii_hexdigit())
    {
        return Err("Release 校验文件格式或资产名不正确。".into());
    }
    Ok(fields[0].to_ascii_lowercase())
}

fn pending_valid(data: &Path, pending: &PendingUpdate) -> bool {
    let path = Path::new(&pending.asset_path);
    path.is_file()
        && path.file_name().and_then(|name| name.to_str()) == Some(pending.asset_name.as_str())
        && pending.asset_name == installer_asset_name(&pending.version)
        && pending.asset_name.to_ascii_lowercase().ends_with(".exe")
        && path
            .metadata()
            .map(|meta| meta.len() == pending.size)
            .unwrap_or(false)
        && sha256(path)
            .map(|value| value.eq_ignore_ascii_case(&pending.sha256))
            .unwrap_or(false)
        && version_is_newer(&pending.version, env!("CARGO_PKG_VERSION"))
        && pending_path(data).is_file()
}

fn info(release: &ResolvedRelease, downloaded: bool) -> UpdateInfo {
    UpdateInfo {
        current_version: env!("CARGO_PKG_VERSION").into(),
        latest_version: release.version.clone(),
        available: version_is_newer(&release.version, env!("CARGO_PKG_VERSION")),
        downloaded,
        asset_name: release.asset.name.clone(),
        asset_size: release.asset.size,
        release_notes: release.notes.clone(),
        message: String::new(),
    }
}

fn download_release(data: &Path, release: &ResolvedRelease) -> Result<(), String> {
    let expected_hash = checksum_value(
        &fetch_text(&release.agent, &release.checksum.browser_download_url)?,
        &release.asset.name,
    )?;
    if let Some(digest) = release.asset.digest.strip_prefix("sha256:") {
        if !digest.eq_ignore_ascii_case(&expected_hash) {
            return Err("GitHub 资产摘要与校验文件不一致。".into());
        }
    }
    let directory = update_dir(data).join("downloads");
    fs::create_dir_all(&directory).map_err(|e| e.to_string())?;
    let destination = directory.join(&release.asset.name);
    if !(destination.is_file()
        && destination
            .metadata()
            .map(|meta| meta.len() == release.asset.size)
            .unwrap_or(false)
        && sha256(&destination)? == expected_hash)
    {
        let part = destination.with_extension("part");
        let _ = fs::remove_file(&destination);
        let mut last_error = String::new();
        for attempt in 1..=DOWNLOAD_ATTEMPTS {
            let _ = fs::remove_file(&part);
            let result = (|| -> Result<(), String> {
                let mut response = release
                    .agent
                    .get(&release.asset.browser_download_url)
                    .header("Accept", "application/octet-stream")
                    .header("User-Agent", "SHIYIN-AI-Updater")
                    .call()
                    .map_err(|e| format!("下载更新包失败：{e}"))?;
                let mut file = File::create(&part).map_err(|e| e.to_string())?;
                let written = io::copy(&mut response.body_mut().as_reader(), &mut file)
                    .map_err(|e| format!("写入更新包失败：{e}"))?;
                file.flush().map_err(|e| e.to_string())?;
                file.sync_all().map_err(|e| e.to_string())?;
                if written != release.asset.size || sha256(&part)? != expected_hash {
                    return Err("更新包大小或 SHA-256 校验失败。".into());
                }
                Ok(())
            })();
            if result.is_ok() {
                fs::rename(&part, &destination).map_err(|e| e.to_string())?;
                break;
            }
            last_error = result.unwrap_err();
            let _ = fs::remove_file(&part);
            if attempt < DOWNLOAD_ATTEMPTS {
                thread::sleep(Duration::from_millis(300 * attempt as u64));
            }
        }
        if !destination.is_file() {
            return Err(format!(
                "下载更新包失败，已重试 {DOWNLOAD_ATTEMPTS} 次：{last_error}"
            ));
        }
    }
    save_pending(
        data,
        &PendingUpdate {
            version: release.version.clone(),
            asset_name: release.asset.name.clone(),
            asset_path: destination.display().to_string(),
            sha256: expected_hash,
            size: release.asset.size,
            deferred: false,
        },
    )
}

fn acquire_lock(update_busy: &Mutex<bool>) -> Result<MutexGuard<'_, bool>, String> {
    let mut lock = update_busy
        .lock()
        .map_err(|_| "更新任务状态异常。".to_string())?;
    if *lock {
        return Err("已有更新任务正在执行。".into());
    }
    *lock = true;
    Ok(lock)
}

fn release_lock(mut lock: MutexGuard<'_, bool>) {
    *lock = false;
}

#[tauri::command]
pub fn get_update_settings(state: State<'_, DesktopState>) -> UpdateSettings {
    load_settings(&state.data_root)
}

#[tauri::command]
pub fn save_update_settings(
    settings: UpdateSettings,
    state: State<'_, DesktopState>,
) -> Result<UpdateSettings, String> {
    let settings = normalize_settings(settings)?;
    save_settings_file(&state.data_root, &settings)?;
    Ok(settings)
}

#[tauri::command]
pub async fn check_for_update(state: State<'_, DesktopState>) -> Result<UpdateInfo, String> {
    let data_root = state.data_root.clone();
    let update_busy = Arc::clone(&state.update_busy);
    tauri::async_runtime::spawn_blocking(move || {
        let lock = acquire_lock(&update_busy)?;
        let result = (|| {
            let settings = load_settings(&data_root);
            if settings.update_policy == DISABLED {
                return Err("自动更新已在设置中关闭。".into());
            }
            let release = resolve_release(&data_root, &settings)?;
            let downloaded = load_pending(&data_root)
                .map(|pending| {
                    pending.version == release.version && pending_valid(&data_root, &pending)
                })
                .unwrap_or(false);
            Ok(info(&release, downloaded))
        })();
        release_lock(lock);
        if let Err(error) = &result {
            log(&data_root, &format!("检查更新失败：{error}"));
        }
        result
    })
    .await
    .map_err(|error| format!("更新后台任务异常：{error}"))?
}

#[tauri::command]
pub async fn download_update(state: State<'_, DesktopState>) -> Result<UpdateInfo, String> {
    let data_root = state.data_root.clone();
    let update_busy = Arc::clone(&state.update_busy);
    tauri::async_runtime::spawn_blocking(move || {
        let lock = acquire_lock(&update_busy)?;
        let result = (|| {
            let settings = load_settings(&data_root);
            if settings.update_policy == DISABLED {
                return Err("自动更新已在设置中关闭。".into());
            }
            let release = resolve_release(&data_root, &settings)?;
            let available = version_is_newer(&release.version, env!("CARGO_PKG_VERSION"));
            if available {
                download_release(&data_root, &release)?;
            }
            Ok(info(&release, available))
        })();
        release_lock(lock);
        if let Err(error) = &result {
            log(&data_root, &format!("下载更新失败：{error}"));
        }
        result
    })
    .await
    .map_err(|error| format!("更新后台任务异常：{error}"))?
}

#[tauri::command]
pub fn defer_downloaded_update(state: State<'_, DesktopState>) -> Result<(), String> {
    let mut pending =
        load_pending(&state.data_root).ok_or_else(|| "尚未下载可安装的更新。".to_string())?;
    if !pending_valid(&state.data_root, &pending) {
        clear_pending(&state.data_root);
        return Err("缓存的更新包无效，已清理。".into());
    }
    pending.deferred = true;
    save_pending(&state.data_root, &pending)
}

#[tauri::command]
pub fn apply_downloaded_update(
    app: AppHandle,
    state: State<'_, DesktopState>,
) -> Result<(), String> {
    let pending =
        load_pending(&state.data_root).ok_or_else(|| "尚未下载可安装的更新。".to_string())?;
    if !pending_valid(&state.data_root, &pending) {
        clear_pending(&state.data_root);
        return Err("缓存的更新包无效，已清理。".into());
    }
    launch_helper(
        &state.portable_root,
        &state.data_root,
        &pending,
        std::process::id(),
    )?;
    stop_backend(&app);
    app.exit(0);
    Ok(())
}

fn launch_helper(
    root: &Path,
    data: &Path,
    pending: &PendingUpdate,
    old_pid: u32,
) -> Result<(), String> {
    let current = std::env::current_exe().map_err(|e| format!("无法定位更新器：{e}"))?;
    let helper_dir = update_dir(data).join("helper");
    fs::create_dir_all(&helper_dir).map_err(|e| e.to_string())?;
    let helper = helper_dir.join(format!("SHIYIN-AI-updater-{}.exe", Uuid::new_v4()));
    fs::copy(current, &helper).map_err(|e| format!("无法准备独立更新器：{e}"))?;
    let session_id = format!("update_{}", Uuid::new_v4());
    let mut command = command_without_console(&helper);
    command.args([
        "--run-update-session",
        &format!("--session-id={session_id}"),
        &format!("--root={}", root.display()),
        &format!("--data={}", data.display()),
        &format!("--update-installer={}", pending.asset_path),
        &format!("--version={}", pending.version),
        &format!("--sha256={}", pending.sha256),
        &format!("--old-pid={old_pid}"),
    ]);
    command
        .current_dir(root)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|e| format!("无法启动独立更新器：{e}"))?;
    Ok(())
}

fn command_without_console(program: impl AsRef<OsStr>) -> Command {
    let mut command = Command::new(program);
    command.creation_flags(CREATE_NO_WINDOW);
    command
}

pub fn apply_pending_update_on_startup() -> bool {
    let Ok(root) = discover_portable_root() else {
        return false;
    };
    let data = root.join("data");
    let Some(pending) = load_pending(&data) else {
        return false;
    };
    if !pending.deferred {
        return false;
    }
    if !pending_valid(&data, &pending) {
        clear_pending(&data);
        return false;
    }
    launch_helper(&root, &data, &pending, std::process::id()).is_ok()
}

fn value(arguments: &[String], name: &str) -> Option<String> {
    arguments
        .iter()
        .find_map(|argument| argument.strip_prefix(name).map(str::to_string))
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UpdateInstallSession {
    pub session_id: String,
    pub version: String,
    pub installer_path: String,
    pub install_root: String,
    pub data_root: String,
    pub sha256: String,
    pub old_pid: u32,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct UpdateProgress {
    step_index: u8,
    progress_percent: u8,
    step_label: String,
    message: String,
    substep: String,
    is_error: bool,
    is_success: bool,
}

pub struct UpdateSessionState {
    session: Mutex<Option<UpdateInstallSession>>,
}

fn parse_update_session_args(arguments: &[String]) -> Option<UpdateInstallSession> {
    if !arguments
        .iter()
        .any(|argument| argument == "--run-update-session")
    {
        return None;
    }
    Some(UpdateInstallSession {
        session_id: value(arguments, "--session-id=")?,
        version: value(arguments, "--version=")?,
        installer_path: value(arguments, "--update-installer=")?,
        install_root: value(arguments, "--root=")?,
        data_root: value(arguments, "--data=")?,
        sha256: value(arguments, "--sha256=")?,
        old_pid: value(arguments, "--old-pid=")?.parse().ok()?,
    })
}

pub fn run_update_session_window_from_args() -> bool {
    let arguments: Vec<String> = std::env::args().collect();
    let Some(session) = parse_update_session_args(&arguments) else {
        return false;
    };
    let data_for_log = PathBuf::from(&session.data_root);
    let data_for_log_setup = data_for_log.clone();
    let result = tauri::Builder::default()
        .manage(UpdateSessionState {
            session: Mutex::new(Some(session)),
        })
        .setup(move |app| {
            WebviewWindowBuilder::new(app, "update", WebviewUrl::App("updater.html".into()))
                .title("SHIYIN AI 正在更新")
                .inner_size(760.0, 500.0)
                .min_inner_size(640.0, 460.0)
                .build()
                .map_err(|error| {
                    Box::new(std::io::Error::other(error.to_string())) as Box<dyn std::error::Error>
                })?;
            let session = app
                .state::<UpdateSessionState>()
                .session
                .lock()
                .map_err(|_| std::io::Error::other("更新会话状态异常。"))?
                .take()
                .ok_or_else(|| std::io::Error::other("更新会话已经启动。"))?;
            let handle = app.handle().clone();
            let log_data = data_for_log_setup.clone();
            tauri::async_runtime::spawn(async move {
                // 等待页面先注册 update-progress 监听器，避免首个状态被错过。
                let _ = tauri::async_runtime::spawn_blocking(|| {
                    thread::sleep(Duration::from_millis(350));
                })
                .await;
                let update_handle = handle.clone();
                let result = tauri::async_runtime::spawn_blocking(move || {
                    run_installer_session(&update_handle, &session)
                })
                .await;
                if let Ok(Err(error)) = result {
                    emit_progress(
                        &handle,
                        2,
                        0,
                        "更新失败",
                        &error,
                        "请重新打开软件后重试。",
                        true,
                        false,
                    );
                    log(&log_data, &format!("更新失败：{error}"));
                }
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![run_update_session])
        .run(tauri::generate_context!());
    if let Err(error) = result {
        log(&data_for_log, &format!("更新窗口启动失败：{error}"));
        MessageDialog::new()
            .set_level(MessageLevel::Error)
            .set_title("SHIYIN AI 更新失败")
            .set_description(&format!("无法打开独立更新器：{error}"))
            .set_buttons(MessageButtons::Ok)
            .show();
    }
    true
}

#[tauri::command]
pub async fn run_update_session(
    app: AppHandle,
    state: State<'_, UpdateSessionState>,
) -> Result<(), String> {
    let session = state
        .session
        .lock()
        .map_err(|_| "更新会话状态异常。".to_string())?
        .take()
        .ok_or_else(|| "更新会话已经启动。".to_string())?;
    tauri::async_runtime::spawn_blocking(move || run_installer_session(&app, &session))
        .await
        .map_err(|error| format!("更新后台任务异常：{error}"))?
}

fn emit_progress(
    app: &AppHandle,
    step_index: u8,
    progress_percent: u8,
    step_label: &str,
    message: &str,
    substep: &str,
    is_error: bool,
    is_success: bool,
) {
    let _ = app.emit(
        "update-progress",
        UpdateProgress {
            step_index,
            progress_percent,
            step_label: step_label.to_string(),
            message: message.to_string(),
            substep: substep.to_string(),
            is_error,
            is_success,
        },
    );
}

fn run_installer_session(app: &AppHandle, session: &UpdateInstallSession) -> Result<(), String> {
    let data = Path::new(&session.data_root);
    let installer = Path::new(&session.installer_path);
    let root = Path::new(&session.install_root);
    emit_progress(
        app,
        0,
        0,
        "准备安装",
        "正在准备独立更新器会话…",
        "",
        false,
        false,
    );
    log(
        data,
        &format!("准备安装 v{}，会话 {}", session.version, session.session_id),
    );
    if !installer.is_file()
        || !root.is_dir()
        || !version_is_newer(&session.version, env!("CARGO_PKG_VERSION"))
        || sha256(installer)? != session.sha256.to_ascii_lowercase()
        || installer.file_name().and_then(|name| name.to_str())
            != Some(installer_asset_name(&session.version).as_str())
    {
        return Err("更新会话校验失败，未修改当前软件。".into());
    }
    emit_progress(
        app,
        0,
        0,
        "准备安装",
        "安装包校验完成，正在准备更新环境…",
        "已确认版本、文件名和 SHA-256 校验值。",
        false,
        false,
    );

    emit_progress(
        app,
        1,
        0,
        "关闭旧版本",
        "正在等待旧版本退出…",
        "主程序即将关闭，更新窗口会继续完成安装。",
        false,
        false,
    );
    wait_for_exit_with_timeout(session.old_pid, Duration::from_secs(120))?;
    emit_progress(
        app,
        1,
        0,
        "关闭旧版本",
        "旧版本已退出，正在交接安装任务…",
        "更新窗口会保持打开，请不要手动关闭。",
        false,
        false,
    );

    let installer_log = update_dir(data)
        .join("sessions")
        .join(&session.session_id)
        .join("installer.log");
    let installer_progress = update_dir(data)
        .join("sessions")
        .join(&session.session_id)
        .join("installer-progress.txt");
    if let Some(parent) = installer_log.parent() {
        fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    }
    let _ = fs::remove_file(&installer_progress);
    emit_progress(
        app,
        2,
        0,
        "安装新版本",
        "正在启动安装程序…",
        "安装器启动后将显示实时处理进度。",
        false,
        false,
    );
    let installer_command = r#"$installer = $env:SHIYIN_UPDATE_INSTALLER; $root = $env:SHIYIN_UPDATE_ROOT; $log = $env:SHIYIN_UPDATE_INSTALLER_LOG; $progress = $env:SHIYIN_UPDATE_PROGRESS; $arguments = @('/SP-', '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/NOCANCEL', '/CLOSEAPPLICATIONS', '/FORCECLOSEAPPLICATIONS', ('/DIR="' + $root + '"'), ('/LOG="' + $log + '"'), ('/UPDATEPROGRESS="' + $progress + '"')); $p = Start-Process -FilePath $installer -ArgumentList $arguments -Verb RunAs -Wait -PassThru; exit $p.ExitCode"#;
    let mut installer_process = command_without_console("powershell.exe")
        .args([
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            installer_command,
        ])
        .env("SHIYIN_UPDATE_INSTALLER", installer)
        .env("SHIYIN_UPDATE_ROOT", root)
        .env("SHIYIN_UPDATE_INSTALLER_LOG", &installer_log)
        .env("SHIYIN_UPDATE_PROGRESS", &installer_progress)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|error| format!("无法启动安装程序：{error}"))?;
    let mut last_progress = None;
    let mut latest_percent = 0;
    let exit_code = loop {
        if let Some(percent) = emit_installer_progress(app, &installer_progress, &mut last_progress)
        {
            latest_percent = percent;
        }
        match installer_process
            .try_wait()
            .map_err(|error| format!("无法读取安装程序状态：{error}"))?
        {
            Some(status) => {
                if let Some(percent) =
                    emit_installer_progress(app, &installer_progress, &mut last_progress)
                {
                    latest_percent = percent;
                }
                break status.code().unwrap_or(1);
            }
            None => thread::sleep(Duration::from_millis(120)),
        }
    };
    if exit_code != 0 {
        let message = format!("安装程序退出码：{exit_code}");
        log(data, &message);
        emit_progress(
            app,
            2,
            latest_percent,
            "安装新版本",
            &message,
            "请重新打开软件后重试。",
            true,
            false,
        );
        return Err(message);
    }

    emit_progress(
        app,
        3,
        100,
        "启动新版本",
        "安装完成，正在启动新版本…",
        "正在等待新版主程序可用。",
        false,
        false,
    );
    let app_exe = root.join("SHIYIN AI.exe");
    let deadline = Instant::now() + Duration::from_secs(30);
    while !app_exe.is_file() && Instant::now() < deadline {
        thread::sleep(Duration::from_millis(300));
    }
    if !app_exe.is_file() {
        return Err("安装完成但未找到新版主程序。".into());
    }
    thread::sleep(Duration::from_millis(800));
    Command::new(&app_exe)
        .current_dir(root)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|error| format!("更新完成但无法重启新版：{error}"))?;
    let _ = fs::remove_file(pending_path(data));
    emit_progress(
        app,
        4,
        100,
        "完成",
        &format!("已启动 v{}", session.version),
        "更新完成。",
        false,
        true,
    );
    thread::sleep(Duration::from_millis(900));
    app.exit(0);
    Ok(())
}

fn read_installer_progress(path: &Path) -> Option<(u64, u64)> {
    let raw = fs::read_to_string(path).ok()?;
    let mut fields = raw.trim().split('|');
    let current = fields.next()?.parse::<u64>().ok()?;
    let total = fields.next()?.parse::<u64>().ok()?;
    (total > 0 && current <= total).then_some((current, total))
}

fn emit_installer_progress(
    app: &AppHandle,
    path: &Path,
    last_progress: &mut Option<(u64, u64)>,
) -> Option<u8> {
    let (current, total) = read_installer_progress(path)?;
    let percent = progress_percent(current, total);
    if *last_progress != Some((current, total)) {
        *last_progress = Some((current, total));
        emit_progress(
            app,
            2,
            percent,
            "安装新版本",
            &format!("正在安装新版本… {percent}%"),
            &format!("安装器实时处理进度：{current} / {total}"),
            false,
            false,
        );
    }
    Some(percent)
}

fn progress_percent(current: u64, total: u64) -> u8 {
    current
        .saturating_mul(100)
        .checked_div(total)
        .unwrap_or(0)
        .min(99) as u8
}

fn log(data: &Path, message: &str) {
    let _ = fs::create_dir_all(update_dir(data));
    if let Ok(mut file) = OpenOptions::new()
        .create(true)
        .append(true)
        .open(update_dir(data).join("updater.log"))
    {
        let _ = writeln!(file, "{message}");
    }
}

fn wait_for_exit_with_timeout(pid: u32, timeout: Duration) -> Result<(), String> {
    let deadline = Instant::now() + timeout;
    loop {
        let output = command_without_console("tasklist")
            .args(["/FI", &format!("PID eq {pid}"), "/FO", "CSV", "/NH"])
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .output()
            .map_err(|e| format!("无法等待旧进程退出：{e}"))?;
        if !String::from_utf8_lossy(&output.stdout).contains(&format!("\"{pid}\"")) {
            return Ok(());
        }
        if Instant::now() >= deadline {
            return Err(format!(
                "旧版本在 {} 秒内未退出，更新已取消。",
                timeout.as_secs()
            ));
        }
        thread::sleep(Duration::from_millis(250));
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn version_comparison_handles_release_boundaries() {
        assert!(version_is_newer("1.0.74", "1.0.73"));
        assert!(!version_is_newer("1.0.73", "1.0.73"));
        assert!(!version_is_newer("1.0.72", "1.0.73"));
        assert!(!version_is_newer("v1.0", "1.0.73"));
    }
    #[test]
    fn asset_name_is_exact_and_versioned() {
        assert_eq!(installer_asset_name("1.2.3"), "SHIYIN-AI-Setup-1.2.3.exe");
    }
    #[test]
    fn checksum_rejects_wrong_asset_name() {
        assert!(checksum_value(
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef  other.exe",
            "expected.exe"
        )
        .is_err());
    }
    #[test]
    fn installer_progress_percentage_is_real_and_bounded() {
        assert_eq!(progress_percent(0, 100), 0);
        assert_eq!(progress_percent(25, 100), 25);
        assert_eq!(progress_percent(999, 1000), 99);
        assert_eq!(progress_percent(1000, 1000), 99);
    }
    #[test]
    fn every_update_policy_and_network_mode_is_valid() {
        for policy in [AUTOMATIC, MANUAL, DISABLED] {
            for network in [AUTOMATIC_PROXY, MANUAL_PROXY, DIRECT] {
                assert!(normalize_settings(UpdateSettings {
                    update_policy: policy.into(),
                    network_mode: network.into(),
                    manual_proxy_url: "127.0.0.1:7890".into()
                })
                .is_ok());
            }
        }
    }
}
