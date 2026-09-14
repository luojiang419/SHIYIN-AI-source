//! 已签名的局域网热更新：用户确认、离线应用、日志恢复和健康重启。
use super::*;
use ed25519_dalek::{Signature, Verifier, VerifyingKey};
use std::net::UdpSocket;

const PUBLIC_KEY: &str = include_str!("../distribution-public-key.hex");
const BASELINE_RELEASE: &str = include_str!("../distribution-baseline.txt");

fn effective_release(applied: &str, baseline: &str) -> String {
    [applied.trim(), baseline.trim()].into_iter()
        .filter(|v| v.len() == 14 && v.bytes().all(|b| b.is_ascii_digit()))
        .max().unwrap_or("").to_string()
}

fn installed_release(data: &Path) -> String {
    let applied = fs::read_to_string(hot_update_state_path(data)).ok()
        .and_then(|s| serde_json::from_str::<serde_json::Value>(&s).ok())
        .and_then(|v| v["version"].as_str().map(str::to_string)).unwrap_or_default();
    effective_release(&applied, BASELINE_RELEASE)
}
const ROOTS: [&str; 3] = ["app/web", "app/backend/canvas-backend", "app/skills"];

#[derive(Clone, Serialize, Deserialize)]
pub(super) struct Manifest {
    protocol_version: u8,
    pub version: String,
    min_desktop_version: String,
    #[serde(default)]
    notes: String,
    #[serde(default)]
    prune_roots: Vec<String>,
    files: Vec<HotUpdateFile>,
}

#[derive(Serialize, Deserialize)]
struct Envelope { payload: String, signature: String, public_key: String }

fn unhex<const N: usize>(s: &str) -> Result<[u8; N], String> {
    if s.len() != N * 2 || !s.is_ascii() { return Err("签名编码无效".into()); }
    let mut out = [0; N];
    for (i, b) in out.iter_mut().enumerate() {
        *b = u8::from_str_radix(&s[i*2..i*2+2], 16).map_err(|_| "签名编码无效")?;
    }
    Ok(out)
}

fn relative(s: &str) -> Result<PathBuf, String> {
    if s != "SHIYIN AI.exe" && !ROOTS.iter().any(|r| s.starts_with(&format!("{r}/"))) {
        return Err("文件不在热更新白名单".into());
    }
    if s.contains(['\\', ':']) || s.split('/').any(|p| p.is_empty() || p == "." || p == ".." || p.ends_with(['.', ' '])) {
        return Err("文件路径无效".into());
    }
    Ok(s.split('/').collect())
}

fn verify(raw: &str) -> Result<Manifest, String> {
    let env: Envelope = serde_json::from_str(raw).map_err(|_| "更新签名清单无效")?;
    if env.public_key != PUBLIC_KEY.trim() { return Err("更新源公钥不受信任".into()); }
    let key = VerifyingKey::from_bytes(&unhex::<32>(&env.public_key)?).map_err(|_| "公钥无效")?;
    let signature = Signature::from_bytes(&unhex::<64>(&env.signature)?);
    key.verify(env.payload.as_bytes(), &signature).map_err(|_| "更新清单签名校验失败")?;
    let m: Manifest = serde_json::from_str(&env.payload).map_err(|_| "更新清单格式错误")?;
    if m.protocol_version != 2 || m.version.len() != 14 || !m.version.bytes().all(|b| b.is_ascii_digit())
        || normalize_version(&m.min_desktop_version).is_none() || m.files.is_empty() || m.files.len() > 20000 {
        return Err("更新清单版本或文件数量无效".into());
    }
    let mut seen = HashSet::new();
    for f in &m.files {
        relative(&f.path)?;
        unhex::<32>(&f.sha256)?;
        if !seen.insert(f.path.to_lowercase()) { return Err("清单有重复文件".into()); }
    }
    if m.prune_roots.iter().any(|r| !ROOTS.contains(&r.as_str())) { return Err("清理范围无效".into()); }
    Ok(m)
}

fn agent() -> ureq::Agent {
    ureq::Agent::new_with_config(ureq::Agent::config_builder().https_only(false)
        .timeout_global(Some(Duration::from_secs(600))).build())
}

