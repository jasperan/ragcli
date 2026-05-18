use crate::api::client::ApiClient;
use anyhow::{bail, Result};
use std::path::PathBuf;
use std::process::Stdio;
use tokio::process::{Child, Command};

pub struct ServerProcess {
    child: Child,
    pub port: u16,
}

impl ServerProcess {
    pub async fn spawn(project_root: Option<PathBuf>, port: u16) -> Result<Self> {
        let mut command = if let Some(root) = project_root {
            let ragcli_py = root.join("ragcli.py");
            if !ragcli_py.exists() {
                bail!("ragcli.py not found at {}", ragcli_py.display());
            }
            let python = std::env::var("RAGCLI_PYTHON").unwrap_or_else(|_| "python3".to_string());
            let mut cmd = Command::new(python);
            cmd.args(["ragcli.py", "api", "--port", &port.to_string()])
                .current_dir(root);
            cmd
        } else {
            let ragcli = std::env::var("RAGCLI_COMMAND").unwrap_or_else(|_| "ragcli".to_string());
            let mut cmd = Command::new(ragcli);
            cmd.args(["api", "--port", &port.to_string()]);
            cmd
        };

        let child = command
            .stdout(Stdio::null())
            .stderr(Stdio::piped())
            .kill_on_drop(true)
            .spawn()?;

        Ok(Self { child, port })
    }

    pub async fn wait_healthy(client: &ApiClient, timeout_secs: u64) -> Result<()> {
        let deadline = tokio::time::Instant::now() + tokio::time::Duration::from_secs(timeout_secs);

        while tokio::time::Instant::now() < deadline {
            if client.health().await.is_ok() {
                return Ok(());
            }
            tokio::time::sleep(tokio::time::Duration::from_millis(500)).await;
        }
        bail!(
            "API server at {} did not become healthy within {}s",
            client.base_url(),
            timeout_secs
        )
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

pub fn find_project_root() -> Option<PathBuf> {
    // Check RAGCLI_ROOT env var first
    if let Ok(root) = std::env::var("RAGCLI_ROOT") {
        let path = PathBuf::from(root);
        if path.join("ragcli.py").exists() {
            return Some(path);
        }
    }

    // Check relative to binary location
    if let Ok(exe) = std::env::current_exe() {
        for ancestor in exe.ancestors().skip(1) {
            if ancestor.join("ragcli.py").exists() {
                return Some(ancestor.to_path_buf());
            }
        }
    }

    // Check current directory and parents
    if let Ok(cwd) = std::env::current_dir() {
        for ancestor in cwd.ancestors() {
            if ancestor.join("ragcli.py").exists() {
                return Some(ancestor.to_path_buf());
            }
        }
    }

    None
}
