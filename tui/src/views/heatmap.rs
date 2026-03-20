use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::widgets::{Block, Borders, Paragraph};
use crossterm::event::KeyCode;
use crate::theme::Theme;
use super::View;

pub struct HeatmapView {
    // state will be added in Phase 3
}

impl HeatmapView {
    pub fn new() -> Self {
        Self {}
    }
}

impl View for HeatmapView {
    fn render(&self, frame: &mut Frame, area: Rect) {
        let block = Block::default()
            .title(" Vector Heatmap ")
            .borders(Borders::ALL)
            .border_style(Theme::border());
        let content = Paragraph::new("Run a query first to visualize embeddings...")
            .block(block);
        frame.render_widget(content, area);
    }

    fn handle_key(&mut self, _key: KeyCode) {}

    fn name(&self) -> &str { "Heatmap" }
}
