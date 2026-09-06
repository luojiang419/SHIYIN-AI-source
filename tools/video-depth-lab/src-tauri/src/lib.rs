use rfd::FileDialog;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{
    fs,
    io::{BufRead, BufReader, Read},
    path::{Path, PathBuf},
    process::{Command, Stdio},
    sync::{Arc, Mutex},
    thread,
    time::{SystemTime, UNIX_EPOCH},
};
use tauri::{AppHandle, Emitter, Manager, State};

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

#[cfg(target_os = "windows")]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

const LAB_ROOT_ENV: &str = "SHIYIN_VIDEO_DEPTH_LAB_ROOT";
const MAX_VIDEO_BYTES: u64 = 20 * 1024 * 1024 * 1024;

#[derive(Clone)]
struct LabState {
    root: PathBuf,
    operation_lock: Arc<Mutex<()>>,
    active_pid: Arc<Mutex<Option<u32>>>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct VideoPayload {
    path: String,
    name: String,
    size: u64,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
struct InferenceRequest {
    input_path: String,
    output_root: String,
    model: String,
    input_size: u32,
    target_fps: f64,
    max_frames: i32,
    max_resolution: i32,
    parameters: Value,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
struct PostprocessRequest {
    raw_path: String,
    output_path: String,
    parameters: Value,
}

fn is_lab_root(path: &Path) -> bool {
    path.join("worker/main.py").is_file()
}

fn locate_lab_root() -> Result<PathBuf, String> {
    let mut candidates = Vec::new();
    if let Ok(value) = std::env::var(LAB_ROOT_ENV) {
        if !value.trim().is_empty() {
            candidates.push(PathBuf::from(value.trim()));
        }
    }
    candidates.push(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(".."));
    if let Ok(current) = std::env::current_dir() {
        candidates.extend(current.ancestors().map(Path::to_path_buf));
    }
    if let Ok(executable) = std::env::current_exe() {
        candidates.extend(executable.ancestors().map(Path::to_path_buf));
    }
    for candidate in candidates {
        if is_lab_root(&candidate) {
            return candidate
                .canonicalize()
                .map_err(|error| format!("无法解析工具目录：{error}"));
        }
    }
    Err("无法定位 video-depth-lab；可设置 SHIYIN_VIDEO_DEPTH_LAB_ROOT".to_string())
}

fn python_executable(root: &Path) -> Result<PathBuf, String> {
    let candidates = if cfg!(target_os = "windows") {
        vec![
            root.join("runtime/venv/Scripts/python.exe"),
            root.join("runtime/venv/python.exe"),
        ]
    } else {
        vec![root.join("runtime/venv/bin/python")]
    };
    candidates
        .into_iter()
        .find(|path| path.is_file())
        .ok_or_else(|| "推理环境尚未安装，请先运行 setup.ps1".to_string())
}

fn validate_video(path: &Path) -> Result<VideoPayload, String> {
    if !path.is_file() {
        return Err("输入视频不存在".to_string());
    }
    let extension = path
        .extension()
        .and_then(|value| value.to_str())
        .unwrap_or("")
        .to_ascii_lowercase();
    if !matches!(
        extension.as_str(),
        "mp4" | "mov" | "mkv" | "avi" | "webm" | "m4v"
    ) {
        return Err("仅支持 MP4、MOV、MKV、AVI、WEBM 或 M4V 视频".to_string());
    }
    let metadata = fs::metadata(path).map_err(|error| format!("无法读取视频信息：{error}"))?;
    if metadata.len() == 0 || metadata.len() > MAX_VIDEO_BYTES {
        return Err("输入视频必须大于 0 且不超过 20GB".to_string());
    }
    Ok(VideoPayload {
        path: path.display().to_string(),
        name: path
            .file_name()
            .and_then(|value| value.to_str())
            .unwrap_or("input-video")
            .to_string(),
        size: metadata.len(),
    })
}

fn load_video_payload(root: &Path, path: &Path) -> Result<Value, String> {
    let payload = validate_video(path)?;
    let probe = run_worker(
        None,
        root,
        &[
            "probe".to_string(),
            "--input".to_string(),
            payload.path.clone(),
        ],
        None,
    )?;
    Ok(json!({
        "path": payload.path,
        "name": payload.name,
        "size": payload.size,
        "width": probe.get("width").and_then(Value::as_u64).unwrap_or(0),
        "height": probe.get("height").and_then(Value::as_u64).unwrap_or(0),
        "fps": probe.get("fps").and_then(Value::as_f64).unwrap_or(0.0),
        "duration": probe.get("duration").and_then(Value::as_f64).unwrap_or(0.0),
        "frameCount": probe.get("frameCount").and_then(Value::as_u64).unwrap_or(0)
    }))
}

fn hidden_command(program: &Path) -> Command {
    let mut command = Command::new(program);
    #[cfg(target_os = "windows")]
    command.creation_flags(CREATE_NO_WINDOW);
    command
}

fn run_worker(
    app: Option<&AppHandle>,
    root: &Path,
    args: &[String],
    active_pid: Option<&Arc<Mutex<Option<u32>>>>,
) -> Result<Value, String> {
    let python = python_executable(root)?;
    let mut command = hidden_command(&python);
    command
        .arg(root.join("worker/main.py"))
        .args(args)
        .current_dir(root)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .env("PYTHONUTF8", "1")
        .env("PYTHONIOENCODING", "utf-8")
        .env_remove("HTTP_PROXY")
        .env_remove("HTTPS_PROXY")
        .env_remove("ALL_PROXY");
    let mut child = command
        .spawn()
        .map_err(|error| format!("无法启动视频深度 worker：{error}"))?;
    if let Some(slot) = active_pid {
        *slot
            .lock()
            .map_err(|_| "worker 进程状态锁已损坏".to_string())? = Some(child.id());
    }
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| "无法读取 worker 输出".to_string())?;
    let stderr = child
        .stderr
        .take()
        .ok_or_else(|| "无法读取 worker 错误输出".to_string())?;
    let stderr_reader = thread::spawn(move || {
        let mut content = String::new();
        let _ = BufReader::new(stderr).read_to_string(&mut content);
        content
    });
    let mut result = None;
    let mut worker_error = None;
    for line in BufReader::new(stdout).lines().map_while(Result::ok) {
        let Ok(value) = serde_json::from_str::<Value>(&line) else {
            continue;
        };
        match value.get("type").and_then(Value::as_str) {
            Some("progress") => {
                if let Some(handle) = app {
                    let _ = handle.emit("depth-progress", &value);
                }
            }
            Some("result") => result = value.get("result").cloned(),
            Some("error") => {
                worker_error = value
                    .get("error")
                    .and_then(Value::as_str)
                    .map(str::to_string)
            }
            _ => {}
        }
    }
    let status = child
        .wait()
        .map_err(|error| format!("无法等待 worker：{error}"))?;
    if let Some(slot) = active_pid {
        *slot
            .lock()
            .map_err(|_| "worker 进程状态锁已损坏".to_string())? = None;
    }
    let stderr = stderr_reader.join().unwrap_or_default();
    if !status.success() || result.is_none() {
        let detail = stderr
            .lines()
            .rev()
            .take(8)
            .collect::<Vec<_>>()
            .into_iter()
            .rev()
            .collect::<Vec<_>>()
            .join(" | ");
        let message = worker_error.unwrap_or_else(|| "视频深度 worker 未返回结果".to_string());
        return Err(if detail.is_empty() {
            message
        } else {
            format!("{message}：{detail}")
        });
    }
    Ok(result.expect("result checked above"))
}

fn clean_name(value: &str, fallback: &str, extension: &str) -> String {
    let name: String = value
        .chars()
        .map(|character| {
            if character.is_control()
                || matches!(
                    character,
                    '\\' | '/' | ':' | '*' | '?' | '"' | '<' | '>' | '|'
                )
            {
                '_'
            } else {
                character
            }
        })
        .collect();
    let mut name = name.trim().trim_end_matches(['.', ' ']).to_string();
    if name.is_empty() {
        name = fallback.to_string();
    }
    if !name.to_ascii_lowercase().ends_with(extension) {
        name.push_str(extension);
    }
    name
}

fn run_id(model: &str) -> String {
    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();
    format!("{timestamp}-{}", model.replace('_', "-"))
}

#[tauri::command]
async fn get_runtime_status(state: State<'_, LabState>) -> Result<Value, String> {
    let snapshot = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        run_worker(None, &snapshot.root, &["status".to_string()], None)
    })
    .await
    .map_err(|error| format!("状态检查后台任务失败：{error}"))?
}

