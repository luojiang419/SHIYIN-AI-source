use crate::{discover_portable_root, stop_backend, DesktopState};
use rfd::{MessageButtons, MessageDialog, MessageLevel};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    fs::{self, File, OpenOptions},
    io::{self, Read, Write},
    net::{SocketAddr, TcpStream},
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
const LEGACY_ZIP_PREFIX: &str = "SHIYIN-AI-v";
const LEGACY_ZIP_SUFFIX: &str = "-windows-x64.zip";
const AUTOMATIC: &str = "automatic";
const MANUAL: &str = "manual";
const DISABLED: &str = "disabled";
const AUTOMATIC_PROXY: &str = "automaticProxy";
const MANUAL_PROXY: &str = "manualProxy";
const DIRECT: &str = "direct";
const DOWNLOAD_ATTEMPTS: usize = 3;

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
    pub asset_kind: String,
    pub release_notes: String,
    pub message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct PendingUpdate {
    version: String,
    asset_name: String,
    #[serde(alias = "zip_path")]
    asset_path: String,
    sha256: String,
    size: u64,
    deferred: bool,
    #[serde(default)]
    asset_kind: Option<String>,
}

struct ResolvedRelease {
    version: String,
    asset: GitHubAsset,
    checksum: GitHubAsset,
    notes: String,
    agent: ureq::Agent,
    asset_kind: String,
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

fn legacy_zip_asset_name(version: &str) -> String {
    format!("{LEGACY_ZIP_PREFIX}{version}{LEGACY_ZIP_SUFFIX}")
}

fn asset_candidates(version: &str) -> [(String, &'static str); 2] {
    [
        (installer_asset_name(version), "installer"),
        (legacy_zip_asset_name(version), "legacyZip"),
    ]
}

fn asset_kind(pending: &PendingUpdate) -> &str {
    pending.asset_kind.as_deref().unwrap_or_else(|| {
        if pending.asset_name.to_ascii_lowercase().ends_with(".exe") {
            "installer"
        } else {
            "legacyZip"
        }
    })
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
        let mut selected = None;
        for (expected, kind) in asset_candidates(&version) {
            let mut assets = release
                .assets
                .iter()
                .filter(|asset| asset.name == expected)
                .cloned();
            let Some(asset) = assets.next() else {
                continue;
            };
            if assets.next().is_some() || asset.size == 0 || asset.browser_download_url.is_empty() {
                return Err(format!("Release 的更新资产无效或重复：{expected}"));
            }
            selected = Some((asset, expected, kind));
            break;
        }
        let (asset, expected, asset_kind) = selected.ok_or_else(|| {
            format!(
                "Release 缺少唯一的更新包：{} 或 {}",
                installer_asset_name(&version),
                legacy_zip_asset_name(&version)
            )
        })?;
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
            asset_kind: asset_kind.to_string(),
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
        && matches!(asset_kind(pending), "installer" | "legacyZip")
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
        asset_kind: release.asset_kind.clone(),
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
            asset_kind: Some(release.asset_kind.clone()),
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
    let (mode, package_arg) = if asset_kind(pending) == "installer" {
        (
            "--run-update-session",
            format!("--update-installer={}", pending.asset_path),
        )
    } else {
        ("--apply-update", format!("--zip={}", pending.asset_path))
    };
    let mut command = Command::new(&helper);
    command.args([
        mode,
        &format!("--session-id={session_id}"),
        &format!("--root={}", root.display()),
        &format!("--data={}", data.display()),
        &package_arg,
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

pub fn run_update_helper_from_args() -> bool {
    let arguments: Vec<String> = std::env::args().collect();
    if !arguments
        .iter()
        .any(|argument| argument == "--apply-update")
    {
        return false;
    }
    let data_for_log = value(&arguments, "--data=").map(PathBuf::from);
    let result = (|| {
        let root = PathBuf::from(
            value(&arguments, "--root=").ok_or_else(|| "缺少更新目标目录。".to_string())?,
        );
        let data = PathBuf::from(
            value(&arguments, "--data=").ok_or_else(|| "缺少数据目录。".to_string())?,
        );
        let zip =
            PathBuf::from(value(&arguments, "--zip=").ok_or_else(|| "缺少更新包。".to_string())?);
        let version =
            value(&arguments, "--version=").ok_or_else(|| "缺少更新版本。".to_string())?;
        let hash = value(&arguments, "--sha256=").ok_or_else(|| "缺少更新校验值。".to_string())?;
        let old_pid = value(&arguments, "--old-pid=")
            .and_then(|text| text.parse().ok())
            .ok_or_else(|| "缺少旧进程编号。".to_string())?;
        apply_session(&root, &data, &zip, &version, &hash, old_pid)
    })();
    if let Err(error) = result {
        if let Some(data) = data_for_log.as_deref() {
            log(data, &format!("更新失败：{error}"));
        }
        MessageDialog::new()
            .set_level(MessageLevel::Error)
            .set_title("SHIYIN AI 更新失败")
            .set_description(&error)
            .set_buttons(MessageButtons::Ok)
            .show();
    }
    true
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
        1,
        "关闭旧版本",
        "正在等待旧版本退出…",
        "主程序即将关闭，更新窗口会继续完成安装。",
        false,
        false,
    );
    wait_for_exit_with_timeout(session.old_pid, Duration::from_secs(120))?;

    emit_progress(
        app,
        2,
        "安装新版本",
        "正在启动静默安装程序…",
        "系统可能会请求管理员权限确认。",
        false,
        false,
    );
    let installer_log = update_dir(data)
        .join("sessions")
        .join(&session.session_id)
        .join("installer.log");
    if let Some(parent) = installer_log.parent() {
        fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    }
    let exit_code = Command::new("powershell.exe")
        .args([
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            "$installer = $env:SHIYIN_UPDATE_INSTALLER; $root = $env:SHIYIN_UPDATE_ROOT; $log = $env:SHIYIN_UPDATE_INSTALLER_LOG; $p = Start-Process -FilePath $installer -ArgumentList @('/SP-', '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/NOCANCEL', '/CLOSEAPPLICATIONS', '/FORCECLOSEAPPLICATIONS', ('/DIR=' + $root), ('/LOG=' + $log)) -Verb RunAs -Wait -PassThru; exit $p.ExitCode",
        ])
        .env("SHIYIN_UPDATE_INSTALLER", installer)
        .env("SHIYIN_UPDATE_ROOT", root)
        .env("SHIYIN_UPDATE_INSTALLER_LOG", &installer_log)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map_err(|error| format!("无法启动安装程序：{error}"))?
        .code()
        .unwrap_or(1);
    if exit_code != 0 {
        let message = format!("安装程序退出码：{exit_code}");
        log(data, &message);
        emit_progress(
            app,
            2,
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

fn wait_for_exit(pid: u32) -> Result<(), String> {
    wait_for_exit_with_timeout(pid, Duration::from_secs(45))
}

fn wait_for_exit_with_timeout(pid: u32, timeout: Duration) -> Result<(), String> {
    let deadline = Instant::now() + timeout;
    loop {
        let output = Command::new("tasklist")
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

fn archive_is_safe(zip: &Path, root_name: &str) -> Result<(), String> {
    let output = Command::new("tar")
        .args(["-tf", &zip.display().to_string()])
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .output()
        .map_err(|e| format!("无法检查更新包：{e}"))?;
    if !output.status.success() {
        return Err("更新包无法读取。".into());
    }
    let prefix = format!("{root_name}/");
    for entry in String::from_utf8_lossy(&output.stdout).lines() {
        let entry = entry.replace('\\', "/");
        if entry.is_empty()
            || entry.starts_with('/')
            || entry.split('/').any(|part| part == "..")
            || !entry.starts_with(&prefix)
        {
            return Err("更新包包含不安全或不符合契约的文件路径。".into());
        }
    }
    Ok(())
}

fn extract(zip: &Path, destination: &Path) -> Result<(), String> {
    let output = Command::new("powershell.exe")
        .args([
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            "$zipPath = $env:SHIYIN_UPDATE_ZIP; $destinationPath = $env:SHIYIN_UPDATE_DESTINATION; if ([string]::IsNullOrWhiteSpace($zipPath) -or [string]::IsNullOrWhiteSpace($destinationPath)) { exit 2 }; Expand-Archive -LiteralPath $zipPath -DestinationPath $destinationPath -Force",
        ])
        .env("SHIYIN_UPDATE_ZIP", zip)
        .env("SHIYIN_UPDATE_DESTINATION", destination)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .output()
        .map_err(|e| format!("无法启动系统解压工具：{e}"))?;
    if output.status.success() {
        return Ok(());
    }
    let detail = String::from_utf8_lossy(&output.stderr)
        .lines()
        .next()
        .unwrap_or_default()
        .trim()
        .to_string();
    if detail.is_empty() {
        Err("解压更新包失败。".into())
    } else {
        Err(format!("解压更新包失败：{detail}"))
    }
}

fn copy_directory(source: &Path, destination: &Path) -> Result<(), String> {
    fs::create_dir_all(destination).map_err(|e| e.to_string())?;
    for entry in fs::read_dir(source).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        let from = entry.path();
        let to = destination.join(entry.file_name());
        if entry.file_type().map_err(|e| e.to_string())?.is_dir() {
            copy_directory(&from, &to)?;
        } else {
            fs::copy(&from, &to).map_err(|e| format!("无法替换 {}：{e}", to.display()))?;
        }
    }
    Ok(())
}

fn replace_app_directory(staged: &Path, root: &Path) -> Result<(), String> {
    let source = staged.join("app");
    let target = root.join("app");
    if !source.is_dir() {
        return Err("更新包缺少 app 目录。".into());
    }
    let backup = root.join(format!(".app-backup-{}", Uuid::new_v4()));
    if target.exists() {
        fs::rename(&target, &backup).map_err(|e| format!("无法备份旧 app 目录：{e}"))?;
    }
    if let Err(error) = fs::rename(&source, &target) {
        if backup.exists() {
            let _ = fs::rename(&backup, &target);
        }
        return Err(format!("无法替换 app 目录：{error}"));
    }
    if backup.exists() {
        fs::remove_dir_all(backup).map_err(|e| format!("无法清理旧 app 目录：{e}"))?;
    }
    Ok(())
}

fn copy_release_root_files(staged: &Path, root: &Path) -> Result<(), String> {
    for entry in fs::read_dir(staged).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        if entry.file_name() == "app" {
            continue;
        }
        let from = entry.path();
        let to = root.join(entry.file_name());
        if entry.file_type().map_err(|e| e.to_string())?.is_dir() {
            copy_directory(&from, &to)?;
        } else {
            fs::copy(&from, &to).map_err(|e| format!("无法替换 {}：{e}", to.display()))?;
        }
    }
    Ok(())
}

fn apply_session(
    root: &Path,
    data: &Path,
    zip: &Path,
    version: &str,
    expected_sha: &str,
    old_pid: u32,
) -> Result<(), String> {
    log(data, &format!("准备安装 v{version}"));
    if !root.join("app").is_dir()
        || !zip.is_file()
        || !version_is_newer(version, env!("CARGO_PKG_VERSION"))
        || sha256(zip)? != expected_sha.to_ascii_lowercase()
    {
        return Err("更新会话校验失败，未修改当前软件。".into());
    }
    wait_for_exit(old_pid)?;
    let root_name = format!("SHIYIN-AI-v{version}-windows-x64");
    archive_is_safe(zip, &root_name)?;
    let extraction = update_dir(data).join(format!("extract-{}", Uuid::new_v4()));
    let _ = fs::remove_dir_all(&extraction);
    fs::create_dir_all(&extraction).map_err(|e| e.to_string())?;
    extract(zip, &extraction)?;
    let staged = extraction.join(&root_name);
    if !staged.join("app").is_dir() || !staged.join("SHIYIN AI.exe").is_file() {
        let _ = fs::remove_dir_all(&extraction);
        return Err("更新包缺少 SHIYIN AI 主程序或 app 目录。".into());
    }
    replace_app_directory(&staged, root)?;
    copy_release_root_files(&staged, root)?;
    clear_pending(data);
    let _ = fs::remove_dir_all(&extraction);
    log(data, &format!("v{version} 安装完成，正在重启"));
    Command::new(root.join("SHIYIN AI.exe"))
        .current_dir(root)
        .spawn()
        .map_err(|e| format!("更新完成但无法重启新版：{e}"))?;
    Ok(())
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
        assert_eq!(
            legacy_zip_asset_name("1.2.3"),
            "SHIYIN-AI-v1.2.3-windows-x64.zip"
        );
    }
    #[test]
    fn checksum_rejects_wrong_asset_name() {
        assert!(checksum_value(
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef  other.zip",
            "expected.zip"
        )
        .is_err());
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

    #[test]
    fn replacing_app_directory_removes_stale_runtime_files_and_keeps_data() {
        let install_root =
            std::env::temp_dir().join(format!("shiyin-updater-test-{}", Uuid::new_v4()));
        let staged = install_root.join("staged");
        fs::create_dir_all(install_root.join("app").join("backend")).unwrap();
        fs::create_dir_all(staged.join("app").join("backend")).unwrap();
        fs::create_dir_all(install_root.join("data")).unwrap();
        fs::write(
            install_root.join("app").join("backend").join("stale.pyd"),
            b"old",
        )
        .unwrap();
        fs::write(
            staged.join("app").join("backend").join("current.pyd"),
            b"new",
        )
        .unwrap();
        fs::write(install_root.join("data").join("keep.txt"), b"user data").unwrap();

        replace_app_directory(&staged, &install_root).unwrap();

        assert!(!install_root
            .join("app")
            .join("backend")
            .join("stale.pyd")
            .exists());
        assert_eq!(
            fs::read(install_root.join("app").join("backend").join("current.pyd")).unwrap(),
            b"new"
        );
        assert_eq!(
            fs::read(install_root.join("data").join("keep.txt")).unwrap(),
            b"user data"
        );
        fs::remove_dir_all(install_root).unwrap();
    }
}
