use ratatui::Frame;
use ratatui::layout::{Constraint, Direction, Layout, Rect};
use ratatui::widgets::{Block, Borders, Paragraph, Wrap};
use ratatui::text::{Line, Span};
use ratatui::style::{Modifier, Style};
use crossterm::event::KeyCode;
use rattles::presets::prelude as spinners;
use crate::theme::Theme;
use super::View;

#[derive(Clone, PartialEq)]
pub enum AgentStatus {
    Pending,
    Running,
    Complete,
    Failed,
}

#[derive(Clone)]
pub struct AgentPane {
    pub name: String,
    pub status: AgentStatus,
    pub output: Vec<String>,
    pub duration_ms: Option<u64>,
}

impl AgentPane {
    pub fn new(name: &str) -> Self {
        Self {
            name: name.to_string(),
            status: AgentStatus::Pending,
            output: Vec::new(),
            duration_ms: None,
        }
    }

    pub fn status_icon(&self) -> String {
        match self.status {
            AgentStatus::Pending => "○".to_string(),
            AgentStatus::Running => spinners::dots().current_frame().to_string(),
            AgentStatus::Complete => "✓".to_string(),
            AgentStatus::Failed => "✗".to_string(),
        }
    }

    pub fn status_style(&self) -> Style {
        match self.status {
            AgentStatus::Pending => Style::default().fg(Theme::DIM),
            AgentStatus::Running => Style::default().fg(Theme::PRIMARY).add_modifier(Modifier::BOLD),
            AgentStatus::Complete => Style::default().fg(Theme::SUCCESS),
            AgentStatus::Failed => Style::default().fg(Theme::ERROR),
        }
    }
}

pub struct AgentsView {
    pub agents: [AgentPane; 4],
    pub current_query: String,
    pub current_stage: usize,
    pub elapsed_ms: u64,
    pub focused_agent: Option<usize>,
    pub has_trace: bool,
    pub replay_requested: bool,
}

impl AgentsView {
    pub fn new() -> Self {
        Self {
            agents: [
                AgentPane::new("Planner"),
                AgentPane::new("Researcher"),
                AgentPane::new("Reasoner"),
                AgentPane::new("Synthesizer"),
            ],
            current_query: String::new(),
            current_stage: 0,
            elapsed_ms: 0,
            focused_agent: None,
            has_trace: false,
            replay_requested: false,
        }
    }

    pub fn start_trace(&mut self, query: &str) {
        self.current_query = query.to_string();
        self.current_stage = 0;
        self.elapsed_ms = 0;
        self.has_trace = true;
        self.replay_requested = false;
        for agent in self.agents.iter_mut() {
            agent.status = AgentStatus::Pending;
            agent.output.clear();
            agent.duration_ms = None;
        }
    }

    pub fn agent_started(&mut self, agent_idx: usize) {
        if agent_idx < 4 {
            self.agents[agent_idx].status = AgentStatus::Running;
            self.current_stage = agent_idx;
        }
    }

    pub fn agent_output(&mut self, agent_idx: usize, text: &str) {
        if agent_idx < 4 {
            self.agents[agent_idx].output.push(text.to_string());
        }
    }

    pub fn agent_completed(&mut self, agent_idx: usize, duration_ms: u64) {
        if agent_idx < 4 {
            self.agents[agent_idx].status = AgentStatus::Complete;
            self.agents[agent_idx].duration_ms = Some(duration_ms);
        }
    }

    pub fn agent_failed(&mut self, agent_idx: usize) {
        if agent_idx < 4 {
            self.agents[agent_idx].status = AgentStatus::Failed;
        }
    }

    fn render_agent_pane(&self, frame: &mut Frame, area: Rect, idx: usize) {
        let agent = &self.agents[idx];
        let icon = agent.status_icon();
        let status_style = agent.status_style();

        let title = format!(" {} {} ", icon, agent.name);
        let block = Block::default()
            .title(Span::styled(title, status_style))
            .borders(Borders::ALL)
            .border_style(Theme::border());

        let inner = block.inner(area);
        frame.render_widget(block, area);

        let lines: Vec<Line> = if matches!(agent.status, AgentStatus::Pending) {
            vec![Line::from(Span::styled("(waiting)", Style::default().fg(Theme::DIM)))]
        } else if agent.output.is_empty() {
            if matches!(agent.status, AgentStatus::Running) {
                let frame = spinners::waverows().current_frame();
                vec![Line::from(vec![
                    Span::styled(frame, Style::default().fg(Theme::PRIMARY)),
                    Span::styled(" thinking...", Style::default().fg(Theme::DIM)),
                ])]
            } else {
                vec![Line::from("")]
            }
        } else {
            agent.output.iter().map(|s| Line::from(Span::styled(s.as_str(), Style::default().fg(Theme::TEXT)))).collect()
        };

        let duration_line = if let Some(ms) = agent.duration_ms {
            vec![Line::from(Span::styled(
                format!("Done in {:.1}s", ms as f64 / 1000.0),
                Style::default().fg(Theme::DIM),
            ))]
        } else {
            vec![]
        };

        let all_lines: Vec<Line> = lines.into_iter().chain(duration_line).collect();

        let para = Paragraph::new(all_lines).wrap(Wrap { trim: true });
        frame.render_widget(para, inner);
    }

