use ratatui::Frame;
use ratatui::layout::{Constraint, Direction, Layout, Rect};
use ratatui::widgets::{Block, Borders, Paragraph, Sparkline, Gauge};
use ratatui::text::{Line, Span};
use ratatui::style::{Style, Modifier};
use crossterm::event::KeyCode;
use crate::theme::Theme;
use crate::api::models::{SystemStatus, SystemStats, ModelsResponse};
use super::View;

pub struct MonitorView {
    pub health: Option<SystemStatus>,
    pub stats: Option<SystemStats>,
    pub models: Option<ModelsResponse>,
    pub latency_history: Vec<u64>,
    pub cpu_percent: f64,
    pub mem_percent: f64,
    pub refresh_requested: bool,
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
            refresh_requested: false,
        }
    }

    fn render_service_cards(&self, frame: &mut Frame, area: Rect) {
        let chunks = Layout::default()
            .direction(Direction::Horizontal)
            .constraints([
                Constraint::Percentage(33),
                Constraint::Percentage(34),
                Constraint::Percentage(33),
            ])
            .split(area);

        // --- API card ---
        let api_healthy = self.health.as_ref().map(|h| h.healthy).unwrap_or(false);
        let api_dot = if api_healthy { "● " } else { "○ " };
        let api_dot_style = if api_healthy {
            Style::default().fg(Theme::SUCCESS)
        } else {
            Style::default().fg(Theme::ERROR)
        };
        let api_detail = match &self.stats {
            Some(s) => format!("{} docs", s.total_documents),
            None => "Connecting...".to_string(),
        };
        let api_lines = vec![
            Line::from(vec![
                Span::styled(api_dot, api_dot_style),
                Span::styled("API Server", Style::default().fg(Theme::TEXT).add_modifier(Modifier::BOLD)),
            ]),
            Line::from(Span::styled(api_detail, Style::default().fg(Theme::DIM))),
        ];
        let api_block = Block::default()
            .title(" API ")
            .borders(Borders::ALL)
            .border_style(Theme::border());
        frame.render_widget(
            Paragraph::new(api_lines).block(api_block),
            chunks[0],
        );

        // --- Oracle DB card ---
        let db_healthy = self.health.as_ref()
            .map(|h| h.database.status == "healthy")
            .unwrap_or(false);
        let db_dot = if db_healthy { "● " } else { "○ " };
        let db_dot_style = if db_healthy {
            Style::default().fg(Theme::SUCCESS)
        } else {
            Style::default().fg(Theme::ERROR)
        };
        let db_detail = match &self.stats {
            Some(s) => format!("{} vectors, dim={}", s.total_vectors, s.embedding_dimension),
            None => "Connecting...".to_string(),
        };
        let db_lines = vec![
            Line::from(vec![
                Span::styled(db_dot, db_dot_style),
                Span::styled("Oracle DB", Style::default().fg(Theme::TEXT).add_modifier(Modifier::BOLD)),
            ]),
            Line::from(Span::styled(db_detail, Style::default().fg(Theme::DIM))),
        ];
        let db_block = Block::default()
            .title(" Oracle DB ")
            .borders(Borders::ALL)
            .border_style(Theme::border());
        frame.render_widget(
            Paragraph::new(db_lines).block(db_block),
            chunks[1],
        );

        // --- Ollama card ---
        let ollama_healthy = self.health.as_ref()
            .map(|h| h.ollama.status == "healthy")
            .unwrap_or(false);
        let ollama_dot = if ollama_healthy { "● " } else { "○ " };
        let ollama_dot_style = if ollama_healthy {
            Style::default().fg(Theme::SUCCESS)
        } else {
            Style::default().fg(Theme::ERROR)
        };
        let ollama_detail = match &self.models {
            Some(m) => format!("{} models", m.chat_models.len() + m.embedding_models.len()),
            None => "Connecting...".to_string(),
        };
        let ollama_lines = vec![
            Line::from(vec![
                Span::styled(ollama_dot, ollama_dot_style),
                Span::styled("Ollama", Style::default().fg(Theme::TEXT).add_modifier(Modifier::BOLD)),
            ]),
            Line::from(Span::styled(ollama_detail, Style::default().fg(Theme::DIM))),
        ];
        let ollama_block = Block::default()
            .title(" Ollama ")
            .borders(Borders::ALL)
            .border_style(Theme::border());
        frame.render_widget(
            Paragraph::new(ollama_lines).block(ollama_block),
            chunks[2],
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
            None => vec![Line::from(Span::styled("...", Style::default().fg(Theme::DIM)))],
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
                    rows.push(Line::from(Span::styled("No models found", Style::default().fg(Theme::DIM))));
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
        let sections = Layout::default()
            .direction(Direction::Vertical)
            .constraints([
                Constraint::Length(5),
                Constraint::Length(8),
                Constraint::Min(0),
            ])
            .split(area);

        self.render_service_cards(frame, sections[0]);
        self.render_sparkline(frame, sections[1]);

        let bottom = Layout::default()
            .direction(Direction::Horizontal)
            .constraints([
                Constraint::Percentage(55),
                Constraint::Percentage(45),
            ])
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

    fn keybindings(&self) -> Vec<(&'static str, &'static str)> {
        vec![
            ("r", "Refresh data"),
        ]
    }
}
