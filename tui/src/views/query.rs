use super::text::{truncate_end, truncate_start, wrap_text};
use super::View;
use crate::api::models::QueryResponse;
use crate::api::stream::SseChunkEvent;
use crate::theme::Theme;
use crossterm::event::KeyCode;
use ratatui::layout::{Constraint, Direction, Layout, Rect};
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, Paragraph};
use ratatui::Frame;

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
    pub pending_query: Option<(u64, String)>,
    pub active_query_id: Option<u64>,
    pub current_query: Option<String>,
    next_query_id: u64,
    pub error: Option<String>,
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
            pending_query: None,
            active_query_id: None,
            current_query: None,
            next_query_id: 1,
            error: None,
        }
    }

    fn archive_current_response(&mut self) {
        if let Some(query) = self.current_query.take() {
            if !self.response_text.is_empty() {
                self.history.push((query, self.response_text.clone()));
            }
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
        self.active_query_id = None;
        self.current_query = Some(query.to_string());
    }

    pub fn take_pending_query(&mut self) -> Option<(u64, String, Option<String>)> {
        self.pending_query
            .take()
            .map(|(request_id, query)| (request_id, query, self.session_id.clone()))
    }

    pub fn set_query_result(
        &mut self,
        request_id: u64,
        query: String,
        response: QueryResponse,
        elapsed_ms: u64,
    ) -> bool {
        if self.active_query_id != Some(request_id) {
            return false;
        }

        let chunks = response
            .chunks
            .iter()
            .map(|chunk| SseChunkEvent {
                chunk_id: chunk.chunk_id.clone(),
                document_id: chunk.document_id.clone(),
                text: chunk.text.clone(),
                similarity_score: chunk.similarity_score,
                chunk_number: chunk.chunk_number,
            })
            .collect();

        self.response_text = response.response;
        self.chunks = chunks;
        self.session_id = response.session_id;
        self.ttft_ms = Some(elapsed_ms);
        self.error = None;
        self.streaming = false;
        self.active_query_id = None;
        self.current_query = Some(query);
        self.input.clear();
        self.cursor_pos = 0;
        true
    }

    pub fn set_query_error(&mut self, request_id: u64, message: String) -> bool {
        if self.active_query_id != Some(request_id) {
            return false;
        }

        self.streaming = false;
        self.active_query_id = None;
        self.error = Some(message);
        true
    }

    pub fn set_error(&mut self, message: String) {
        self.streaming = false;
        self.active_query_id = None;
        self.error = Some(message);
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

    fn push_wrapped_text(lines: &mut Vec<Line>, text: &str, width: usize, style: Style) {
        for wrapped in wrap_text(text, width) {
            lines.push(Line::from(Span::styled(wrapped, style)));
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
            Span::styled(
                cursor_char,
                Style::default().bg(Theme::PRIMARY).fg(Color::Black),
            ),
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
                Self::push_wrapped_text(
                    &mut lines,
                    resp_line,
                    avail_width,
                    Style::default().fg(Theme::DIM),
                );
            }
            lines.push(Line::from(Span::styled(
                "-".repeat(avail_width),
                Style::default().fg(Theme::DIM),
            )));
        }

        // Current streaming response
        if let Some(error) = &self.error {
            lines.push(Line::from(Span::styled(
                format!("Error: {}", error),
                Style::default().fg(Theme::ERROR),
            )));
        } else if !self.response_text.is_empty() || self.streaming {
            for resp_line in self.response_text.lines() {
                Self::push_wrapped_text(
                    &mut lines,
                    resp_line,
                    avail_width,
                    Style::default().fg(Theme::TEXT),
                );
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
                    let fname = truncate_start(&chunk.document_id, 23);
                    let header = format!("#{} {}  {}%", i + 1, fname, score_pct);
                    lines.push(Line::from(vec![Span::styled(
                        header,
                        Self::chunk_score_style(chunk.similarity_score)
                            .add_modifier(Modifier::BOLD),
                    )]));
                    lines.push(Line::from(Span::styled(
                        truncate_end(&chunk.text.replace('\n', " "), avail_width),
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
                .map(|s| truncate_start(s, 21))
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
        let direction = if area.width < 100 {
            Direction::Vertical
        } else {
            Direction::Horizontal
        };
        let panes = Layout::default()
            .direction(direction)
            .constraints(match direction {
                Direction::Vertical => [Constraint::Percentage(60), Constraint::Percentage(40)],
                Direction::Horizontal => [Constraint::Percentage(60), Constraint::Percentage(40)],
            })
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
                let query = self.input.trim().to_string();
                if !query.is_empty() && !self.streaming {
                    self.archive_current_response();
                    let request_id = self.next_query_id;
                    self.next_query_id = self.next_query_id.saturating_add(1);
                    self.streaming = true;
                    self.pending_query = Some((request_id, query.clone()));
                    self.active_query_id = Some(request_id);
                    self.current_query = Some(query);
                    self.error = None;
                    self.response_text.clear();
                    self.chunks.clear();
                    self.scroll_offset = 0;
                    self.ttft_ms = None;
                }
            }
            KeyCode::Esc => {
                if self.streaming {
                    self.streaming = false;
                    self.pending_query = None;
                    self.active_query_id = None;
                    self.current_query = None;
                    self.response_text.clear();
                    self.chunks.clear();
                } else {
                    self.input.clear();
                    self.cursor_pos = 0;
                    self.error = None;
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

    fn as_any_mut(&mut self) -> &mut dyn std::any::Any {
        self
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::api::models::QueryResponse;
    use crossterm::event::KeyCode;

    fn query_response(text: &str) -> QueryResponse {
        QueryResponse {
            response: text.to_string(),
            chunks: Vec::new(),
            query_embedding: None,
            metrics: serde_json::json!({}),
            session_id: None,
            trace_id: None,
        }
    }

    #[test]
    fn successful_query_stays_current_until_next_query() {
        let mut view = QueryView::new();
        view.input = "first".to_string();
        view.cursor_pos = view.input.len();
        view.handle_key(KeyCode::Enter);
        let (request_id, query, _) = view.take_pending_query().expect("pending query");

        assert!(view.set_query_result(request_id, query, query_response("answer"), 42));

        assert_eq!(view.response_text, "answer");
        assert!(view.history.is_empty());

        view.input = "second".to_string();
        view.cursor_pos = view.input.len();
        view.handle_key(KeyCode::Enter);

        assert_eq!(
            view.history,
            vec![("first".to_string(), "answer".to_string())]
        );
        assert!(view.response_text.is_empty());
    }

    #[test]
    fn cancelled_query_result_is_ignored() {
        let mut view = QueryView::new();
        view.input = "slow".to_string();
        view.cursor_pos = view.input.len();
        view.handle_key(KeyCode::Enter);
        let (request_id, query, _) = view.take_pending_query().expect("pending query");

        view.handle_key(KeyCode::Esc);

        assert!(!view.set_query_result(request_id, query, query_response("stale"), 42));
        assert!(view.response_text.is_empty());
        assert!(view.history.is_empty());
    }
}