#[tauri::command]
fn choose_input_video(state: State<'_, LabState>) -> Result<Option<Value>, String> {
    let Some(path) = FileDialog::new()
        .set_title("选择输入视频")
        .add_filter("视频", &["mp4", "mov", "mkv", "avi", "webm", "m4v"])
        .pick_file()
    else {
        return Ok(None);
    };
    load_video_payload(&state.root, &path).map(Some)
}

#[tauri::command]
fn load_input_video(state: State<'_, LabState>, path: String) -> Result<Value, String> {
    load_video_payload(&state.root, Path::new(path.trim()))
}

#[tauri::command]
fn choose_output_directory() -> Option<String> {
    FileDialog::new()
        .set_title("选择深度视频输出目录")
        .pick_folder()
        .map(|path| path.display().to_string())
}

#[tauri::command]
async fn run_inference(
    app: AppHandle,
    state: State<'_, LabState>,
    request: InferenceRequest,
) -> Result<Value, String> {
    let snapshot = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        let _guard = snapshot
            .operation_lock
            .lock()
            .map_err(|_| "推理任务锁已损坏".to_string())?;
        validate_video(Path::new(request.input_path.trim()))?;
        if !(196..=756).contains(&request.input_size) || request.input_size % 14 != 0 {
            return Err("模型输入尺寸必须位于 196–756 且为 14 的倍数".to_string());
        }
        if request.target_fps != -1.0 && !(1.0..=240.0).contains(&request.target_fps) {
            return Err("目标 FPS 必须为 -1（原始 FPS）或位于 1–240".to_string());
        }
        if request.max_frames != -1 && !(1..=1_000_000).contains(&request.max_frames) {
            return Err("最大帧数必须为 -1（全部帧）或 1–1000000".to_string());
        }
        if request.max_resolution != -1 && !(256..=8192).contains(&request.max_resolution) {
            return Err("输出最长边必须为 -1（原始分辨率）或位于 256–8192".to_string());
        }
        let base = if request.output_root.trim().is_empty() {
            snapshot.root.join("runtime/outputs")
        } else {
            PathBuf::from(request.output_root.trim())
        };
        fs::create_dir_all(&base).map_err(|error| format!("无法创建输出根目录：{error}"))?;
        let output_dir = base.join(run_id(&request.model));
        let args = vec![
            "infer".to_string(),
            "--model".to_string(),
            request.model,
            "--input".to_string(),
            request.input_path,
            "--output-dir".to_string(),
            output_dir.display().to_string(),
            "--input-size".to_string(),
            request.input_size.to_string(),
            "--target-fps".to_string(),
            request.target_fps.to_string(),
            "--max-frames".to_string(),
            request.max_frames.to_string(),
            "--max-resolution".to_string(),
            request.max_resolution.to_string(),
            "--params-json".to_string(),
            serde_json::to_string(&request.parameters).map_err(|error| error.to_string())?,
        ];
        run_worker(
            Some(&app),
            &snapshot.root,
            &args,
            Some(&snapshot.active_pid),
        )
    })
    .await
    .map_err(|error| format!("推理后台任务失败：{error}"))?
}

