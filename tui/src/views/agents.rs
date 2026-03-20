use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::widgets::{Block, Borders, Paragraph};
use crossterm::event::KeyCode;
use crate::theme::Theme;
use super::View;

pub struct AgentsView {
    // state will be added in Phase 3
}

impl AgentsView {
    pub fn new() -> Self {
        Self {}
    }
}

impl View for AgentsView {
    fn render(&self, frame: &mut Frame, area: Rect) {
        let block = Block::default()
            .title(" Agent Trace ")
            .borders(Borders::ALL)
            .border_style(Theme::border());
        let content = Paragraph::new("Run a query with tracing to see agent activity...")
            .block(block);
        frame.render_widget(content, area);
    }

    fn handle_key(&mut self, _key: KeyCode) {}

    fn name(&self) -> &str { "Agents" }
}
