use ratatui::Frame;
use ratatui::layout::{Constraint, Direction, Layout, Rect};
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, Paragraph};
use crossterm::event::KeyCode;
use crate::api::stream::SseChunkEvent;
use crate::theme::Theme;
use super::View;

pub struct QueryView {
    pub input: String,
    pub cursor_pos: usize,
    pub response_text: String,
    pub chunks: Vec<SseChunkEvent>,
    pub streaming: bool,
    pub session_id: Option<String>,
    pub history: Vec<(String, String)>,
    pub ttft_ms: Option<u64>,
    pub model_name: String,
    pub scroll_offset: u16,
}

impl QueryView {
    pub fn new() -> Self {
        Self {
            input: String::new(),
            cursor_pos: 0,
            response_text: String::new(),
            chunks: Vec::new(),
            streaming: false,
            session_id: None,
            history: Vec::new(),
            ttft_ms: None,
            model_name: String::from("-"),
            scroll_offset: 0,
        }
    }

    /// Called by the app layer when an SSE token arrives.
    pub fn append_token(&mut self, token: &str) {
        self.response_text.push_str(token);
    }

    /// Called by the app layer when the SSE "chunks" event arrives.
    pub fn set_chunks(&mut self, chunks: Vec<SseChunkEvent>) {
        self.chunks = chunks;
    }

    /// Called when streaming completes successfully.
    pub fn finish_stream(&mut self, query: &str) {
        self.streaming = false;
        if !self.response_text.is_empty() {
            self.history.push((query.to_string(), self.response_text.clone()));
        }
    }

    fn chunk_score_style(score: f64) -> Style {
        if score >= 0.90 {
            Style::default().fg(Theme::SUCCESS)
        } else if score >= 0.75 {
            Style::default().fg(Theme::WARNING)
        } else {
            Style::default().fg(Theme::DIM)
        }
    }

    fn render_left(&self, frame: &mut Frame, area: Rect) {
        let sections = Layout::default()
            .direction(Direction::Vertical)
            .constraints([Constraint::Length(3), Constraint::Min(0)])
            .split(area);

        // Input box
        let input_block = Block::default()
            .title(" Query ")
            .borders(Borders::ALL)
            .border_style(if self.streaming {
                Style::default().fg(Theme::WARNING)
            } else {
                Theme::border()
            });

        let before_cursor = &self.input[..self.cursor_pos];
        let after_cursor = &self.input[self.cursor_pos..];
        let next_boundary = after_cursor
            .char_indices()
            .nth(1)
            .map(|(i, _)| i)
            .unwrap_or(after_cursor.len());
        let cursor_char = if after_cursor.is_empty() {
            " ".to_string()
        } else {
            after_cursor[..next_boundary].to_string()
        };
        let after_rest = if after_cursor.is_empty() {
            String::new()
        } else {
            after_cursor[next_boundary..].to_string()
        };

        let input_line = Line::from(vec![
            Span::styled("> ", Style::default().fg(Theme::DIM)),
            Span::styled(before_cursor.to_string(), Style::default().fg(Theme::TEXT)),
            Span::styled(cursor_char, Style::default().bg(Theme::PRIMARY).fg(Color::Black)),
            Span::styled(after_rest, Style::default().fg(Theme::TEXT)),
        ]);

        let input_para = Paragraph::new(input_line).block(input_block);
        frame.render_widget(input_para, sections[0]);

        // Response area
        let resp_block = Block::default()
            .title(" Response ")
            .borders(Borders::ALL)
            .border_style(Theme::border());

        let inner = resp_block.inner(sections[1]);
        frame.render_widget(resp_block, sections[1]);

        if inner.height == 0 {
            return;
        }

        let avail_width = inner.width.saturating_sub(1) as usize;
        let mut lines: Vec<Line> = Vec::new();

        // Previous turns (dimmed)
        for (q, r) in &self.history {
            lines.push(Line::from(vec![
                Span::styled("> ", Style::default().fg(Theme::DIM)),
                Span::styled(
                    q.clone(),
                    Style::default()
                        .fg(Theme::DIM)
                        .add_modifier(Modifier::ITALIC),
                ),
            ]));
            for resp_line in r.lines() {
                let mut rem = resp_line;
                loop {
                    if rem.is_empty() {
                        break;
                    }
                    let take = rem
                        .char_indices()
                        .nth(avail_width)
                        .map(|(i, _)| i)
                        .unwrap_or(rem.len());
                    lines.push(Line::from(Span::styled(
                        rem[..take].to_string(),
                        Style::default().fg(Theme::DIM),
                    )));
                    rem = &rem[take..];
                }
            }
            lines.push(Line::from(Span::styled(
                "-".repeat(avail_width),
                Style::default().fg(Theme::DIM),
            )));
        }

        // Current streaming response
        if !self.response_text.is_empty() || self.streaming {
            for resp_line in self.response_text.lines() {
                let mut rem = resp_line;
                loop {
                    if rem.is_empty() {
                        break;
                    }
                    let take = rem
                        .char_indices()
                        .nth(avail_width)
                        .map(|(i, _)| i)
                        .unwrap_or(rem.len());
                    lines.push(Line::from(Span::styled(
                        rem[..take].to_string(),
                        Style::default().fg(Theme::TEXT),
                    )));
                    rem = &rem[take..];
                }
            }
            if self.streaming {
                lines.push(Line::from(Span::styled(
                    "\u{2588}",
                    Style::default()
                        .fg(Theme::PRIMARY)
                        .add_modifier(Modifier::SLOW_BLINK),
                )));
            }
        } else if self.history.is_empty() {
            lines.push(Line::from(Span::styled(
                "Type a query and press Enter...",
                Style::default().fg(Theme::DIM),
            )));
        }

        let total = lines.len() as u16;
        let max_scroll = total.saturating_sub(inner.height);
        let scroll = self.scroll_offset.min(max_scroll);

        let para = Paragraph::new(lines).scroll((scroll, 0));
        frame.render_widget(para, inner);
    }

