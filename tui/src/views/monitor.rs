use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::widgets::{Block, Borders, Paragraph};
use crossterm::event::KeyCode;
use crate::theme::Theme;
use super::View;

pub struct MonitorView {
    // state will be added in Phase 3
}

impl MonitorView {
    pub fn new() -> Self {
        Self {}
    }
}

impl View for MonitorView {
    fn render(&self, frame: &mut Frame, area: Rect) {
        let block = Block::default()
            .title(" System Monitor ")
            .borders(Borders::ALL)
            .border_style(Theme::border());
        let content = Paragraph::new("Connecting to services...")
            .block(block);
        frame.render_widget(content, area);
    }

    fn handle_key(&mut self, _key: KeyCode) {}

    fn name(&self) -> &str { "Monitor" }
}
