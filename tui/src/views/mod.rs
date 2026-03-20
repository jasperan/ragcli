pub mod query;
pub mod heatmap;
pub mod graph;
pub mod agents;
pub mod documents;
pub mod monitor;

use crossterm::event::KeyCode;
use ratatui::Frame;
use ratatui::layout::Rect;

pub trait View {
    fn render(&self, frame: &mut Frame, area: Rect);
    fn handle_key(&mut self, key: KeyCode);
    fn name(&self) -> &str;
}