    fn render_right(&self, frame: &mut Frame, area: Rect) {
        let sections = Layout::default()
            .direction(Direction::Vertical)
            .constraints([Constraint::Min(0), Constraint::Length(5)])
            .split(area);

        // Source chunks
        let chunk_block = Block::default()
            .title(" Source Chunks ")
            .borders(Borders::ALL)
            .border_style(Theme::border());

        let inner = chunk_block.inner(sections[0]);
        frame.render_widget(chunk_block, sections[0]);

        if inner.height > 0 {
            let avail_width = inner.width.saturating_sub(2) as usize;
            let mut lines: Vec<Line> = Vec::new();

            if self.chunks.is_empty() {
                lines.push(Line::from(Span::styled(
                    "No source chunks yet.",
                    Style::default().fg(Theme::DIM),
                )));
            } else {
                for (i, chunk) in self.chunks.iter().enumerate() {
                    let score_pct = (chunk.similarity_score * 100.0) as u32;
                    let fname = if chunk.document_id.len() > 20 {
                        format!("...{}", &chunk.document_id[chunk.document_id.len() - 20..])
                    } else {
                        chunk.document_id.clone()
                    };
                    let header = format!("#{} {}  {}%", i + 1, fname, score_pct);
                    lines.push(Line::from(vec![Span::styled(
                        header,
                        Self::chunk_score_style(chunk.similarity_score)
                            .add_modifier(Modifier::BOLD),
                    )]));
                    let preview = chunk.text.replace('\n', " ");
                    let take = preview
                        .char_indices()
                        .nth(avail_width)
                        .map(|(i, _)| i)
                        .unwrap_or(preview.len());
                    let preview_short = if preview.len() > take {
                        format!("{}...", &preview[..take.saturating_sub(3)])
                    } else {
                        preview[..take].to_string()
                    };
                    lines.push(Line::from(Span::styled(
                        preview_short,
                        Style::default().fg(Theme::DIM),
                    )));
                    lines.push(Line::from(""));
                }
            }

            let para = Paragraph::new(lines);
            frame.render_widget(para, inner);
        }

        // Info strip
        let info_block = Block::default()
            .title(" Session Info ")
            .borders(Borders::ALL)
            .border_style(Style::default().fg(Theme::DIM));

        let inner_info = info_block.inner(sections[1]);
        frame.render_widget(info_block, sections[1]);

        if inner_info.height > 0 {
            let session_str = self
                .session_id
                .as_deref()
                .map(|s| {
                    if s.len() > 18 {
                        format!("...{}", &s[s.len() - 18..])
                    } else {
                        s.to_string()
                    }
                })
                .unwrap_or_else(|| "none".to_string());

            let ttft_str = self
                .ttft_ms
                .map(|ms| format!("{}ms", ms))
                .unwrap_or_else(|| "-".to_string());

            let info_lines = vec![
                Line::from(vec![
                    Span::styled("Session: ", Style::default().fg(Theme::DIM)),
                    Span::styled(session_str, Style::default().fg(Theme::TEXT)),
                ]),
                Line::from(vec![
                    Span::styled("Model:   ", Style::default().fg(Theme::DIM)),
                    Span::styled(self.model_name.clone(), Style::default().fg(Theme::PRIMARY)),
                ]),
                Line::from(vec![
                    Span::styled("TTFT:    ", Style::default().fg(Theme::DIM)),
                    Span::styled(ttft_str, Style::default().fg(Theme::WARNING)),
                ]),
            ];

            let para = Paragraph::new(info_lines);
            frame.render_widget(para, inner_info);
        }
    }
}

