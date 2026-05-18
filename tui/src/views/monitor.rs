use super::View;
use crate::api::models::{LatencyResponse, ModelsResponse, SystemStats, SystemStatus};
use crate::theme::Theme;
use crossterm::event::KeyCode;
use ratatui::layout::{Constraint, Direction, Layout, Rect};
use ratatui::style::{Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, Gauge, Paragraph, Sparkline};
use ratatui::Frame;

pub struct MonitorView {
    pub health: Option<SystemStatus>,
    pub stats: Option<SystemStats>,
    pub models: Option<ModelsResponse>,
    pub latency_history: Vec<u64>,
    pub cpu_percent: f64,
    pub mem_percent: f64,
    pub refresh_requested: bool,
    pub loading: bool,
    pub error: Option<String>,
}

impl MonitorView {
    pub fn new() -> Self {
        Self {
            health: None,
            stats: None,
            models: None,
            latency_history: Vec::new(),
            cpu_percent: 0.0,
            mem_percent: 0.0,
            refresh_requested: true,
            loading: true,
            error: None,
        }
    }

    pub fn take_refresh_request(&mut self) -> bool {
        std::mem::take(&mut self.refresh_requested)
    }

    pub fn set_health(&mut self, health: SystemStatus) {
        self.health = Some(health);
        self.loading = false;
        self.error = None;
    }

    pub fn set_stats(&mut self, stats: SystemStats) {
        self.stats = Some(stats);
        self.loading = false;
    }

    pub fn set_models(&mut self, models: ModelsResponse) {
        self.models = Some(models);
        self.loading = false;
    }

    pub fn set_latency(&mut self, latency: LatencyResponse) {
        self.latency_history = latency
            .data_points
            .iter()
            .rev()
            .map(|point| point.total_time_ms.max(0.0) as u64)
            .collect();
        self.loading = false;
    }

    pub fn set_error(&mut self, message: String) {
        self.error = Some(message);
        self.loading = false;
    }

    fn component_ok(status: &str) -> bool {
        matches!(status, "connected" | "ok" | "healthy")
    }

    fn render_service_card(
        frame: &mut Frame,
        area: Rect,
        title: &str,
        label: &str,
        healthy: bool,
        detail: String,
    ) {
        let dot = if healthy { "● " } else { "○ " };
        let dot_style = if healthy {
            Style::default().fg(Theme::SUCCESS)
        } else {
            Style::default().fg(Theme::ERROR)
        };
        let lines = vec![
            Line::from(vec![
                Span::styled(dot, dot_style),
                Span::styled(
                    label,
                    Style::default()
                        .fg(Theme::TEXT)
                        .add_modifier(Modifier::BOLD),
                ),
            ]),
            Line::from(Span::styled(detail, Style::default().fg(Theme::DIM))),
        ];
        let block = Block::default()
            .title(title)
            .borders(Borders::ALL)
            .border_style(Theme::border());

        frame.render_widget(Paragraph::new(lines).block(block), area);
    }

    fn render_service_cards(&self, frame: &mut Frame, area: Rect) {
        let direction = if area.width < 80 {
            Direction::Vertical
        } else {
            Direction::Horizontal
        };
        let chunks = Layout::default()
            .direction(direction)
            .constraints(match direction {
                Direction::Vertical => [
                    Constraint::Length(3),
                    Constraint::Length(3),
                    Constraint::Length(3),
                ],
                Direction::Horizontal => [
                    Constraint::Percentage(33),
                    Constraint::Percentage(34),
                    Constraint::Percentage(33),
                ],
            })
            .split(area);

        let api_healthy = self.health.as_ref().map(|h| h.healthy).unwrap_or(false);
        let api_detail = if let Some(error) = &self.error {
            format!("Error: {}", error)
        } else if self.loading {
            "Loading...".to_string()
        } else {
            match &self.stats {
                Some(s) => format!("{} docs", s.total_documents),
                None => "Connecting...".to_string(),
            }
        };
        Self::render_service_card(
            frame,
            chunks[0],
            " API ",
            "API Server",
            api_healthy,
            api_detail,
        );

        let db_healthy = self
            .health
            .as_ref()
            .map(|h| Self::component_ok(&h.database.status))
            .unwrap_or(false);
        let db_detail = if let Some(health) = &self.health {
            if db_healthy {
                match &self.stats {
                    Some(s) => {
                        format!("{} vectors, dim={}", s.total_vectors, s.embedding_dimension)
                    }
                    None => health.database.message.clone(),
                }
            } else {
                health.database.message.clone()
            }
        } else {
            "Connecting...".to_string()
        };
        Self::render_service_card(
            frame,
            chunks[1],
            " Oracle DB ",
            "Oracle DB",
            db_healthy,
            db_detail,
        );

        let ollama_healthy = self
            .health
            .as_ref()
            .map(|h| Self::component_ok(&h.ollama.status))
            .unwrap_or(false);
        let ollama_detail = if let Some(health) = &self.health {
            if ollama_healthy {
                match &self.models {
                    Some(m) => format!("{} models", m.chat_models.len() + m.embedding_models.len()),
                    None => health.ollama.message.clone(),
                }
            } else {
                health.ollama.message.clone()
            }
        } else {
            "Connecting...".to_string()
        };
        Self::render_service_card(
            frame,
            chunks[2],
            " Ollama ",
            "Ollama",
            ollama_healthy,
            ollama_detail,
        );
    }

