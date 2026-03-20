use anyhow::Result;
use crossterm::event::{self, Event, KeyCode, KeyEventKind};
use ratatui::{DefaultTerminal, Frame};
use ratatui::layout::{Constraint, Layout};
use ratatui::widgets::{Block, Borders, Paragraph, Tabs};
use ratatui::text::Line;
use strum::{Display, EnumIter, FromRepr, IntoEnumIterator};
use crate::theme::Theme;

#[derive(Default, Clone, Copy, Display, EnumIter, FromRepr, PartialEq)]
pub enum Tab {
    #[default]
    #[strum(to_string = "Query")]
    Query,
    #[strum(to_string = "Heatmap")]
    Heatmap,
    #[strum(to_string = "Graph")]
    Graph,
    #[strum(to_string = "Agents")]
    Agents,
    #[strum(to_string = "Docs")]
    Documents,
    #[strum(to_string = "System")]
    Monitor,
}

pub struct App {
    pub active_tab: Tab,
    pub should_quit: bool,
}

impl App {
    pub fn new() -> Self {
        Self {
            active_tab: Tab::Query,
            should_quit: false,
        }
    }

    pub async fn run(&mut self, mut terminal: DefaultTerminal) -> Result<()> {
        while !self.should_quit {
            terminal.draw(|frame| self.render(frame))?;
            if event::poll(std::time::Duration::from_millis(16))? {
                if let Event::Key(key) = event::read()? {
                    if key.kind == KeyEventKind::Press {
                        self.handle_key(key.code);
                    }
                }
            }
        }
        Ok(())
    }

    fn handle_key(&mut self, key: KeyCode) {
        match key {
            KeyCode::Char('q') => self.should_quit = true,
            KeyCode::Char('1') => self.active_tab = Tab::Query,
            KeyCode::Char('2') => self.active_tab = Tab::Heatmap,
            KeyCode::Char('3') => self.active_tab = Tab::Graph,
            KeyCode::Char('4') => self.active_tab = Tab::Agents,
            KeyCode::Char('5') => self.active_tab = Tab::Documents,
            KeyCode::Char('6') => self.active_tab = Tab::Monitor,
            KeyCode::Tab => {
                let idx = self.active_tab as usize;
                self.active_tab = Tab::from_repr((idx + 1) % 6).unwrap_or(Tab::Query);
            }
            KeyCode::BackTab => {
                let idx = self.active_tab as usize;
                self.active_tab = Tab::from_repr((idx + 5) % 6).unwrap_or(Tab::Query);
            }
            _ => {}
        }
    }

    fn render(&self, frame: &mut Frame) {
        let [tab_area, view_area, status_area] = Layout::vertical([
            Constraint::Length(3),
            Constraint::Fill(1),
            Constraint::Length(1),
        ]).areas(frame.area());

        // Tab bar
        let tab_titles: Vec<String> = Tab::iter().map(|t| t.to_string()).collect();
        let tabs = Tabs::new(tab_titles)
            .select(self.active_tab as usize)
            .highlight_style(Theme::tab_active())
            .style(Theme::tab_inactive())
            .divider(" │ ")
            .block(Block::default().borders(Borders::BOTTOM).border_style(Theme::border()));
        frame.render_widget(tabs, tab_area);

        // Placeholder view
        let placeholder = Paragraph::new(format!("{} view", self.active_tab))
            .block(Block::default().borders(Borders::ALL).border_style(Theme::border()));
        frame.render_widget(placeholder, view_area);

        // Status bar
        let status = Line::from(vec![
            " [q]uit  [1-6]tab  [/]search  [?]help".into(),
        ]).style(Theme::header());
        frame.render_widget(Paragraph::new(status), status_area);
    }
}