fn read_small(agent: &ureq::Agent, url: &str, current: &str) -> Result<String, String> {
    let mut r = agent.get(url).header("X-Shiyin-Version", current).call().map_err(|e| e.to_string())?;
    let mut s = String::new();
    r.body_mut().as_reader().take(16 * 1024 * 1024).read_to_string(&mut s).map_err(|e| e.to_string())?;
    Ok(s)
}

fn discovered() -> Option<String> {
    let sock = UdpSocket::bind("0.0.0.0:0").ok()?;
    sock.set_broadcast(true).ok()?;
    sock.set_read_timeout(Some(Duration::from_millis(750))).ok()?;
    sock.send_to(b"SHIYIN-DISCOVER-2", "255.255.255.255:3012").ok()?;
    let mut buf = [0u8; 2048];
    let (n, _) = sock.recv_from(&mut buf).ok()?;
    let value: serde_json::Value = serde_json::from_slice(&buf[..n]).ok()?;
    if value["public_key"].as_str()? != PUBLIC_KEY.trim() { return None; }
    let url = value["url"].as_str()?;
    let parsed: tauri::Url = url.parse().ok()?;
    if parsed.scheme() != "http" || parsed.host_str().is_none() || !parsed.username().is_empty() { return None; }
    Some(url.trim_end_matches('/').into())
}

pub(super) fn check(data: &Path, settings: &UpdateSettings) -> Result<Option<(Manifest, String, String)>, String> {
    if !settings.lan_update_enabled { return Ok(None); }
    let small_agent = build_lan_update_agent();
    let applied = installed_release(data);
    let current=format!("{} / {}",env!("CARGO_PKG_VERSION"),applied);
    let mut base = settings.lan_update_url.clone();
    let raw = match read_small(&small_agent, &format!("{base}/v1/catalog"), &current) {
        Ok(raw) => raw,
        Err(_) => {
            let Some(found) = discovered() else { return Err("无法连接局域网分发中心，请确认管理员电脑已启动服务。".into()); };
            base = found;
            read_small(&small_agent, &format!("{base}/v1/catalog"), &current)?
        }
    };
    if serde_json::from_str::<serde_json::Value>(&raw).ok().is_some_and(|v| v.get("release").is_some_and(|r| r.is_null())) { return Ok(None); }
    let m = verify(&raw)?;
    if version_is_newer(&m.min_desktop_version, env!("CARGO_PKG_VERSION")) {
        return Err(format!("热更新要求桌面基线 {}，请联系管理员迁移更新器。", m.min_desktop_version));
    }
    if m.version <= applied { return Ok(None); }
    if base != settings.lan_update_url {
        let mut updated = settings.clone(); updated.lan_update_url = base.clone(); save_settings_file(data, &updated)?;
    }
    Ok(Some((m, raw, base)))
}

pub(super) fn information(m: &Manifest, downloaded: bool) -> UpdateInfo {
    UpdateInfo { current_version: env!("CARGO_PKG_VERSION").into(), latest_version: m.version.clone(),
        available: true, downloaded, asset_name: format!("热更新 {}", m.version),
        asset_size: m.files.iter().map(|f| f.size).sum(), release_notes: m.notes.clone(),
        message: "局域网热更新，安装后自动重启".into(), kind: "hot".into() }
}

fn matches(path: &Path, f: &HotUpdateFile) -> bool {
    path.metadata().is_ok_and(|m| m.len() == f.size) && sha256(path).is_ok_and(|s| s.eq_ignore_ascii_case(&f.sha256))
}

