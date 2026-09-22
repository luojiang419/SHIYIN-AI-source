use ed25519_dalek::{Signature, Verifier, VerifyingKey};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{collections::HashSet, fs, io::Read, path::{Path, PathBuf}, process::Command};
use tauri::{AppHandle, State};

const PUBLIC_KEY: &str = include_str!("../distribution-public-key.hex");
const PRODUCT: &str = "depth-batch";
const DEFAULT_LAN: &str = "http://192.168.0.24:3011";

#[derive(Default)]
pub struct UpdateState { pub root: PathBuf }

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
#[serde(default)]
pub struct UpdateSettings { pub enabled: bool, pub lan_update_url: String }
impl Default for UpdateSettings { fn default() -> Self { Self { enabled: true, lan_update_url: DEFAULT_LAN.into() } } }

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct UpdateInfo { pub current_version: String, pub latest_version: String, pub available: bool, pub downloaded: bool, pub asset_size: u64, pub release_notes: String }
#[derive(Deserialize)] struct Envelope { payload: String, signature: String, public_key: String }
#[derive(Deserialize)] struct Package { name: String, size: u64, sha256: String }
#[derive(Deserialize)] struct FileEntry { path: String, size: u64, sha256: String }
#[derive(Deserialize)] struct Manifest { product: String, version: String, #[serde(default)] notes: String, package: Package, files: Vec<FileEntry> }

fn data(root: &Path) -> PathBuf { root.join("data") }
fn settings_file(root: &Path) -> PathBuf { data(root).join("config").join("update.json") }
fn pending_file(root: &Path) -> PathBuf { data(root).join("update").join("pending.json") }
fn hex<const N: usize>(value: &str) -> Result<[u8; N], String> { if value.len()!=N*2 || !value.is_ascii(){return Err("更新签名编码无效".into())}; let mut output=[0;N]; for(i,byte) in output.iter_mut().enumerate(){*byte=u8::from_str_radix(&value[i*2..i*2+2],16).map_err(|_|"更新签名编码无效")?;} Ok(output) }
fn hash(path: &Path)->Result<String,String>{let mut file=fs::File::open(path).map_err(|e|e.to_string())?;let mut h=Sha256::new();let mut b=[0;65536];loop{let n=file.read(&mut b).map_err(|e|e.to_string())?;if n==0{break}h.update(&b[..n]);}Ok(format!("{:x}",h.finalize()))}
fn release_id(value:&str)->bool{value.len()==14&&value.bytes().all(|b|b.is_ascii_digit())}
fn relative(value:&str)->Result<PathBuf,String>{if value.is_empty()||value.contains(['\\',':'])||value.split('/').any(|p|p.is_empty()||p=="."||p==".."){return Err("更新文件路径无效".into())}Ok(value.split('/').collect())}
fn verify(raw:&str)->Result<Manifest,String>{let e:Envelope=serde_json::from_str(raw).map_err(|_|"更新清单无效")?;if e.public_key!=PUBLIC_KEY.trim(){return Err("更新源公钥不受信任".into())};let key=VerifyingKey::from_bytes(&hex::<32>(&e.public_key)?).map_err(|_|"更新公钥无效")?;key.verify(e.payload.as_bytes(),&Signature::from_bytes(&hex::<64>(&e.signature)?)).map_err(|_|"更新清单签名校验失败")?;let m:Manifest=serde_json::from_str(&e.payload).map_err(|_|"更新清单内容无效")?;if m.product!=PRODUCT||!release_id(&m.version)||m.files.is_empty()||m.files.len()>10000||m.package.name!=format!("SHIYIN-Depth-Batch-Update-{}.shiyin-update",m.version)||m.package.size==0||hex::<32>(&m.package.sha256).is_err(){return Err("更新包不属于 SHIYIN-Depth-Batch 或格式无效".into())};let mut seen=HashSet::new();for f in &m.files{relative(&f.path)?;if f.size==0||hex::<32>(&f.sha256).is_err()||!seen.insert(f.path.to_ascii_lowercase()){return Err("更新文件清单无效".into())}}Ok(m)}
fn settings(root:&Path)->UpdateSettings{fs::read_to_string(settings_file(root)).ok().and_then(|raw|serde_json::from_str(&raw).ok()).unwrap_or_default()}
fn save(root:&Path,s:&UpdateSettings)->Result<(),String>{let target=settings_file(root);fs::create_dir_all(target.parent().unwrap()).map_err(|e|e.to_string())?;fs::write(target,serde_json::to_vec_pretty(s).map_err(|e|e.to_string())?).map_err(|e|e.to_string())}
fn base(s:&UpdateSettings)->Result<String,String>{let value=s.lan_update_url.trim().trim_end_matches('/');if !value.starts_with("http://")||value.contains(['?','#']){return Err("局域网更新地址无效".into())}Ok(value.into())}
fn catalog(root:&Path)->Result<(Manifest,String),String>{let s=settings(root);if !s.enabled{return Err("已关闭自动更新".into())};let base=base(&s)?;let response=ureq::get(&format!("{base}/v1/catalog?product={PRODUCT}")).call().map_err(|e|format!("无法连接更新服务器：{e}"))?;let raw=response.into_body().read_to_string().map_err(|e|e.to_string())?;Ok((verify(&raw)?,base))}
fn downloaded(root:&Path, version:&str)->bool{fs::read_to_string(pending_file(root)).ok().and_then(|raw|serde_json::from_str::<serde_json::Value>(&raw).ok()).and_then(|v|v["version"].as_str().map(str::to_string)).as_deref()==Some(version)}
fn info(m:&Manifest,root:&Path)->UpdateInfo{UpdateInfo{current_version:env!("CARGO_PKG_VERSION").into(),latest_version:m.version.clone(),available:true,downloaded:downloaded(root,&m.version),asset_size:m.package.size,release_notes:m.notes.clone()}}

