use anyhow::{Result, bail};
use std::path::PathBuf;
use tokio::process::{Child, Command};
use std::process::Stdio;
use crate::api::client::ApiClient;

pub struct ServerProcess {
    child: Child,
    pub port: u16,
}

impl ServerProcess {
    pub async fn spawn(project_root: PathBuf, port: u16) -> Result<Self> {
        let ragcli_py = project_root.join("ragcli.py");
        if !ragcli_py.exists() {
            bail!("ragcli.py not found at {}", ragcli_py.display());
        }

        let child = Command::new("python")
            .args(["ragcli.py", "api", "--port", &port.to_string()])
            .current_dir(&project_root)
            .stdout(Stdio::null())
            .stderr(Stdio::piped())
            .kill_on_drop(true)
            .spawn()?;

        Ok(Self { child, port })
    }

    pub async fn wait_healthy(port: u16, timeout_secs: u64) -> Result<()> {
        let client = ApiClient::new(port);
        let deadline = tokio::time::Instant::now() + tokio::time::Duration::from_secs(timeout_secs);

        while tokio::time::Instant::now() < deadline {
            if client.health().await.is_ok() {
                return Ok(());
            }
            tokio::time::sleep(tokio::time::Duration::from_millis(500)).await;
        }
        bail!("API server did not become healthy within {}s", timeout_secs)
    }

    pub fn kill(&mut self) {
        let _ = self.child.start_kill();
    }
}

impl Drop for ServerProcess {
    fn drop(&mut self) {
        self.kill();
    }
}

pub fn find_project_root() -> Result<PathBuf> {
    // Check RAGCLI_ROOT env var first
    if let Ok(root) = std::env::var("RAGCLI_ROOT") {
        let path = PathBuf::from(root);
        if path.join("ragcli.py").exists() {
            return Ok(path);
        }
    }

    // Check relative to binary location
    if let Ok(exe) = std::env::current_exe() {
        for ancestor in exe.ancestors().skip(1) {
            if ancestor.join("ragcli.py").exists() {
                return Ok(ancestor.to_path_buf());
            }
        }
    }

    // Check current directory and parents
    let cwd = std::env::current_dir()?;
    for ancestor in cwd.ancestors() {
        if ancestor.join("ragcli.py").exists() {
            return Ok(ancestor.to_path_buf());
        }
    }

    bail!("Could not find ragcli project root. Set RAGCLI_ROOT env var.")
}