pub(super) fn download(root: &Path, data: &Path, m: &Manifest, raw: &str, base: &str) -> Result<(), String> {
    let dir = update_dir(data).join("hot").join(&m.version);
    fs::create_dir_all(dir.join("files")).map_err(|e| e.to_string())?;
    let agent = agent();
    for f in &m.files {
        let rel = relative(&f.path)?;
        let dest = safe_target(root, &rel)?;
        if matches(&dest, f) { continue; }
        let target = dir.join("files").join(&rel);
        if matches(&target, f) { continue; }
        fs::create_dir_all(target.parent().unwrap()).map_err(|e| e.to_string())?;
        let part = target.with_extension("download-part");
        let offset = part.metadata().map(|m| m.len()).unwrap_or(0);
        let offset = if offset < f.size { offset } else { 0 };
        let mut request = agent.get(&format!("{base}/v1/blobs/{}", f.sha256));
        let range = format!("bytes={offset}-");
        if offset > 0 { request = request.header("Range", &range); }
        let mut response = request.call().map_err(|e| format!("下载失败：{e}"))?;
        let resume = offset > 0 && response.status().as_u16() == 206;
        let mut file = OpenOptions::new().create(true).write(true).append(resume).truncate(!resume).open(&part).map_err(|e| e.to_string())?;
        io::copy(&mut response.body_mut().as_reader().take(f.size + 1), &mut file).map_err(|e| e.to_string())?;
        file.sync_all().map_err(|e| e.to_string())?;
        drop(file);
        if !matches(&part, f) { let _ = fs::remove_file(part); return Err(format!("文件校验失败：{}", f.path)); }
        fs::rename(&part, &target).map_err(|e| e.to_string())?;
    }
    let envelope = dir.join("envelope.json");
    fs::write(&envelope, raw).map_err(|e| e.to_string())?;
    save_pending(data, &PendingUpdate { version: m.version.clone(), asset_name: "envelope.json".into(),
        asset_path: envelope.to_string_lossy().into(), sha256: sha256(&envelope)?,
        size: raw.len() as u64, deferred: false, kind: "hot".into() })
}

pub(super) fn pending_valid(data: &Path, p: &PendingUpdate) -> bool {
    let expected = update_dir(data).join("hot").join(&p.version).join("envelope.json");
    p.version.len() == 14 && p.version.bytes().all(|b| b.is_ascii_digit())
        && p.version > installed_release(data)
        && Path::new(&p.asset_path) == expected && sha256(&expected).is_ok_and(|s| s == p.sha256)
        && fs::read_to_string(&expected).ok().and_then(|s| verify(&s).ok()).is_some_and(|m| m.version == p.version)
}

fn safe_target(root: &Path, relative: &Path) -> Result<PathBuf, String> {
    let canonical = root.canonicalize().map_err(|e| e.to_string())?;
    let mut path = root.to_path_buf();
    for part in relative.components() {
        path.push(part);
        if path.exists() && !path.canonicalize().map_err(|e| e.to_string())?.starts_with(&canonical) { return Err("更新路径通过链接越界".into()); }
    }
    Ok(path)
}

#[derive(Serialize, Deserialize)]
struct Change { path: String, existed: bool }

fn rollback(root: &Path, dir: &Path, changes: &[Change]) -> Result<(), String> {
    for c in changes.iter().rev() {
        let rel = relative(&c.path)?;
        let target = safe_target(root, &rel)?;
        let backup = dir.join("backup").join(rel);
        if c.existed {
            if backup.exists() {
                if target.exists() { fs::remove_file(&target).map_err(|e| e.to_string())?; }
                fs::rename(&backup, &target).map_err(|e| e.to_string())?;
            }
        } else if target.exists() { fs::remove_file(target).map_err(|e| e.to_string())?; }
    }
    Ok(())
}

fn write_journal(dir: &Path, changes: &[Change]) -> Result<(), String> {
    let bytes = serde_json::to_vec(changes).map_err(|e| e.to_string())?;
    let part = dir.join("journal.part");
    let mut file = File::create(&part).map_err(|e| e.to_string())?;
    file.write_all(&bytes).and_then(|_| file.sync_all()).map_err(|e| e.to_string())?;
    drop(file);
    fs::rename(part, dir.join("journal.json")).map_err(|e| e.to_string())
}

