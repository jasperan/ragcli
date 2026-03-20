mod api;
mod app;
mod server;
mod theme;
mod views;
mod widgets;

use anyhow::Result;
use api::client::ApiClient;

#[tokio::main]
async fn main() -> Result<()> {
    let port: u16 = std::env::var("RAGCLI_PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(8000);

    let project_root = server::find_project_root()?;

    // Spawn the FastAPI server
    let _server = server::ServerProcess::spawn(project_root, port).await?;

    // Wait for API to be ready
    eprintln!("Starting API server on port {}...", port);
    server::ServerProcess::wait_healthy(port, 15).await?;

    let client = ApiClient::new(port);
    let terminal = ratatui::init();
    let result = app::App::new(client).run(terminal).await;
    ratatui::restore();
    result
}
