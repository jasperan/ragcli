use anyhow::Result;
use crossterm::event::{Event, KeyCode, KeyEventKind, EventStream};
use futures_util::StreamExt;
use ratatui::{DefaultTerminal, Frame};
use ratatui::layout::{Constraint, Layout};
use ratatui::widgets::{Block, Borders, Paragraph, Tabs};
use ratatui::text::Line;
use strum::{Display, EnumIter, FromRepr, IntoEnumIterator};
use tokio::sync::mpsc;
use std::time::Duration;
use crate::api::client::ApiClient;
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

pub enum AppEvent {
    Key(KeyCode),
    Tick,
    ApiResponse(ApiMessage),
    Resize(u16, u16),
}

#[derive(Debug)]
pub enum ApiMessage {
    Health(super::api::models::SystemStatus),
    Stats(super::api::models::SystemStats),
    Documents(super::api::models::DocumentListResponse),
    Models(super::api::models::ModelsResponse),
    QueryResult(super::api::models::QueryResponse),
    Error(String),
}

pub struct App {
    pub active_tab: Tab,
    pub should_quit: bool,
    pub client: ApiClient,
    pub event_tx: Option<mpsc::UnboundedSender<AppEvent>>,
}

impl App {
    pub fn new(client: ApiClient) -> Self {
        Self {
            active_tab: Tab::Query,
            should_quit: false,
            client,
            event_tx: None,
        }
    }

    pub async fn run(&mut self, mut terminal: DefaultTerminal) -> Result<()> {
        let (tx, mut rx) = mpsc::unbounded_channel::<AppEvent>();

        // Terminal event reader task
        let tx_keys = tx.clone();
        tokio::spawn(async move {
            let mut stream = EventStream::new();
            while let Some(Ok(evt)) = stream.next().await {
                let app_evt = match evt {
                    Event::Key(k) if k.kind == KeyEventKind::Press => {
                        AppEvent::Key(k.code)
                    }
                    Event::Resize(w, h) => AppEvent::Resize(w, h),
                    _ => continue,
                };
                if tx_keys.send(app_evt).is_err() { break; }
            }
        });

        // Tick timer task (60fps render)
        let tx_tick = tx.clone();
        tokio::spawn(async move {
            let mut interval = tokio::time::interval(Duration::from_millis(16));
            loop {
                interval.tick().await;
                if tx_tick.send(AppEvent::Tick).is_err() { break; }
            }
        });

        // Store sender for API tasks to use later
        self.event_tx = Some(tx);

        // Main loop
        while !self.should_quit {
            terminal.draw(|frame| self.render(frame))?;
            if let Some(event) = rx.recv().await {
                match event {
                    AppEvent::Key(key) => self.handle_key(key),
                    AppEvent::Tick => { /* views will use this for animations/refreshes */ }
                    AppEvent::ApiResponse(msg) => self.handle_api_message(msg),
                    AppEvent::Resize(_, _) => { /* ratatui handles resize automatically */ }
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

    fn handle_api_message(&mut self, msg: ApiMessage) {
        // Will be filled per-view in later tasks
        match msg {
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