    fn render_sparkline(&self, frame: &mut Frame, area: Rect) {
        let block = Block::default()
            .title(" Query Latency (last 50) ")
            .borders(Borders::ALL)
            .border_style(Theme::border());

        let sparkline = Sparkline::default()
            .block(block)
            .data(&self.latency_history)
            .style(Style::default().fg(Theme::PRIMARY));

        frame.render_widget(sparkline, area);
    }

    fn render_models(&self, frame: &mut Frame, area: Rect) {
        let block = Block::default()
            .title(" Models ")
            .borders(Borders::ALL)
            .border_style(Theme::border());

        let lines: Vec<Line> = match &self.models {
            None => vec![Line::from(Span::styled(
                "...",
                Style::default().fg(Theme::DIM),
            ))],
            Some(m) => {
                let mut rows: Vec<Line> = Vec::new();
                for model in &m.chat_models {
                    let is_current = model.name == m.current_chat_model;
                    let prefix = if is_current { "▶ " } else { "  " };
                    rows.push(Line::from(vec![
                        Span::styled(prefix, Style::default().fg(Theme::PRIMARY)),
                        Span::styled(model.name.clone(), Style::default().fg(Theme::TEXT)),
                        Span::styled(" (chat)", Style::default().fg(Theme::DIM)),
                    ]));
                }
                for model in &m.embedding_models {
                    let is_current = model.name == m.current_embedding_model;
                    let prefix = if is_current { "▶ " } else { "  " };
                    rows.push(Line::from(vec![
                        Span::styled(prefix, Style::default().fg(Theme::WARNING)),
                        Span::styled(model.name.clone(), Style::default().fg(Theme::TEXT)),
                        Span::styled(" (embed)", Style::default().fg(Theme::DIM)),
                    ]));
                }
                if rows.is_empty() {
                    rows.push(Line::from(Span::styled(
                        "No models found",
                        Style::default().fg(Theme::DIM),
                    )));
                }
                rows
            }
        };

        frame.render_widget(Paragraph::new(lines).block(block), area);
    }

    fn render_resources(&self, frame: &mut Frame, area: Rect) {
        let block = Block::default()
            .title(" Resources ")
            .borders(Borders::ALL)
            .border_style(Theme::border());

        let inner = block.inner(area);
        frame.render_widget(block, area);

        let rows = Layout::default()
            .direction(Direction::Vertical)
            .constraints([
                Constraint::Length(2),
                Constraint::Length(1),
                Constraint::Length(2),
                Constraint::Min(0),
            ])
            .split(inner);

        // CPU gauge
        let cpu_pct = self.cpu_percent.clamp(0.0, 100.0) as u16;
        let cpu_label = format!("CPU  {:>3}%", cpu_pct);
        let cpu_gauge = Gauge::default()
            .block(Block::default())
            .gauge_style(Style::default().fg(Theme::PRIMARY).bg(Theme::ACCENT))
            .percent(cpu_pct)
            .label(cpu_label);
        frame.render_widget(cpu_gauge, rows[0]);

        // RAM gauge
        let mem_pct = self.mem_percent.clamp(0.0, 100.0) as u16;
        let mem_label = format!("RAM  {:>3}%", mem_pct);
        let mem_gauge = Gauge::default()
            .block(Block::default())
            .gauge_style(Style::default().fg(Theme::SUCCESS).bg(Theme::ACCENT))
            .percent(mem_pct)
            .label(mem_label);
        frame.render_widget(mem_gauge, rows[2]);
    }
}

impl View for MonitorView {
    fn render(&self, frame: &mut Frame, area: Rect) {
        let service_height = if area.width < 80 { 9 } else { 5 };
        let sections = Layout::default()
            .direction(Direction::Vertical)
            .constraints([
                Constraint::Length(service_height),
                Constraint::Length(8),
                Constraint::Min(0),
            ])
            .split(area);

        self.render_service_cards(frame, sections[0]);
        self.render_sparkline(frame, sections[1]);

        let bottom_direction = if area.width < 90 {
            Direction::Vertical
        } else {
            Direction::Horizontal
        };
        let bottom = Layout::default()
            .direction(bottom_direction)
            .constraints(match bottom_direction {
                Direction::Vertical => [Constraint::Percentage(50), Constraint::Percentage(50)],
                Direction::Horizontal => [Constraint::Percentage(55), Constraint::Percentage(45)],
            })
            .split(sections[2]);

        self.render_models(frame, bottom[0]);
        self.render_resources(frame, bottom[1]);
    }

    fn handle_key(&mut self, key: KeyCode) {
        if let KeyCode::Char('r') = key {
            self.refresh_requested = true;
        }
    }

    fn name(&self) -> &str {
        "System"
    }

    fn as_any_mut(&mut self) -> &mut dyn std::any::Any {
        self
    }

    fn keybindings(&self) -> Vec<(&'static str, &'static str)> {
        vec![("r", "Refresh data")]
    }
}