#[tauri::command]
async fn apply_parameters(
    app: AppHandle,
    state: State<'_, LabState>,
    request: PostprocessRequest,
) -> Result<Value, String> {
    let snapshot = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        let _guard = snapshot
            .operation_lock
            .lock()
            .map_err(|_| "参数任务锁已损坏".to_string())?;
        let args = vec![
            "postprocess".to_string(),
            "--raw".to_string(),
            request.raw_path,
            "--output".to_string(),
            request.output_path,
            "--params-json".to_string(),
            serde_json::to_string(&request.parameters).map_err(|error| error.to_string())?,
        ];
        run_worker(
            Some(&app),
            &snapshot.root,
            &args,
            Some(&snapshot.active_pid),
        )
    })
    .await
    .map_err(|error| format!("参数后台任务失败：{error}"))?
}

#[tauri::command]
fn export_depth_video(
    source_path: String,
    suggested_name: String,
) -> Result<Option<String>, String> {
    let source = PathBuf::from(source_path.trim());
    if !source.is_file() {
        return Err("当前深度视频不存在".to_string());
    }
    let filename = clean_name(&suggested_name, "depth-video", ".mp4");
    let Some(path) = FileDialog::new()
        .set_title("导出深度视频")
        .set_file_name(&filename)
        .add_filter("MP4 深度视频", &["mp4"])
        .save_file()
    else {
        return Ok(None);
    };
    fs::copy(&source, &path).map_err(|error| format!("深度视频导出失败：{error}"))?;
    Ok(Some(path.display().to_string()))
}

#[tauri::command]
fn export_parameter_config(
    content: String,
    suggested_name: String,
) -> Result<Option<String>, String> {
    let value: Value =
        serde_json::from_str(&content).map_err(|error| format!("参数配置 JSON 无效：{error}"))?;
    if !value.is_object() {
        return Err("参数配置必须是 JSON 对象".to_string());
    }
    let filename = clean_name(&suggested_name, "video-depth-parameters", ".json");
    let Some(path) = FileDialog::new()
        .set_title("导出视频深度参数配置")
        .set_file_name(&filename)
        .add_filter("JSON 参数配置", &["json"])
        .save_file()
    else {
        return Ok(None);
    };
    fs::write(&path, format!("{}\n", content.trim()))
        .map_err(|error| format!("配置保存失败：{error}"))?;
    Ok(Some(path.display().to_string()))
}

