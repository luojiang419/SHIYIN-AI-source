use ed25519_dalek::{Signature, Verifier, VerifyingKey};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::HashSet,
    fs,
    io::Read,
    path::{Path, PathBuf},
    process::Command,
    sync::Mutex,
    thread,
    time::Duration,
};
use tauri::{AppHandle, Emitter, Manager, State, WebviewUrl, WebviewWindowBuilder};

const PUBLIC_KEY: &str = include_str!("../distribution-public-key.hex");
const BASELINE_RELEASE: &str = include_str!("../distribution-baseline.txt");
const PRODUCT: &str = "depth-batch";
const DEFAULT_LAN: &str = "http://192.168.0.24:3011";
const MODELSCOPE_REPOSITORY: &str = "jiangjiang419/SHIYIN-Depth-Batch";

#[derive(Default)]
pub struct UpdateState {
    pub root: PathBuf,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
#[serde(default)]
pub struct UpdateSettings {
    pub enabled: bool,
    pub lan_update_url: String,
}
impl Default for UpdateSettings {
    fn default() -> Self {
        Self {
            enabled: true,
            lan_update_url: DEFAULT_LAN.into(),
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
    pub asset_size: u64,
    pub release_notes: String,
}
#[derive(Deserialize)]
struct Envelope {
    payload: String,
    signature: String,
    public_key: String,
}
#[derive(Clone, Deserialize)]
struct Package {
    name: String,
    size: u64,
    sha256: String,
}
#[derive(Clone, Deserialize)]
struct FileEntry {
    path: String,
    size: u64,
    sha256: String,
}
#[derive(Clone, Deserialize)]
struct Manifest {
    product: String,
    version: String,
    #[serde(default)]
    notes: String,
    package: Package,
    files: Vec<FileEntry>,
}
struct UpdateSource {
    manifest: Manifest,
    package_url: String,
}

#[derive(Clone)]
struct UpdateInstallSession {
    parent_pid: u32,
    stage: PathBuf,
    root: PathBuf,
    data_root: PathBuf,
    version: String,
}

struct UpdateSessionState {
    session: Mutex<Option<UpdateInstallSession>>,
}

#[derive(Clone, Serialize)]
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

fn data(root: &Path) -> PathBuf {
    #[cfg(test)]
    return root.join("data");

    #[cfg(not(test))]
    std::env::var_os("LOCALAPPDATA")
        .filter(|value| !value.is_empty())
        .map(PathBuf::from)
        .map(|path| path.join("SHIYIN-Depth-Batch"))
        .unwrap_or_else(|| root.join("data"))
}
fn settings_file(root: &Path) -> PathBuf {
    data(root).join("config").join("update.json")
}
fn pending_file(root: &Path) -> PathBuf {
    data(root).join("update").join("pending.json")
}
fn installed_file(root: &Path) -> PathBuf {
    data(root).join("update").join("installed.json")
}
fn hex<const N: usize>(value: &str) -> Result<[u8; N], String> {
    if value.len() != N * 2 || !value.is_ascii() {
        return Err("更新签名编码无效".into());
    };
    let mut output = [0; N];
    for (i, byte) in output.iter_mut().enumerate() {
        *byte = u8::from_str_radix(&value[i * 2..i * 2 + 2], 16).map_err(|_| "更新签名编码无效")?;
    }
    Ok(output)
}
fn hash(path: &Path) -> Result<String, String> {
    let mut file = fs::File::open(path).map_err(|e| e.to_string())?;
    let mut h = Sha256::new();
    let mut b = [0; 65536];
    loop {
        let n = file.read(&mut b).map_err(|e| e.to_string())?;
        if n == 0 {
            break;
        }
        h.update(&b[..n]);
    }
    Ok(format!("{:x}", h.finalize()))
}
fn release_id(value: &str) -> bool {
    value.len() == 14 && value.bytes().all(|b| b.is_ascii_digit())
}
fn relative(value: &str) -> Result<PathBuf, String> {
    if value.is_empty()
        || value.contains(['\\', ':'])
        || value
            .split('/')
            .any(|p| p.is_empty() || p == "." || p == "..")
    {
        return Err("更新文件路径无效".into());
    }
    Ok(value.split('/').collect())
}
fn verify(raw: &str) -> Result<Manifest, String> {
    let normalized = raw.trim_start_matches('\u{feff}').trim();
    let e: Envelope =
        serde_json::from_str(normalized).map_err(|error| format!("更新清单无效：{error}"))?;
    if e.public_key != PUBLIC_KEY.trim() {
        return Err("更新源公钥不受信任".into());
    };
    let key = VerifyingKey::from_bytes(&hex::<32>(&e.public_key)?).map_err(|_| "更新公钥无效")?;
    key.verify(
        e.payload.as_bytes(),
        &Signature::from_bytes(&hex::<64>(&e.signature)?),
    )
    .map_err(|_| "更新清单签名校验失败")?;
    let m: Manifest =
        serde_json::from_str(&e.payload).map_err(|error| format!("更新清单内容无效：{error}"))?;
    if m.product != PRODUCT
        || !release_id(&m.version)
        || m.files.is_empty()
        || m.files.len() > 10000
        || m.package.name != format!("SHIYIN-Depth-Batch-Update-{}.shiyin-update", m.version)
        || m.package.size == 0
        || hex::<32>(&m.package.sha256).is_err()
    {
        return Err("更新包不属于 SHIYIN-Depth-Batch 或格式无效".into());
    };
    let mut seen = HashSet::new();
    for f in &m.files {
        relative(&f.path)?;
        if f.size == 0 || hex::<32>(&f.sha256).is_err() || !seen.insert(f.path.to_ascii_lowercase())
        {
            return Err("更新文件清单无效".into());
        }
    }
    Ok(m)
}
fn settings(root: &Path) -> UpdateSettings {
    let current = settings_file(root);
    let legacy = root.join("data").join("config").join("update.json");
    [current, legacy]
        .into_iter()
        .find_map(|path| {
            fs::read_to_string(path)
                .ok()
                .and_then(|raw| serde_json::from_str(&raw).ok())
        })
        .unwrap_or_default()
}
fn save(root: &Path, s: &UpdateSettings) -> Result<(), String> {
    let target = settings_file(root);
    fs::create_dir_all(target.parent().unwrap()).map_err(|e| e.to_string())?;
    fs::write(
        target,
        serde_json::to_vec_pretty(s).map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())
}
fn base(s: &UpdateSettings) -> Result<String, String> {
    let value = s.lan_update_url.trim().trim_end_matches('/');
    if !value.starts_with("http://") || value.contains(['?', '#']) {
        return Err("局域网更新地址无效".into());
    }
    Ok(value.into())
}
fn modelscope_file(path: &str) -> String {
    format!("https://modelscope.cn/models/{MODELSCOPE_REPOSITORY}/resolve/master/{path}")
}
fn fetch_catalog(url: &str) -> Result<Manifest, String> {
    let response = ureq::get(url)
        .header("Accept", "application/json")
        .header("User-Agent", "SHIYIN-Depth-Batch-Updater/1")
        .call()
        .map_err(|e| format!("请求失败：{e}"))?;
    let raw = response
        .into_body()
        .read_to_string()
        .map_err(|e| format!("读取响应失败：{e}"))?;
    verify(&raw).map_err(|e| format!("{url}：{e}"))
}
fn installed(root: &Path) -> String {
    let applied = fs::read_to_string(installed_file(root))
        .ok()
        .and_then(|raw| serde_json::from_str::<serde_json::Value>(&raw).ok())
        .and_then(|v| v["version"].as_str().map(str::to_string))
        .filter(|v| release_id(v))
        .unwrap_or_default();
    [applied.as_str(), BASELINE_RELEASE.trim()]
        .into_iter()
        .filter(|v| release_id(v))
        .max()
        .unwrap_or("")
        .to_string()
}
fn catalog(root: &Path) -> Result<UpdateSource, String> {
    let s = settings(root);
    if !s.enabled {
        return Err("已关闭自动更新".into());
    };
    let lan_result = base(&s).and_then(|base| {
        fetch_catalog(&format!("{base}/v1/catalog?product={PRODUCT}"))
            .map(|manifest| (base, manifest))
    });
    if let Ok((base, manifest)) = lan_result.as_ref() {
        let package_url = format!("{base}/hot-depth-batch/packages/{}", manifest.package.name);
        return Ok(UpdateSource {
            manifest: manifest.clone(),
            package_url,
        });
    }
    let lan_error = lan_result
        .err()
        .unwrap_or_else(|| "局域网更新源未知错误".into());
    let manifest =
        fetch_catalog(&modelscope_file("public/catalog.json")).map_err(|modelscope_error| {
            format!("局域网更新源不可用：{lan_error}\n魔塔更新源不可用：{modelscope_error}")
        })?;
    let package_url = modelscope_file(&format!(
        "updates/{}/{}",
        manifest.version, manifest.package.name
    ));
    Ok(UpdateSource {
        manifest,
        package_url,
    })
}
fn downloaded(root: &Path, version: &str) -> bool {
    fs::read_to_string(pending_file(root))
        .ok()
        .and_then(|raw| serde_json::from_str::<serde_json::Value>(&raw).ok())
        .and_then(|v| v["version"].as_str().map(str::to_string))
        .as_deref()
        == Some(version)
}
fn info(m: &Manifest, root: &Path) -> UpdateInfo {
    let available = m.version > installed(root);
    UpdateInfo {
        current_version: env!("CARGO_PKG_VERSION").into(),
        latest_version: m.version.clone(),
        available,
        downloaded: available && downloaded(root, &m.version),
        asset_size: m.package.size,
        release_notes: m.notes.clone(),
    }
}

#[tauri::command]
pub fn get_update_settings(state: State<'_, UpdateState>) -> UpdateSettings {
    settings(&state.root)
}
#[tauri::command]
pub fn save_update_settings(
    state: State<'_, UpdateState>,
    mut s: UpdateSettings,
) -> Result<UpdateSettings, String> {
    s.lan_update_url = s.lan_update_url.trim().trim_end_matches('/').into();
    let _ = base(&s)?;
    save(&state.root, &s)?;
    Ok(s)
}
#[tauri::command]
pub async fn check_for_update(state: State<'_, UpdateState>) -> Result<UpdateInfo, String> {
    let root = state.root.clone();
    tauri::async_runtime::spawn_blocking(move || {
        let source = catalog(&root)?;
        Ok(info(&source.manifest, &root))
    })
    .await
    .map_err(|e| e.to_string())?
}
#[tauri::command]
pub async fn download_update(state: State<'_, UpdateState>) -> Result<UpdateInfo, String> {
    let root = state.root.clone();
    tauri::async_runtime::spawn_blocking(move || {
        let source = catalog(&root)?;
        let m = source.manifest;
        if m.version <= installed(&root) {
            return Err("当前已是最新版本".into());
        }
        let update = data(&root).join("update");
        fs::create_dir_all(&update).map_err(|e| e.to_string())?;
        let package_path = update.join(&m.package.name);
        let mut response = ureq::get(&source.package_url)
            .call()
            .map_err(|e| format!("下载更新失败：{e}"))?;
        let mut file = fs::File::create(&package_path).map_err(|e| e.to_string())?;
        std::io::copy(&mut response.body_mut().as_reader(), &mut file)
            .map_err(|e| e.to_string())?;
        if hash(&package_path)? != m.package.sha256 {
            return Err("更新包校验失败".into());
        };
        let stage = update.join("staged").join(&m.version);
        if stage.exists() {
            fs::remove_dir_all(&stage).map_err(|e| e.to_string())?
        }
        fs::create_dir_all(&stage).map_err(|e| e.to_string())?;
        let archive = fs::File::open(&package_path).map_err(|e| e.to_string())?;
        let mut zip = zip::ZipArchive::new(archive).map_err(|_| "更新包无法解压")?;
        for entry in &m.files {
            let target = stage.join(relative(&entry.path)?);
            if let Some(parent) = target.parent() {
                fs::create_dir_all(parent).map_err(|e| e.to_string())?
            };
            let mut source = zip.by_name(&entry.path).map_err(|_| "更新包缺少文件")?;
            let mut output = fs::File::create(&target).map_err(|e| e.to_string())?;
            std::io::copy(&mut source, &mut output).map_err(|e| e.to_string())?;
            if target.metadata().map_err(|e| e.to_string())?.len() != entry.size
                || hash(&target)? != entry.sha256
            {
                return Err("更新文件校验失败".into());
            }
        }
        fs::write(
            pending_file(&root),
            serde_json::json!({"version":m.version,"stage":stage}).to_string(),
        )
        .map_err(|e| e.to_string())?;
        let mut result = info(&m, &root);
        result.downloaded = true;
        Ok(result)
    })
    .await
    .map_err(|e| e.to_string())?
}
#[tauri::command]
pub fn apply_downloaded_update(
    app: AppHandle,
    state: State<'_, UpdateState>,
) -> Result<(), String> {
    let raw = fs::read_to_string(pending_file(&state.root))
        .map_err(|_| "没有已下载的更新".to_string())?;
    let pending: serde_json::Value = serde_json::from_str(&raw).map_err(|_| "更新记录无效")?;
    let stage = pending["stage"].as_str().ok_or("更新记录无效")?;
    let version = pending["version"]
        .as_str()
        .filter(|value| release_id(value))
        .ok_or("更新记录无效")?;
    let exe = std::env::current_exe().map_err(|e| e.to_string())?;
    let updater_exe = data(&state.root)
        .join("update")
        .join("SHIYIN-Depth-Batch-Updater.exe");
    fs::copy(&exe, &updater_exe).map_err(|e| format!("准备独立更新器失败：{e}"))?;
    Command::new(updater_exe)
        .args([
            "--run-depth-batch-update",
            &format!("--parent-pid={}", std::process::id()),
            &format!("--stage={stage}"),
            &format!("--root={}", state.root.display()),
            &format!("--data={}", data(&state.root).display()),
            &format!("--version={version}"),
        ])
        .spawn()
        .map_err(|e| format!("启动独立更新器失败：{e}"))?;
    app.exit(0);
    Ok(())
}

fn session_arg(arguments: &[String], name: &str) -> Option<String> {
    arguments
        .iter()
        .find_map(|argument| argument.strip_prefix(name).map(str::to_string))
}

fn parse_update_session(arguments: &[String]) -> Option<UpdateInstallSession> {
    if !arguments
        .iter()
        .any(|argument| argument == "--run-depth-batch-update")
    {
        return None;
    }
    let version = session_arg(arguments, "--version=")?;
    if !release_id(&version) {
        return None;
    }
    Some(UpdateInstallSession {
        parent_pid: session_arg(arguments, "--parent-pid=")?.parse().ok()?,
        stage: PathBuf::from(session_arg(arguments, "--stage=")?),
        root: PathBuf::from(session_arg(arguments, "--root=")?),
        data_root: PathBuf::from(session_arg(arguments, "--data=")?),
        version,
    })
}

pub fn run_update_session_window_from_args() -> bool {
    let arguments: Vec<String> = std::env::args().collect();
    let Some(session) = parse_update_session(&arguments) else {
        return false;
    };
    let result = tauri::Builder::default()
        .manage(UpdateSessionState {
            session: Mutex::new(Some(session)),
        })
        .setup(|app| {
            if let Some(main) = app.get_webview_window("main") {
                let _ = main.close();
            }
            WebviewWindowBuilder::new(app, "update", WebviewUrl::App("updater.html".into()))
                .title("SHIYIN Depth Batch 正在更新")
                .inner_size(720.0, 510.0)
                .min_inner_size(720.0, 510.0)
                .resizable(false)
                .closable(false)
                .center()
                .build()
                .map_err(|error| {
                    Box::new(std::io::Error::other(error.to_string())) as Box<dyn std::error::Error>
                })?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![run_depth_batch_update_session])
        .run(tauri::generate_context!());
    if let Err(error) = result {
        eprintln!("独立更新器启动失败：{error}");
    }
    true
}

fn emit_update_progress(
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
        "depth-batch-update-progress",
        UpdateProgress {
            step_index,
            progress_percent,
            step_label: step_label.into(),
            message: message.into(),
            substep: substep.into(),
            is_error,
            is_success,
        },
    );
}

#[cfg(target_os = "windows")]
fn run_elevated_script(script: &Path) -> Result<(), String> {
    use std::{
        mem::size_of,
        os::windows::ffi::OsStrExt,
        ptr::{null, null_mut},
    };
    use windows_sys::Win32::{
        Foundation::{CloseHandle, GetLastError},
        System::Threading::{GetExitCodeProcess, WaitForSingleObject, INFINITE},
        UI::Shell::{ShellExecuteExW, SEE_MASK_NOCLOSEPROCESS, SHELLEXECUTEINFOW},
    };

    let wide = |value: &std::ffi::OsStr| value.encode_wide().chain(Some(0)).collect::<Vec<u16>>();
    let verb = wide(std::ffi::OsStr::new("runas"));
    let file = wide(std::ffi::OsStr::new("powershell.exe"));
    let parameters = wide(std::ffi::OsStr::new(&format!(
        "-NoProfile -ExecutionPolicy Bypass -File \"{}\"",
        script.display()
    )));
    let mut execution: SHELLEXECUTEINFOW = unsafe { std::mem::zeroed() };
    execution.cbSize = size_of::<SHELLEXECUTEINFOW>() as u32;
    execution.fMask = SEE_MASK_NOCLOSEPROCESS;
    execution.lpVerb = verb.as_ptr();
    execution.lpFile = file.as_ptr();
    execution.lpParameters = parameters.as_ptr();
    execution.lpDirectory = null();
    execution.nShow = 0;
    execution.hProcess = null_mut();
    if unsafe { ShellExecuteExW(&mut execution) } == 0 {
        let code = unsafe { GetLastError() };
        return if code == 1223 {
            Err("管理员授权已取消；请重新更新并在 Windows 提示中选择“是”。".into())
        } else {
            Err(format!("无法启动管理员更新进程（Windows 错误 {code}）"))
        };
    }
    if execution.hProcess.is_null() {
        return Err("管理员更新进程没有返回有效句柄".into());
    }
    unsafe {
        WaitForSingleObject(execution.hProcess, INFINITE);
    }
    let mut exit_code = 1u32;
    let read_ok = unsafe { GetExitCodeProcess(execution.hProcess, &mut exit_code) };
    unsafe {
        CloseHandle(execution.hProcess);
    }
    if read_ok == 0 {
        return Err("无法读取管理员更新进程结果".into());
    }
    if exit_code != 0 {
        return Err(format!("管理员更新脚本执行失败（退出码 {exit_code}）"));
    }
    Ok(())
}

#[cfg(not(target_os = "windows"))]
fn run_elevated_script(script: &Path) -> Result<(), String> {
    let status = Command::new("powershell")
        .args(["-NoProfile", "-ExecutionPolicy", "Bypass", "-File"])
        .arg(script)
        .status()
        .map_err(|e| e.to_string())?;
    if status.success() {
        Ok(())
    } else {
        Err("更新脚本执行失败".into())
    }
}

fn powershell_path(path: &Path) -> String {
    let text = path.to_string_lossy();
    let normalized = if let Some(unc) = text.strip_prefix(r"\\?\UNC\") {
        format!(r"\\{unc}")
    } else {
        text.strip_prefix(r"\\?\").unwrap_or(&text).to_string()
    };
    normalized.replace('\'', "''")
}

fn update_script(session: &UpdateInstallSession) -> String {
    let state_path = session.data_root.join("update").join("installed.json");
    let pending_path = session.data_root.join("update").join("pending.json");
    let error_path = session.data_root.join("update").join("apply-error.log");
    let escaped = powershell_path;
    let content = format!("$ErrorActionPreference='Stop'; try {{ $p=Get-Process -Id {} -ErrorAction SilentlyContinue; if ($p) {{ $p.WaitForExit() }}; Copy-Item -Path '{}\\*' -Destination '{}' -Recurse -Force; [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName('{}')) | Out-Null; [IO.File]::WriteAllText('{}', '{{\"version\":\"{}\"}}', [Text.UTF8Encoding]::new($false)); Remove-Item -LiteralPath '{}' -Force -ErrorAction SilentlyContinue; Remove-Item -LiteralPath '{}' -Force -ErrorAction SilentlyContinue; exit 0 }} catch {{ [IO.File]::WriteAllText('{}', ($_ | Out-String), [Text.UTF8Encoding]::new($false)); exit 1 }}", session.parent_pid, escaped(&session.stage), escaped(&session.root), escaped(&state_path), escaped(&state_path), session.version, escaped(&pending_path), escaped(&error_path), escaped(&error_path));
    format!("\u{feff}{content}")
}

fn install_update(app: &AppHandle, session: &UpdateInstallSession) -> Result<(), String> {
    if !session.stage.is_dir() || !session.root.is_dir() {
        return Err("更新目录不存在或已被移动".into());
    }
    emit_update_progress(
        app,
        0,
        8,
        "准备安装",
        "正在校验更新环境…",
        "独立更新器已启动。",
        false,
        false,
    );
    let script = session
        .data_root
        .join("update")
        .join("apply-depth-batch.ps1");
    let error_path = session.data_root.join("update").join("apply-error.log");
    fs::create_dir_all(script.parent().ok_or("更新脚本目录无效")?).map_err(|e| e.to_string())?;
    // Windows PowerShell 5.1 needs a BOM for Chinese user/install paths.
    fs::write(&script, update_script(session)).map_err(|e| format!("创建更新脚本失败：{e}"))?;
    emit_update_progress(
        app,
        1,
        22,
        "关闭旧版本",
        "正在等待旧版本安全退出…",
        "不会影响已保存的任务和参数。",
        false,
        false,
    );
    emit_update_progress(
        app,
        2,
        42,
        "安装新版本",
        "等待管理员授权并替换程序文件…",
        "请在 Windows 提示中允许此次更新。",
        false,
        false,
    );
    if let Err(error) = run_elevated_script(&script) {
        let detail = fs::read_to_string(&error_path).unwrap_or_default();
        return Err(if detail.trim().is_empty() {
            error
        } else {
            detail.trim().to_string()
        });
    }
    emit_update_progress(
        app,
        3,
        91,
        "启动新版本",
        "更新安装完成，正在重新启动软件…",
        "新版本将自动打开。",
        false,
        false,
    );
    Command::new(session.root.join("SHIYIN-Depth-Batch.exe"))
        .spawn()
        .map_err(|e| format!("重新启动软件失败：{e}"))?;
    emit_update_progress(
        app,
        4,
        100,
        "更新完成",
        "新版本已成功启动。",
        "此窗口即将自动关闭。",
        false,
        true,
    );
    thread::sleep(Duration::from_millis(1600));
    app.exit(0);
    Ok(())
}

#[tauri::command]
fn run_depth_batch_update_session(
    app: AppHandle,
    state: State<'_, UpdateSessionState>,
) -> Result<(), String> {
    let session = state
        .session
        .lock()
        .map_err(|_| "更新会话状态异常".to_string())?
        .take()
        .ok_or("更新会话已经启动")?;
    let handle = app.clone();
    tauri::async_runtime::spawn_blocking(move || {
        if let Err(error) = install_update(&handle, &session) {
            emit_update_progress(
                &handle,
                2,
                42,
                "更新失败",
                &error,
                "软件尚未完成替换，请重新打开后重试。",
                true,
                false,
            );
        }
    });
    Ok(())
}
pub fn apply_from_args() -> bool {
    let args: Vec<String> = std::env::args().collect();
    if !args.iter().any(|arg| arg == "--apply-depth-batch-update") {
        return false;
    }
    let value = |name: &str| {
        args.iter()
            .position(|arg| arg == name)
            .and_then(|index| args.get(index + 1))
            .cloned()
    };
    let (Some(pid), Some(stage)) = (value("--parent-pid"), value("--stage")) else {
        return true;
    };
    let Some(root) = std::env::current_exe()
        .ok()
        .and_then(|path| path.parent().map(Path::to_path_buf))
    else {
        return true;
    };
    let script = data(&root).join("update").join("apply-depth-batch.ps1");
    let root_text = root.display().to_string().replace('\'', "''");
    let version = Path::new(&stage)
        .file_name()
        .and_then(|name| name.to_str())
        .filter(|value| release_id(value))
        .unwrap_or("");
    let state_path = installed_file(&root)
        .display()
        .to_string()
        .replace('\'', "''");
    let pending_path = pending_file(&root)
        .display()
        .to_string()
        .replace('\'', "''");
    let error_path = data(&root)
        .join("update")
        .join("apply-error.log")
        .display()
        .to_string()
        .replace('\'', "''");
    let content = format!("$ErrorActionPreference='Stop'; try {{ $p=Get-Process -Id {pid} -ErrorAction SilentlyContinue; if ($p) {{ $p.WaitForExit() }}; Copy-Item -Path '{}\\*' -Destination '{root_text}' -Recurse -Force; [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName('{state_path}')) | Out-Null; [IO.File]::WriteAllText('{state_path}', '{{\"version\":\"{version}\"}}', [Text.UTF8Encoding]::new($false)); Remove-Item -LiteralPath '{pending_path}' -Force -ErrorAction SilentlyContinue; Remove-Item -LiteralPath '{error_path}' -Force -ErrorAction SilentlyContinue; Start-Process -FilePath '{root_text}\\SHIYIN-Depth-Batch.exe' }} catch {{ [IO.File]::WriteAllText('{error_path}', ($_ | Out-String), [Text.UTF8Encoding]::new($false)); Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('更新安装失败，详情已写入 apply-error.log。','SHIYIN 更新器') | Out-Null }}", stage.replace('\'', "''"));
    if let Some(parent) = script.parent() {
        let _ = fs::create_dir_all(parent);
    }
    if fs::write(&script, format!("\u{feff}{content}")).is_ok() {
        let script_text = script.display().to_string().replace('\'', "''");
        let elevate = format!("$script='{script_text}'; Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList ('-NoProfile -ExecutionPolicy Bypass -File \"' + $script + '\"')");
        let _ = Command::new("powershell.exe")
            .args([
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                &elevate,
            ])
            .spawn();
    }
    true
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    #[cfg(windows)]
    fn update_script_executes_and_reports_copy_failure() {
        let temp = tempdir().unwrap();
        let base = temp.path().join("更新 测试's");
        let stage = base.join("stage");
        let root = base.join("install");
        let data_root = base.join("data");
        fs::create_dir_all(stage.join("worker")).unwrap();
        fs::create_dir_all(&root).unwrap();
        fs::create_dir_all(data_root.join("update")).unwrap();
        fs::write(stage.join("worker/test.txt"), "new version").unwrap();
        let session = UpdateInstallSession {
            parent_pid: 0,
            stage: fs::canonicalize(&stage).unwrap(),
            root: fs::canonicalize(&root).unwrap(),
            data_root,
            version: "20260922105810".into(),
        };
        let pending = session.data_root.join("update/pending.json");
        let installed = session.data_root.join("update/installed.json");
        let error = session.data_root.join("update/apply-error.log");
        let script = base.join("apply.ps1");
        fs::write(&pending, "pending").unwrap();
        fs::write(&script, update_script(&session).replace("Get-Process -Id 0", "Get-Process -Id 2147483647")).unwrap();
        let run = || Command::new("powershell.exe")
            .args(["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File"])
            .arg(&script).output().unwrap();
        let output = run();
        assert!(output.status.success(), "{}", String::from_utf8_lossy(&output.stderr));
        assert_eq!(fs::read_to_string(root.join("worker/test.txt")).unwrap(), "new version");
        assert!(fs::read_to_string(&installed).unwrap().contains(&session.version));
        assert!(!pending.exists());
        assert!(!error.exists());
        // Force a real copy failure; the installed version must not advance.
        use std::os::windows::fs::OpenOptionsExt;
        let _locked = fs::OpenOptions::new().read(true).share_mode(0)
            .open(root.join("worker/test.txt")).unwrap();
        fs::write(&pending, "pending").unwrap();
        fs::write(&installed, "previous version").unwrap();
        let output = run();
        assert_eq!(output.status.code(), Some(1));
        assert!(!fs::read_to_string(error).unwrap().trim().is_empty());
        assert!(pending.exists());
        assert_eq!(fs::read_to_string(installed).unwrap(), "previous version");
    }

    #[test]
    fn modelscope_fallback_reports_signed_release() {
        let temp = tempdir().unwrap();
        save(
            temp.path(),
            &UpdateSettings {
                enabled: true,
                lan_update_url: "http://127.0.0.1:9".into(),
            },
        )
        .unwrap();
        let source = catalog(temp.path()).unwrap();
        assert!(source.package_url.contains("modelscope.cn"));
        assert!(release_id(&source.manifest.version));
        assert_eq!(info(&source.manifest, temp.path()).available,
            source.manifest.version.as_str() > BASELINE_RELEASE.trim());
    }
}
