use ratatui::style::{Color, Modifier, Style};

pub struct Theme;

impl Theme {
    pub const PRIMARY: Color = Color::Rgb(168, 85, 247);    // #a855f7
    pub const SECONDARY: Color = Color::Rgb(107, 33, 168);  // #6b21a8
    pub const ACCENT: Color = Color::Rgb(76, 29, 149);      // #4c1d95
    pub const SUCCESS: Color = Color::Rgb(76, 175, 80);     // #4caf50
    pub const WARNING: Color = Color::Rgb(251, 191, 36);    // #fbbf24
    pub const ERROR: Color = Color::Rgb(239, 68, 68);       // #ef4444
    pub const TEXT: Color = Color::Rgb(226, 232, 240);      // #e2e8f0
    pub const DIM: Color = Color::Rgb(100, 116, 139);       // #64748b

    pub fn tab_active() -> Style {
        Style::default().fg(Theme::PRIMARY).add_modifier(Modifier::BOLD)
    }
    pub fn tab_inactive() -> Style {
        Style::default().fg(Theme::DIM)
    }
    pub fn status_healthy() -> Style {
        Style::default().fg(Theme::SUCCESS)
    }
    pub fn status_unhealthy() -> Style {
        Style::default().fg(Theme::ERROR)
    }
    pub fn header() -> Style {
        Style::default().fg(Theme::TEXT).bg(Theme::ACCENT)
    }
    pub fn border() -> Style {
        Style::default().fg(Theme::SECONDARY)
    }
}
