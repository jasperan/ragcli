pub mod agents;
pub mod documents;
pub mod graph;
pub mod heatmap;
pub mod monitor;
pub mod query;
pub mod text;

use crossterm::event::KeyCode;
use ratatui::layout::Rect;
use ratatui::Frame;
use std::any::Any;

pub trait View {
    fn render(&self, frame: &mut Frame, area: Rect);
    fn handle_key(&mut self, key: KeyCode);
    fn name(&self) -> &str;
    fn as_any_mut(&mut self) -> &mut dyn Any;
    fn keybindings(&self) -> Vec<(&'static str, &'static str)> {
        vec![]
    }
}