#[tauri::command]
fn import_parameter_config() -> Result<Option<String>, String> {
    let Some(path) = FileDialog::new()
        .set_title("导入视频深度参数配置")
        .add_filter("JSON 参数配置", &["json"])
        .pick_file()
    else {
        return Ok(None);
    };
    let metadata = fs::metadata(&path).map_err(|error| format!("无法读取配置：{error}"))?;
    if metadata.len() > 2 * 1024 * 1024 {
        return Err("参数配置不能超过 2MB".to_string());
    }
    let content = fs::read_to_string(&path).map_err(|error| format!("无法读取配置：{error}"))?;
    let value: Value =
        serde_json::from_str(&content).map_err(|error| format!("参数配置 JSON 无效：{error}"))?;
    if !value.is_object() {
        return Err("参数配置必须是 JSON 对象".to_string());
    }
    Ok(Some(content))
}

#[tauri::command]
fn open_output_directory(path: String) -> Result<(), String> {
    let directory = PathBuf::from(path.trim());
    if !directory.is_dir() {
        return Err("输出目录不存在".to_string());
    }
    #[cfg(target_os = "windows")]
    {
        let mut command = Command::new("explorer.exe");
        command.arg(&directory);
        command
            .spawn()
            .map_err(|error| format!("无法打开输出目录：{error}"))?;
    }
    Ok(())
}

#[tauri::command]
fn cancel_inference(state: State<'_, LabState>) -> Result<bool, String> {
    let pid = *state
        .active_pid
        .lock()
        .map_err(|_| "worker 进程状态锁已损坏".to_string())?;
    let Some(pid) = pid else {
        return Ok(false);
    };
    #[cfg(target_os = "windows")]
    {
        let mut command = hidden_command(Path::new("taskkill.exe"));
        let status = command
            .args(["/PID", &pid.to_string(), "/T", "/F"])
            .status()
            .map_err(|error| format!("无法停止 worker：{error}"))?;
        return Ok(status.success());
    }
    #[allow(unreachable_code)]
    Ok(false)
}

pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            let root = locate_lab_root().map_err(std::io::Error::other)?;
            app.manage(LabState {
                root,
                operation_lock: Arc::new(Mutex::new(())),
                active_pid: Arc::new(Mutex::new(None)),
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_runtime_status,
            choose_input_video,
            load_input_video,
            choose_output_directory,
            run_inference,
            apply_parameters,
            export_depth_video,
            export_parameter_config,
            import_parameter_config,
            open_output_directory,
            cancel_inference
        ])
        .run(tauri::generate_context!())
        .expect("SHIYIN 视频深度验证台启动失败");
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn recognizes_lab_root_and_runtime_python() {
        let temp = tempdir().unwrap();
        fs::create_dir_all(temp.path().join("worker")).unwrap();
        fs::create_dir_all(temp.path().join("runtime/venv/Scripts")).unwrap();
        fs::write(temp.path().join("worker/main.py"), b"pass").unwrap();
        fs::write(
            temp.path().join("runtime/venv/Scripts/python.exe"),
            b"python",
        )
        .unwrap();
        assert!(is_lab_root(temp.path()));
        assert!(python_executable(temp.path())
            .unwrap()
            .ends_with("python.exe"));
    }

    #[test]
    fn cleans_export_filename() {
        assert_eq!(clean_name("bad:name", "fallback", ".mp4"), "bad_name.mp4");
        assert_eq!(clean_name("clip.mp4", "fallback", ".mp4"), "clip.mp4");
    }

    #[test]
    fn validates_supported_video() {
        let temp = tempdir().unwrap();
        let path = temp.path().join("sample.mp4");
        fs::write(&path, b"video").unwrap();
        let payload = validate_video(&path).unwrap();
        assert_eq!(payload.name, "sample.mp4");
        assert!(validate_video(&temp.path().join("missing.mp4")).is_err());
    }

    #[test]
    #[ignore = "requires the locally deployed Python environment and model files"]
    fn real_worker_status_reports_two_ready_models() {
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .canonicalize()
            .unwrap();
        let result = run_worker(None, &root, &["status".to_string()], None).unwrap();
        assert_eq!(result.get("ready").and_then(Value::as_bool), Some(true));
        assert_eq!(
            result.get("models").and_then(Value::as_array).map(Vec::len),
            Some(2)
        );
        let sample = root.join(
            "runtime/sources/video-depth-anything/assets/example_videos/davis_rollercoaster.mp4",
        );
        let payload = load_video_payload(&root, &sample).unwrap();
        assert_eq!(payload.get("width").and_then(Value::as_u64), Some(960));
        assert_eq!(payload.get("height").and_then(Value::as_u64), Some(540));
        assert_eq!(payload.get("frameCount").and_then(Value::as_u64), Some(70));
    }
}