    fn render_info_strip(&self, frame: &mut Frame, area: Rect) {
        let block = Block::default()
            .borders(Borders::TOP)
            .border_style(Theme::border());
        let inner = block.inner(area);
        frame.render_widget(block, area);

        let query_display = if self.current_query.is_empty() {
            "(no query)".to_string()
        } else {
            format!("\"{}\"", self.current_query)
        };

        let stage_num = self.current_stage + 1;
        let elapsed_s = self.elapsed_ms as f64 / 1000.0;

        let lines = vec![
            Line::from(vec![
                Span::styled("Query: ", Style::default().fg(Theme::DIM)),
                Span::styled(query_display, Style::default().fg(Theme::TEXT)),
            ]),
            Line::from(vec![
                Span::styled("Pipeline: 4 agents", Style::default().fg(Theme::DIM)),
                Span::styled(" │ ", Style::default().fg(Theme::SECONDARY)),
                Span::styled(format!("Stage {}/4", stage_num), Style::default().fg(Theme::PRIMARY)),
                Span::styled(" │ ", Style::default().fg(Theme::SECONDARY)),
                Span::styled(format!("Elapsed: {:.1}s", elapsed_s), Style::default().fg(Theme::DIM)),
            ]),
        ];

        let para = Paragraph::new(lines);
        frame.render_widget(para, inner);
    }
}

impl View for AgentsView {
    fn render(&self, frame: &mut Frame, area: Rect) {
        if !self.has_trace {
            let block = Block::default()
                .title(" Agent Trace ")
                .borders(Borders::ALL)
                .border_style(Theme::border());
            let content = Paragraph::new(vec![
                Line::from(""),
                Line::from(Span::styled(
                    "  Run a query with tracing to see agent activity...",
                    Style::default().fg(Theme::DIM),
                )),
                Line::from(""),
                Line::from(Span::styled(
                    "  Keys: 1-4 focus agent │ Esc unfocus │ r replay",
                    Style::default().fg(Theme::DIM),
                )),
            ])
            .block(block);
            frame.render_widget(content, area);
            return;
        }

        // Split: content area + info strip (3 lines)
        let chunks = Layout::default()
            .direction(Direction::Vertical)
            .constraints([Constraint::Min(1), Constraint::Length(3)])
            .split(area);

        let content_area = chunks[0];
        let info_area = chunks[1];

        // Render focused or 4-column layout
        if let Some(idx) = self.focused_agent {
            self.render_agent_pane(frame, content_area, idx);
        } else {
            let cols = Layout::default()
                .direction(Direction::Horizontal)
                .constraints([
                    Constraint::Percentage(25),
                    Constraint::Percentage(25),
                    Constraint::Percentage(25),
                    Constraint::Percentage(25),
                ])
                .split(content_area);

            for i in 0..4 {
                self.render_agent_pane(frame, cols[i], i);
            }
        }

        self.render_info_strip(frame, info_area);
    }

    fn handle_key(&mut self, key: KeyCode) {
        match key {
            KeyCode::Char('1') => self.focused_agent = Some(0),
            KeyCode::Char('2') => self.focused_agent = Some(1),
            KeyCode::Char('3') => self.focused_agent = Some(2),
            KeyCode::Char('4') => self.focused_agent = Some(3),
            KeyCode::Esc => self.focused_agent = None,
            KeyCode::Char('r') => self.replay_requested = true,
            _ => {}
        }
    }

    fn name(&self) -> &str {
        "Agents"
    }

    fn keybindings(&self) -> Vec<(&'static str, &'static str)> {
        vec![
            ("1-4", "Focus agent"),
            ("Esc", "4-column view"),
            ("r", "Replay trace"),
        ]
    }
}