impl View for QueryView {
    fn render(&self, frame: &mut Frame, area: Rect) {
        let panes = Layout::default()
            .direction(Direction::Horizontal)
            .constraints([Constraint::Percentage(60), Constraint::Percentage(40)])
            .split(area);

        self.render_left(frame, panes[0]);
        self.render_right(frame, panes[1]);
    }

    fn handle_key(&mut self, key: KeyCode) {
        match key {
            KeyCode::Char(c) => {
                self.input.insert(self.cursor_pos, c);
                self.cursor_pos += c.len_utf8();
            }
            KeyCode::Backspace => {
                if self.cursor_pos > 0 {
                    let mut pos = self.cursor_pos - 1;
                    while !self.input.is_char_boundary(pos) {
                        pos -= 1;
                    }
                    self.input.remove(pos);
                    self.cursor_pos = pos;
                }
            }
            KeyCode::Left => {
                if self.cursor_pos > 0 {
                    let mut pos = self.cursor_pos - 1;
                    while !self.input.is_char_boundary(pos) {
                        pos -= 1;
                    }
                    self.cursor_pos = pos;
                }
            }
            KeyCode::Right => {
                if self.cursor_pos < self.input.len() {
                    let mut pos = self.cursor_pos + 1;
                    while pos < self.input.len() && !self.input.is_char_boundary(pos) {
                        pos += 1;
                    }
                    self.cursor_pos = pos;
                }
            }
            KeyCode::Enter => {
                if !self.input.is_empty() && !self.streaming {
                    self.streaming = true;
                    self.response_text.clear();
                    self.chunks.clear();
                    self.scroll_offset = 0;
                    self.ttft_ms = None;
                }
            }
            KeyCode::Esc => {
                if self.streaming {
                    self.streaming = false;
                } else {
                    self.input.clear();
                    self.cursor_pos = 0;
                }
            }
            KeyCode::Up => {
                self.scroll_offset = self.scroll_offset.saturating_sub(1);
            }
            KeyCode::Down => {
                self.scroll_offset = self.scroll_offset.saturating_add(1);
            }
            _ => {}
        }
    }

    fn name(&self) -> &str {
        "Query"
    }

    fn keybindings(&self) -> Vec<(&'static str, &'static str)> {
        vec![
            ("Enter", "Submit query"),
            ("Esc", "Cancel/Clear"),
            ("Ctrl+N", "New session"),
            ("Up/Down", "Scroll response"),
        ]
    }
}