fn apply(root: &Path, dir: &Path, m: &Manifest) -> Result<Vec<Change>, String> {
    let mut todo: Vec<(String, bool)> = Vec::new();
    for f in &m.files {
        let rel = relative(&f.path)?;
        if matches(&safe_target(root, &rel)?, f) { continue; }
        if !matches(&dir.join("files").join(&rel), f) { return Err(format!("下载文件丢失或损坏：{}", f.path)); }
        todo.push((f.path.clone(), false));
    }
    let expected: HashSet<_> = m.files.iter().map(|f| f.path.to_lowercase()).collect();
    for r in &m.prune_roots {
        let mut files = Vec::new();
        collect_hot_files(&safe_target(root, Path::new(r))?, &mut files)?;
        for file in files {
            let rel = file.strip_prefix(root).map_err(|e| e.to_string())?.to_string_lossy().replace('\\', "/");
            relative(&rel)?;
            if !expected.contains(&rel.to_lowercase()) { todo.push((rel, true)); }
        }
    }
    let mut changes = Vec::new();
    let result = (|| {
        for (name, remove) in todo {
            let rel = relative(&name)?;
            let target = safe_target(root, &rel)?;
            fs::create_dir_all(target.parent().unwrap()).map_err(|e| e.to_string())?;
            changes.push(Change { path: name, existed: target.exists() });
            write_journal(dir, &changes)?;
            if target.exists() {
                let backup = dir.join("backup").join(&rel);
                fs::create_dir_all(backup.parent().unwrap()).map_err(|e| e.to_string())?;
                fs::rename(&target, &backup).map_err(|e| e.to_string())?;
            }
            if !remove {
                let staged = dir.join("files").join(rel);
                fs::copy(staged, &target).map_err(|e| e.to_string())?;
            }
        }
        Ok::<(), String>(())
    })();
    if let Err(error) = result {
        rollback(root, dir, &changes).map_err(|e| format!("{error}；回滚失败：{e}"))?;
        let _ = fs::remove_file(dir.join("journal.json"));
        return Err(error);
    }
    Ok(changes)
}

