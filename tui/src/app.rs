use anyhow::Result;
use crossterm::event::{Event, EventStream, KeyCode, KeyEventKind};
use futures_util::StreamExt;
use ratatui::layout::{Constraint, Layout};
use ratatui::text::Line;
use ratatui::widgets::{Block, Borders, Paragraph, Tabs};
use ratatui::{DefaultTerminal, Frame};
use std::time::{Duration, Instant};
use strum::{Display, EnumIter, FromRepr, IntoEnumIterator};
use tokio::sync::mpsc;

use crate::api::client::ApiClient;
use crate::theme::Theme;
use crate::views::{
    agents::AgentsView, documents::DocumentsView, graph::GraphView, heatmap::HeatmapView,
    monitor::MonitorView, query::QueryView, View,
};
use crate::widgets::help::HelpOverlay;
use crate::widgets::palette::{CommandPalette, PaletteResult};

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

impl Tab {
    const COUNT: usize = 6;

    fn from_index(index: usize) -> Self {
        Self::from_repr(index).unwrap_or_default()
    }

    fn next(self) -> Self {
        Self::from_index((self as usize + 1) % Self::COUNT)
    }

    fn previous(self) -> Self {
        Self::from_index((self as usize + Self::COUNT - 1) % Self::COUNT)
    }
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
    QueryResult {
        request_id: u64,
        query: String,
        response: super::api::models::QueryResponse,
        elapsed_ms: u64,
    },
    QueryError {
        request_id: u64,
        message: String,
    },
    DocumentChunks {
        doc_id: String,
        response: super::api::models::ChunkListResponse,
    },
    DocumentDeleted(String),
    Latency(super::api::models::LatencyResponse),
    Error {
        target: &'static str,
        message: String,
    },
}

enum ViewAction {
    SubmitQuery {
        request_id: u64,
        query: String,
        session_id: Option<String>,
    },
    RefreshDocuments,
    LoadChunks(String),
    DeleteDocument(String),
    RefreshSystem,
}

pub struct App {
    pub active_tab: Tab,
    pub should_quit: bool,
    pub client: ApiClient,
    pub event_tx: Option<mpsc::UnboundedSender<AppEvent>>,
    pub views: Vec<Box<dyn View>>,
    pub palette: CommandPalette,
    pub help: HelpOverlay,
    pub last_status: String,
}

impl App {
    pub fn new(client: ApiClient) -> Self {
        Self {
            active_tab: Tab::Query,
            should_quit: false,
            client,
            event_tx: None,
            views: vec![
                Box::new(QueryView::new()),
                Box::new(HeatmapView::new()),
                Box::new(GraphView::new()),
                Box::new(AgentsView::new()),
                Box::new(DocumentsView::new()),
                Box::new(MonitorView::new()),
            ],
            palette: CommandPalette::new(),
            help: HelpOverlay::new(),
            last_status: "API connected".to_string(),
        }
    }

    pub async fn run(&mut self, mut terminal: DefaultTerminal) -> Result<()> {
        let (tx, mut rx) = mpsc::unbounded_channel::<AppEvent>();

        let tx_keys = tx.clone();
        tokio::spawn(async move {
            let mut stream = EventStream::new();
            while let Some(Ok(evt)) = stream.next().await {
                let app_evt = match evt {
                    Event::Key(k) if k.kind == KeyEventKind::Press => AppEvent::Key(k.code),
                    Event::Resize(w, h) => AppEvent::Resize(w, h),
                    _ => continue,
                };
                if tx_keys.send(app_evt).is_err() {
                    break;
                }
            }
        });

        let tx_tick = tx.clone();
        tokio::spawn(async move {
            let mut interval = tokio::time::interval(Duration::from_millis(33));
            loop {
                interval.tick().await;
                if tx_tick.send(AppEvent::Tick).is_err() {
                    break;
                }
            }
        });

        self.event_tx = Some(tx);
        self.dispatch_action(ViewAction::RefreshSystem);
        self.dispatch_action(ViewAction::RefreshDocuments);

        while !self.should_quit {
            terminal.draw(|frame| self.render(frame))?;
            if let Some(event) = rx.recv().await {
                match event {
                    AppEvent::Key(key) => self.handle_key(key),
                    AppEvent::Tick => {}
                    AppEvent::ApiResponse(msg) => self.handle_api_message(msg),
                    AppEvent::Resize(_, _) => {}
                }
            }
        }
        Ok(())
    }

