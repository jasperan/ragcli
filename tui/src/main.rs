mod app;
mod theme;

use anyhow::Result;

#[tokio::main]
async fn main() -> Result<()> {
    let terminal = ratatui::init();
    let result = app::App::new().run(terminal).await;
    ratatui::restore();
    result
}
