use ratatui::Frame;
use ratatui::layout::{Constraint, Direction, Layout, Rect};
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, Paragraph};
use crossterm::event::KeyCode;
use crate::theme::Theme;
use crate::widgets::heatmap::{compute_contribution, EmbeddingStrip};
use super::View;

pub struct HeatmapChunk {
    pub label: String,
    pub similarity: f64,
    pub embedding: Vec<f64>,
}

pub struct HeatmapView {
    pub query_text: String,
    pub query_embedding: Option<Vec<f64>>,
    pub chunks: Vec<HeatmapChunk>,
    pub scroll_offset: usize,
    pub visible_chunks: usize,
    pub has_data: bool,
}

impl HeatmapView {
    pub fn new() -> Self {
        Self {
            query_text: String::new(),
            query_embedding: None,
            chunks: Vec::new(),
            scroll_offset: 0,
            visible_chunks: 3,
            has_data: false,
        }
    }
}

impl View for HeatmapView {
    fn render(&self, frame: &mut Frame, area: Rect) {
        let outer_block = Block::default()
            .title(" Vector Heatmap ")
            .borders(Borders::ALL)
            .border_style(Theme::border());

        if !self.has_data {
            let content = Paragraph::new("Run a query first to visualize embeddings...")
                .block(outer_block)
                .style(Style::default().fg(Color::Rgb(148, 163, 184)));
            frame.render_widget(content, area);
            return;
        }

        frame.render_widget(outer_block, area);

        // Inner area (subtract border)
        let inner = Rect {
            x: area.x + 1,
            y: area.y + 1,
            width: area.width.saturating_sub(2),
            height: area.height.saturating_sub(2),
        };

        if inner.height < 4 {
            return;
        }

        // Calculate how many rows we need:
        // 1 title + 1 blank + 1 query strip + 1 blank + visible_chunks*3 + 2 legend
        let visible = self.visible_chunks.min(self.chunks.len());
        let needed_rows = 1 + 1 + 1 + 1 + (visible * 3) + 2;

        let mut constraints = vec![
            Constraint::Length(1), // title
            Constraint::Length(1), // blank
            Constraint::Length(1), // query strip
            Constraint::Length(1), // blank
        ];
        for _ in 0..visible {
            constraints.push(Constraint::Length(1)); // chunk strip
            constraints.push(Constraint::Length(1)); // contribution strip
            constraints.push(Constraint::Length(1)); // blank
        }
        constraints.push(Constraint::Length(1)); // legend line 1
        constraints.push(Constraint::Min(1));    // legend line 2 / remainder

        let chunks_layout = Layout::default()
            .direction(Direction::Vertical)
            .constraints(constraints)
            .split(inner);

        // Row 0: Title
        let title_text = format!("Query: {}", self.query_text);
        let title = Paragraph::new(title_text)
            .style(Style::default().fg(Color::Rgb(226, 232, 240)).add_modifier(Modifier::BOLD));
        frame.render_widget(title, chunks_layout[0]);

        // Row 1: blank — nothing to render

        // Row 2: Query embedding strip
        if let Some(ref qe) = self.query_embedding {
            let strip = EmbeddingStrip {
                data: qe,
                label: "Query Embedding",
                scroll_offset: self.scroll_offset,
            };
            frame.render_widget(strip, chunks_layout[2]);
        }

        // Row 3: blank

        // Rows 4+: chunk strips (3 rows each)
        let base = 4usize;
        for (i, chunk) in self.chunks.iter().take(visible).enumerate() {
            let row_base = base + i * 3;
            if row_base + 2 >= chunks_layout.len() {
                break;
            }

            // Chunk embedding strip
            let pct = (chunk.similarity * 100.0).round() as u32;
            let chunk_label = format!("Chunk #{} ({:>3}%)", i + 1, pct);
            let chunk_strip = EmbeddingStrip {
                data: &chunk.embedding,
                label: &chunk_label,
                scroll_offset: self.scroll_offset,
            };
            frame.render_widget(chunk_strip, chunks_layout[row_base]);

            // Contribution strip (query × chunk element-wise)
            if let Some(ref qe) = self.query_embedding {
                let contrib = compute_contribution(qe, &chunk.embedding);
                let contrib_strip = EmbeddingStrip {
                    data: &contrib,
                    label: "Contribution  ",
                    scroll_offset: self.scroll_offset,
                };
                frame.render_widget(contrib_strip, chunks_layout[row_base + 1]);
            }

            // row_base + 2 is blank
        }

        // Legend rows
        let legend_idx = base + visible * 3;
        if legend_idx < chunks_layout.len() {
            let legend1 = Paragraph::new(Line::from(vec![
                Span::styled("█", Style::default().fg(Color::Rgb(200, 20, 20))),
                Span::raw(" positive  "),
                Span::styled("█", Style::default().fg(Color::Rgb(20, 20, 200))),
                Span::raw(" negative  "),
                Span::styled("█", Style::default().fg(Color::Rgb(30, 30, 30))),
                Span::raw(" near-zero"),
            ]));
            frame.render_widget(legend1, chunks_layout[legend_idx]);
        }

        if legend_idx + 1 < chunks_layout.len() {
            let scroll_info = format!(
                "◄/► scroll dims  +/- chunks visible ({})  showing {}/{} chunks",
                self.visible_chunks,
                visible,
                self.chunks.len()
            );
            let legend2 = Paragraph::new(scroll_info)
                .style(Style::default().fg(Color::Rgb(100, 116, 139)));
            frame.render_widget(legend2, chunks_layout[legend_idx + 1]);
        }
    }

    fn handle_key(&mut self, key: KeyCode) {
        match key {
            KeyCode::Left => {
                self.scroll_offset = self.scroll_offset.saturating_sub(10);
            }
            KeyCode::Right => {
                self.scroll_offset += 10;
            }
            KeyCode::Char('+') | KeyCode::Char('=') => {
                self.visible_chunks = (self.visible_chunks + 1).min(10);
            }
            KeyCode::Char('-') => {
                if self.visible_chunks > 1 {
                    self.visible_chunks -= 1;
                }
            }
            _ => {}
        }
    }

    fn name(&self) -> &str {
        "Heatmap"
    }
}