    fn handle_key(&mut self, key: KeyCode) {
        let previous_tab = self.active_tab;

        if self.palette.visible {
            if let Some(result) = self.palette.handle_key(key) {
                match result {
                    PaletteResult::SwitchTab(idx) => self.active_tab = Tab::from_index(idx),
                    PaletteResult::Action(label) => {
                        if label == "Refresh Data" {
                            self.dispatch_action(ViewAction::RefreshSystem);
                            self.dispatch_action(ViewAction::RefreshDocuments);
                        }
                    }
                    PaletteResult::Close => {}
                }
            }
            if self.active_tab != previous_tab {
                self.refresh_for_active_tab();
            }
            return;
        }

        match key {
            KeyCode::Char('q') => self.should_quit = true,
            KeyCode::Char('/') => self.palette.toggle(),
            KeyCode::Char('?') => self.help.toggle(),
            KeyCode::Char('1') => self.active_tab = Tab::Query,
            KeyCode::Char('2') => self.active_tab = Tab::Heatmap,
            KeyCode::Char('3') => self.active_tab = Tab::Graph,
            KeyCode::Char('4') => self.active_tab = Tab::Agents,
            KeyCode::Char('5') => self.active_tab = Tab::Documents,
            KeyCode::Char('6') => self.active_tab = Tab::Monitor,
            KeyCode::Tab => self.active_tab = self.active_tab.next(),
            KeyCode::BackTab => self.active_tab = self.active_tab.previous(),
            _ => {
                self.views[self.active_tab as usize].handle_key(key);
            }
        }

        if self.active_tab != previous_tab {
            self.refresh_for_active_tab();
        }

        if let Some(action) = self.take_active_action() {
            self.dispatch_action(action);
        }
    }

    fn refresh_for_active_tab(&mut self) {
        match self.active_tab {
            Tab::Documents => self.dispatch_action(ViewAction::RefreshDocuments),
            Tab::Monitor => self.dispatch_action(ViewAction::RefreshSystem),
            _ => {}
        }
    }

    fn take_active_action(&mut self) -> Option<ViewAction> {
        match self.active_tab {
            Tab::Query => {
                self.query_view_mut()
                    .take_pending_query()
                    .map(|(request_id, query, session_id)| ViewAction::SubmitQuery {
                        request_id,
                        query,
                        session_id,
                    })
            }
            Tab::Documents => {
                let view = self.documents_view_mut();
                if view.take_refresh_request() {
                    Some(ViewAction::RefreshDocuments)
                } else if let Some(doc_id) = view.take_chunk_load_request() {
                    Some(ViewAction::LoadChunks(doc_id))
                } else {
                    view.take_delete_request().map(ViewAction::DeleteDocument)
                }
            }
            Tab::Monitor => {
                if self.monitor_view_mut().take_refresh_request() {
                    Some(ViewAction::RefreshSystem)
                } else {
                    None
                }
            }
            _ => None,
        }
    }

