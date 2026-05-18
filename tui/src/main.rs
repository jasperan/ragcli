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

    let api_url = std::env::var("RAGCLI_API_URL").ok();
    let client = match api_url {
        Some(url) => ApiClient::from_base_url(url),
        None => ApiClient::new(port),
    };

    let _server = if std::env::var("RAGCLI_API_URL").is_ok() {
        eprintln!(
            "Connecting to existing ragcli API at {}...",
            client.base_url()
        );
        None
    } else {
        let project_root = server::find_project_root();
        eprintln!("Starting ragcli API server on port {}...", port);
        Some(server::ServerProcess::spawn(project_root, port).await?)
    };

    // Wait for API to be ready
    server::ServerProcess::wait_healthy(&client, 15).await?;

    let terminal = ratatui::init();
    let result = app::App::new(client).run(terminal).await;
    ratatui::restore();
    result
}