#[tauri::command] pub fn get_update_settings(state:State<'_,UpdateState>)->UpdateSettings{settings(&state.root)}
#[tauri::command] pub fn save_update_settings(state:State<'_,UpdateState>,mut s:UpdateSettings)->Result<UpdateSettings,String>{s.lan_update_url=s.lan_update_url.trim().trim_end_matches('/').into();let _=base(&s)?;save(&state.root,&s)?;Ok(s)}
#[tauri::command] pub async fn check_for_update(state:State<'_,UpdateState>)->Result<UpdateInfo,String>{let root=state.root.clone();tauri::async_runtime::spawn_blocking(move||{let(m,_)=catalog(&root)?;Ok(info(&m,&root))}).await.map_err(|e|e.to_string())?}
#[tauri::command] pub async fn download_update(state:State<'_,UpdateState>)->Result<UpdateInfo,String>{let root=state.root.clone();tauri::async_runtime::spawn_blocking(move||{let(m,base)=catalog(&root)?;let update=data(&root).join("update");fs::create_dir_all(&update).map_err(|e|e.to_string())?;let package_path=update.join(&m.package.name);let mut response=ureq::get(&format!("{base}/hot-depth-batch/packages/{}",m.package.name)).call().map_err(|e|format!("下载更新失败：{e}"))?;let mut file=fs::File::create(&package_path).map_err(|e|e.to_string())?;std::io::copy(&mut response.body_mut().as_reader(),&mut file).map_err(|e|e.to_string())?;if hash(&package_path)?!=m.package.sha256{return Err("更新包校验失败".into())};let stage=update.join("staged").join(&m.version);if stage.exists(){fs::remove_dir_all(&stage).map_err(|e|e.to_string())?}fs::create_dir_all(&stage).map_err(|e|e.to_string())?;let archive=fs::File::open(&package_path).map_err(|e|e.to_string())?;let mut zip=zip::ZipArchive::new(archive).map_err(|_|"更新包无法解压")?;for entry in &m.files{let target=stage.join(relative(&entry.path)?);if let Some(parent)=target.parent(){fs::create_dir_all(parent).map_err(|e|e.to_string())?};let mut source=zip.by_name(&entry.path).map_err(|_|"更新包缺少文件")?;let mut output=fs::File::create(&target).map_err(|e|e.to_string())?;std::io::copy(&mut source,&mut output).map_err(|e|e.to_string())?;if target.metadata().map_err(|e|e.to_string())?.len()!=entry.size||hash(&target)?!=entry.sha256{return Err("更新文件校验失败".into())}}fs::write(pending_file(&root),serde_json::json!({"version":m.version,"stage":stage}).to_string()).map_err(|e|e.to_string())?;let mut result=info(&m,&root);result.downloaded=true;Ok(result)}).await.map_err(|e|e.to_string())?}
#[tauri::command] pub fn apply_downloaded_update(app:AppHandle,state:State<'_,UpdateState>)->Result<(),String>{let raw=fs::read_to_string(pending_file(&state.root)).map_err(|_|"没有已下载的更新".to_string())?;let pending:serde_json::Value=serde_json::from_str(&raw).map_err(|_|"更新记录无效")?;let stage=pending["stage"].as_str().ok_or("更新记录无效")?;let exe=std::env::current_exe().map_err(|e|e.to_string())?;Command::new(exe).args(["--apply-depth-batch-update","--parent-pid",&std::process::id().to_string(),"--stage",stage]).spawn().map_err(|e|format!("启动独立更新器失败：{e}"))?;app.exit(0);Ok(())}
pub fn apply_from_args() -> bool {
    let args: Vec<String> = std::env::args().collect();
    if !args.iter().any(|arg| arg == "--apply-depth-batch-update") { return false; }
    let value = |name: &str| args.iter().position(|arg| arg == name).and_then(|index| args.get(index + 1)).cloned();
    let (Some(pid), Some(stage)) = (value("--parent-pid"), value("--stage")) else { return true; };
    let Some(root) = std::env::current_exe().ok().and_then(|path| path.parent().map(Path::to_path_buf)) else { return true; };
    let script = data(&root).join("update").join("apply-depth-batch.ps1");
    let root_text = root.display().to_string().replace('\'', "''");
    let content = format!("$ErrorActionPreference='Stop'; $p=Get-Process -Id {pid} -ErrorAction SilentlyContinue; if ($p) {{ $p.WaitForExit() }}; Copy-Item -LiteralPath '{}\\*' -Destination '{root_text}' -Recurse -Force; Start-Process -FilePath '{root_text}\\SHIYIN-Depth-Batch.exe'", stage.replace('\'', "''"));
    if let Some(parent) = script.parent() { let _ = fs::create_dir_all(parent); }
    if fs::write(&script, content).is_ok() {
        let _ = Command::new("powershell.exe").args(["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script.to_string_lossy().as_ref()]).spawn();
    }
    true
}