    fn dispatch_action(&mut self, action: ViewAction) {
        let Some(tx) = self.event_tx.clone() else {
            return;
        };
        let client = self.client.clone();

        match action {
            ViewAction::SubmitQuery {
                request_id,
                query,
                session_id,
            } => {
                self.last_status = "Running query".to_string();
                tokio::spawn(async move {
                    let started = Instant::now();
                    let result = client.query(&query, session_id.as_deref(), 5, true).await;
                    let message = match result {
                        Ok(response) => ApiMessage::QueryResult {
                            request_id,
                            query,
                            response,
                            elapsed_ms: started.elapsed().as_millis() as u64,
                        },
                        Err(err) => ApiMessage::QueryError {
                            request_id,
                            message: err.to_string(),
                        },
                    };
                    let _ = tx.send(AppEvent::ApiResponse(message));
                });
            }
            ViewAction::RefreshDocuments => {
                self.last_status = "Refreshing documents".to_string();
                tokio::spawn(async move {
                    let message = match client.documents(100, 0).await {
                        Ok(response) => ApiMessage::Documents(response),
                        Err(err) => ApiMessage::Error {
                            target: "documents",
                            message: err.to_string(),
                        },
                    };
                    let _ = tx.send(AppEvent::ApiResponse(message));
                });
            }
            ViewAction::LoadChunks(doc_id) => {
                self.last_status = "Loading chunks".to_string();
                tokio::spawn(async move {
                    let message = match client.document_chunks(&doc_id, 100, 0).await {
                        Ok(response) => ApiMessage::DocumentChunks { doc_id, response },
                        Err(err) => ApiMessage::Error {
                            target: "documents",
                            message: err.to_string(),
                        },
                    };
                    let _ = tx.send(AppEvent::ApiResponse(message));
                });
            }
            ViewAction::DeleteDocument(doc_id) => {
                self.last_status = "Deleting document".to_string();
                tokio::spawn(async move {
                    let message = match client.delete_document(&doc_id).await {
                        Ok(()) => ApiMessage::DocumentDeleted(doc_id),
                        Err(err) => ApiMessage::Error {
                            target: "documents",
                            message: err.to_string(),
                        },
                    };
                    let _ = tx.send(AppEvent::ApiResponse(message));
                });
            }
            ViewAction::RefreshSystem => {
                self.last_status = "Refreshing system status".to_string();
                self.dispatch_system_refresh(client, tx);
            }
        }
    }

    fn dispatch_system_refresh(&self, client: ApiClient, tx: mpsc::UnboundedSender<AppEvent>) {
        let health_client = client.clone();
        let health_tx = tx.clone();
        tokio::spawn(async move {
            let message = match health_client.health().await {
                Ok(response) => ApiMessage::Health(response),
                Err(err) => ApiMessage::Error {
                    target: "system",
                    message: err.to_string(),
                },
            };
            let _ = health_tx.send(AppEvent::ApiResponse(message));
        });

        let stats_client = client.clone();
        let stats_tx = tx.clone();
        tokio::spawn(async move {
            let message = match stats_client.stats().await {
                Ok(response) => ApiMessage::Stats(response),
                Err(err) => ApiMessage::Error {
                    target: "system",
                    message: err.to_string(),
                },
            };
            let _ = stats_tx.send(AppEvent::ApiResponse(message));
        });

        let models_client = client.clone();
        let models_tx = tx.clone();
        tokio::spawn(async move {
            let message = match models_client.models().await {
                Ok(response) => ApiMessage::Models(response),
                Err(err) => ApiMessage::Error {
                    target: "system",
                    message: err.to_string(),
                },
            };
            let _ = models_tx.send(AppEvent::ApiResponse(message));
        });

        tokio::spawn(async move {
            let message = match client.latency_stats(50).await {
                Ok(response) => ApiMessage::Latency(response),
                Err(err) => ApiMessage::Error {
                    target: "system",
                    message: err.to_string(),
                },
            };
            let _ = tx.send(AppEvent::ApiResponse(message));
        });
    }

