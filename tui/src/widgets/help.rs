use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::widgets::{Block, Borders, Clear, Paragraph};
use ratatui::text::{Line, Span};
use ratatui::style::{Style, Modifier};
use crate::theme::Theme;

pub struct HelpOverlay {
    pub visible: bool,
}

impl HelpOverlay {
    pub fn new() -> Self {
        Self { visible: false }
    }

    pub fn toggle(&mut self) {
        self.visible = !self.visible;
    }

    pub fn render(&self, frame: &mut Frame, area: Rect, view_name: &str, keybindings: &[(&str, &str)]) {
        if !self.visible { return; }

        let global_keys: &[(&str, &str)] = &[
            ("q", "Quit"),
            ("1-6", "Switch tab"),
            ("Tab", "Next tab"),
            ("/", "Command palette"),
            ("?", "Toggle help"),
        ];

        let total_items = keybindings.len() + global_keys.len() + 3; // +3 for headers and separator
        let panel_width: u16 = 35;
        let panel_height = (total_items as u16 + 2).min(area.height);

        // Position: right-aligned, top-aligned
        let x = area.width.saturating_sub(panel_width + 1);
        let panel_area = Rect::new(area.x + x, area.y + 1, panel_width, panel_height);

        // Clear background
        frame.render_widget(Clear, panel_area);

        // Build lines
        let mut lines = Vec::new();

        // View-specific header
        lines.push(Line::from(Span::styled(
            format!(" {} Keys", view_name),
            Style::default().fg(Theme::PRIMARY).add_modifier(Modifier::BOLD),
        )));

        for (key, desc) in keybindings {
            lines.push(Line::from(vec![
                Span::styled(format!("  {:>10}", key), Style::default().fg(Theme::WARNING)),
                Span::raw("  "),
                Span::styled(*desc, Style::default().fg(Theme::TEXT)),
            ]));
        }

        // Separator
        lines.push(Line::from(""));

        // Global header
        lines.push(Line::from(Span::styled(
            " Global Keys",
            Style::default().fg(Theme::PRIMARY).add_modifier(Modifier::BOLD),
        )));

        for (key, desc) in global_keys {
            lines.push(Line::from(vec![
                Span::styled(format!("  {:>10}", key), Style::default().fg(Theme::WARNING)),
                Span::raw("  "),
                Span::styled(*desc, Style::default().fg(Theme::TEXT)),
            ]));
        }

        let block = Block::default()
            .title(" Help ")
            .borders(Borders::ALL)
            .border_style(Theme::border());
        let paragraph = Paragraph::new(lines).block(block);
        frame.render_widget(paragraph, panel_area);
    }
}