pub(super) fn session(app: &AppHandle, s: &UpdateInstallSession) -> Result<(), String> {
    let root = Path::new(&s.install_root);
    let data = Path::new(&s.data_root);
    let envelope = Path::new(&s.installer_path);
    let m = verify(&fs::read_to_string(envelope).map_err(|e| e.to_string())?)?;
    let dir = update_dir(data).join("hot").join(&m.version);
    if m.version != s.version || envelope != dir.join("envelope.json") || sha256(envelope)? != s.sha256 { return Err("更新会话不匹配".into()); }
    if version_is_newer(&m.min_desktop_version, env!("CARGO_PKG_VERSION")) { return Err("更新器基线不足".into()); }
    if m.version <= installed_release(data) { return Err("此热更新不晚于已安装基线".into()); }
    emit_progress(app, 1, 12, "关闭旧版本", "正在等待主程序和后端退出…", "热更新已签名并逐文件校验", false, false);
    wait_for_exit_with_timeout(s.old_pid, Duration::from_secs(120))?;
    emit_progress(app, 2, 35, "应用热更新", "正在备份并替换应用文件…", "用户数据保持在独立目录", false, false);
    let changes = match apply(root, &dir, &m) {
        Ok(c) => c,
        Err(e) => {
            clear_pending(data);
            let _ = command_without_console(root.join("SHIYIN AI.exe")).current_dir(root).spawn();
            return Err(format!("更新失败，已恢复旧版：{e}"));
        }
    };
    emit_progress(app, 3, 90, "启动新版本", "正在重启并等待新版本就绪…", "启动失败将恢复旧版本", false, false);
    let ready = dir.join("ready");
    let _ = fs::remove_file(&ready);
    let child = command_without_console(root.join("SHIYIN AI.exe")).current_dir(root)
        .env("SHIYIN_HOT_READY_VERSION", &m.version).spawn();
    let mut child = match child {
        Ok(c) => c,
        Err(e) => { rollback(root, &dir, &changes)?; clear_pending(data); let _=fs::remove_file(dir.join("journal.json")); return Err(format!("重启失败已回滚：{e}")); }
    };
    let until = Instant::now() + Duration::from_secs(90);
    while !ready.exists() && Instant::now() < until {
        if child.try_wait().map_err(|e| e.to_string())?.is_some() { break; }
        thread::sleep(Duration::from_millis(250));
    }
    if !ready.exists() {
        let _ = command_without_console("taskkill.exe").args(["/PID", &child.id().to_string(), "/T", "/F"]).status();
        let _ = child.wait();
        rollback(root, &dir, &changes)?;
        let _=fs::remove_file(dir.join("journal.json"));
        clear_pending(data);
        let _ = command_without_console(root.join("SHIYIN AI.exe")).current_dir(root).spawn();
        return Err("新版本未就绪，已回滚并重新启动旧版本".into());
    }
    fs::write(hot_update_state_path(data), serde_json::to_vec(&m).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
    fs::remove_file(dir.join("journal.json")).or_else(|e| if e.kind()==io::ErrorKind::NotFound {Ok(())}else{Err(e)}).map_err(|e| e.to_string())?;
    clear_pending(data);
    log(data, &format!("热更新 {} 完成，新程序已启动并确认就绪", m.version));
    emit_progress(app, 4, 100, "完成", "热更新成功，软件已自动重启", &m.version, false, true);
    thread::sleep(Duration::from_millis(900)); app.exit(0); Ok(())
}

pub(super) fn mark_ready(data: &Path) {
    if let Ok(version) = std::env::var("SHIYIN_HOT_READY_VERSION") {
        if version.len()==14 && version.bytes().all(|b| b.is_ascii_digit()) {
            let _ = fs::write(update_dir(data).join("hot").join(version).join("ready"), b"backend-and-window-ready");
        }
    }
}

pub(super) fn recover(root: &Path, data: &Path) -> Result<(), String> {
    let hot = update_dir(data).join("hot");
    if !hot.exists() { return Ok(()); }
    let applied = fs::read_to_string(hot_update_state_path(data)).ok()
        .and_then(|s| serde_json::from_str::<serde_json::Value>(&s).ok())
        .and_then(|v| v["version"].as_str().map(str::to_owned)).unwrap_or_default();
    for entry in fs::read_dir(hot).map_err(|e| e.to_string())? {
        let dir = entry.map_err(|e| e.to_string())?.path();
        let version = dir.file_name().and_then(OsStr::to_str).unwrap_or("");
        if version.len()!=14 || !version.bytes().all(|b| b.is_ascii_digit()) {continue;}
        if std::env::var("SHIYIN_HOT_READY_VERSION").as_deref()==Ok(version) {continue;}
        let journal=dir.join("journal.json");
        if journal.exists() {
            if applied != version {
                let changes:Vec<Change>=serde_json::from_slice(&fs::read(&journal).map_err(|e|e.to_string())?).map_err(|e|e.to_string())?;
                rollback(root,&dir,&changes)?;
                clear_pending(data);
                log(data,&format!("恢复中断的热更新 {version}，已回滚"));
            }
            fs::remove_file(journal).map_err(|e|e.to_string())?;
        }
    }
    Ok(())
}

pub(super) fn cli(args: &[String]) -> bool {
    let migration_exe=std::env::current_exe().ok().and_then(|p|p.file_stem().map(|s|s.to_string_lossy().to_string())).is_some_and(|s|s=="SHIYIN-Hot-Update");
    if args.iter().any(|s|s=="--migrate-client") || migration_exe {
        let result=(|| {
            let root=if let Some(path)=value(args,"--root=") {PathBuf::from(path)} else {
                rfd::FileDialog::new().set_title("选择 SHIYIN AI 安装目录（包含 SHIYIN AI.exe）")
                    .pick_folder().ok_or_else(||"已取消迁移".to_string())?
            };
            if !root.join("SHIYIN AI.exe").is_file(){return Err("所选目录没有 SHIYIN AI.exe".into());}
            let consent=MessageDialog::new().set_title("接入局域网热更新")
                .set_description("请先保存并退出 SHIYIN AI。此工具将下载已签名的应用更新，保留用户数据，安装完成后自动重启。继续迁移？")
                .set_buttons(MessageButtons::OkCancel).show();
            if consent != rfd::MessageDialogResult::Ok {return Ok(());}
            let data=root.join("data");let settings=load_settings(&data);
            let Some((m,raw,base))=check(&data,&settings)? else{return Err("暂无新热更新".into());};
            download(&root,&data,&m,&raw,&base)?;
            let pending=load_pending(&data).ok_or("无法读取已下载更新")?;
            launch_helper(&root,&data,&pending,std::process::id())?;
            Ok::<(),String>(())
        })();
        if let Err(e)=result{MessageDialog::new().set_title("热更新迁移").set_description(e).show();}
        return true;
    }
    if !args.iter().any(|s|s=="--prepare-hot-update") {return false;}
    let Some(root)=value(args,"--root=").map(PathBuf::from) else {return true;};
    let data=root.join("data");
    let result=(|| {
        let settings=load_settings(&data);
        let Some((m,raw,base))=check(&data,&settings)? else {return Err("没有新的热更新".into());};
        download(&root,&data,&m,&raw,&base)?;
        Ok::<_,String>(serde_json::json!({"ok":true,"version":m.version}))
    })().unwrap_or_else(|e|serde_json::json!({"ok":false,"error":e}));
    let _=fs::create_dir_all(update_dir(&data));
    let _=fs::write(update_dir(&data).join("hot-cli-result.json"),result.to_string());
    true
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn baseline_prevents_old_updates_on_fresh_or_existing_installs() {
        assert_eq!(effective_release("", "20260914180000"), "20260914180000");
        assert_eq!(effective_release("20260914154010", "20260914180000"), "20260914180000");
        assert_eq!(effective_release("20260915120000", "20260914180000"), "20260915120000");
        assert_eq!(effective_release("invalid", "20260914180000\n"), "20260914180000");
    }
    #[test] fn rejects_untrusted_and_escaping_updates() {
        assert!(relative("app/web/../config/x").is_err());
        assert!(relative("app/web/a:stream").is_err());
        assert!(relative("data/config/app.json").is_err());
        assert!(relative("SHIYIN AI.exe").is_ok());
        assert!(verify(r#"{"payload":"{}","public_key":"00","signature":"00"}"#).is_err());
    }
    #[test] fn applies_and_rolls_back_files_and_pruning() {
        let root=std::env::temp_dir().join(format!("shiyin-hot-test-{}",Uuid::new_v4()));
        let dir=root.join("data/update/hot/test");
        fs::create_dir_all(root.join("app/web")).unwrap();
        fs::create_dir_all(dir.join("files/app/web")).unwrap();
        fs::write(root.join("app/web/a.js"),b"old").unwrap();
        fs::write(root.join("app/web/obsolete.js"),b"old").unwrap();
        let staged=dir.join("files/app/web/a.js");fs::write(&staged,b"new").unwrap();
        let m=Manifest{protocol_version:2,version:"20260914180000".into(),min_desktop_version:"1.0.446".into(),notes:"".into(),prune_roots:vec!["app/web".into()],files:vec![HotUpdateFile{path:"app/web/a.js".into(),size:3,sha256:sha256(&staged).unwrap()}]};
        let changes=apply(&root,&dir,&m).unwrap();
        assert_eq!(fs::read(root.join("app/web/a.js")).unwrap(),b"new");
        assert!(!root.join("app/web/obsolete.js").exists());
        rollback(&root,&dir,&changes).unwrap();
        assert_eq!(fs::read(root.join("app/web/a.js")).unwrap(),b"old");
        assert!(root.join("app/web/obsolete.js").exists());
        fs::remove_dir_all(root).unwrap();
    }
    #[test] fn interrupted_transaction_recovers_before_start() {
        let root=std::env::temp_dir().join(format!("shiyin-recovery-{}",Uuid::new_v4()));
        let data=root.join("data");let dir=data.join("update/hot/20260914180001");
        fs::create_dir_all(root.join("app/web")).unwrap();
        fs::create_dir_all(dir.join("backup/app/web")).unwrap();
        fs::write(root.join("app/web/a.js"),b"partial").unwrap();
        fs::write(dir.join("backup/app/web/a.js"),b"old").unwrap();
        write_journal(&dir,&[Change{path:"app/web/a.js".into(),existed:true}]).unwrap();
        recover(&root,&data).unwrap();
        assert_eq!(fs::read(root.join("app/web/a.js")).unwrap(),b"old");
        assert!(!dir.join("journal.json").exists());
        fs::remove_dir_all(root).unwrap();
    }
}