    fn handle_api_message(&mut self, msg: ApiMessage) {
        match msg {
            ApiMessage::Health(response) => {
                self.monitor_view_mut().set_health(response);
                self.last_status = "System status updated".to_string();
            }
            ApiMessage::Stats(response) => {
                self.monitor_view_mut().set_stats(response);
            }
            ApiMessage::Documents(response) => {
                self.documents_view_mut()
                    .set_documents(response.documents, response.total_count);
                self.last_status = "Documents updated".to_string();
            }
            ApiMessage::Models(response) => {
                self.monitor_view_mut().set_models(response);
            }
            ApiMessage::QueryResult {
                request_id,
                query,
                response,
                elapsed_ms,
            } => {
                if self
                    .query_view_mut()
                    .set_query_result(request_id, query, response, elapsed_ms)
                {
                    self.last_status = "Query complete".to_string();
                }
            }
            ApiMessage::QueryError {
                request_id,
                message,
            } => {
                if self
                    .query_view_mut()
                    .set_query_error(request_id, message.clone())
                {
                    self.last_status = format!("query error: {}", message);
                }
            }
            ApiMessage::DocumentChunks { doc_id, response } => {
                if self
                    .documents_view_mut()
                    .set_chunks(&doc_id, response.chunks)
                {
                    self.last_status = "Chunks loaded".to_string();
                }
            }
            ApiMessage::DocumentDeleted(doc_id) => {
                self.documents_view_mut().remove_document(&doc_id);
                self.last_status = "Document deleted".to_string();
            }
            ApiMessage::Latency(response) => {
                self.monitor_view_mut().set_latency(response);
            }
            ApiMessage::Error { target, message } => {
                match target {
                    "query" => self.query_view_mut().set_error(message.clone()),
                    "documents" => self.documents_view_mut().set_error(message.clone()),
                    "system" => self.monitor_view_mut().set_error(message.clone()),
                    _ => {}
                }
                self.last_status = format!("{} error: {}", target, message);
            }
        }
    }

    fn query_view_mut(&mut self) -> &mut QueryView {
        self.views[Tab::Query as usize]
            .as_any_mut()
            .downcast_mut::<QueryView>()
            .expect("query view type")
    }

    fn documents_view_mut(&mut self) -> &mut DocumentsView {
        self.views[Tab::Documents as usize]
            .as_any_mut()
            .downcast_mut::<DocumentsView>()
            .expect("documents view type")
    }

    fn monitor_view_mut(&mut self) -> &mut MonitorView {
        self.views[Tab::Monitor as usize]
            .as_any_mut()
            .downcast_mut::<MonitorView>()
            .expect("monitor view type")
    }

    fn render(&mut self, frame: &mut Frame) {
        let [tab_area, view_area, status_area] = Layout::vertical([
            Constraint::Length(3),
            Constraint::Fill(1),
            Constraint::Length(1),
        ])
        .areas(frame.area());

        let tab_titles: Vec<String> = Tab::iter().map(|t| t.to_string()).collect();
        let tabs = Tabs::new(tab_titles)
            .select(self.active_tab as usize)
            .highlight_style(Theme::tab_active())
            .style(Theme::tab_inactive())
            .divider(" | ")
            .block(
                Block::default()
                    .borders(Borders::BOTTOM)
                    .border_style(Theme::border()),
            );
        frame.render_widget(tabs, tab_area);

        self.views[self.active_tab as usize].render(frame, view_area);

        let status = Line::from(vec![format!(
            " {}  [q]uit [1-6]tab [/]palette [?]help",
            self.last_status
        )
        .into()])
        .style(Theme::header());
        frame.render_widget(Paragraph::new(status), status_area);

        if self.palette.visible {
            self.palette.render(frame, frame.area());
        }

        if self.help.visible {
            let kb = self.views[self.active_tab as usize].keybindings();
            let view_name = self.views[self.active_tab as usize].name().to_string();
            let kb_refs: Vec<(&str, &str)> = kb.iter().map(|(k, v)| (*k, *v)).collect();
            self.help.render(frame, frame.area(), &view_name, &kb_refs);
        }
    }
}
