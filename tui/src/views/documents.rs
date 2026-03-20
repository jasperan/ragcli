use std::cell::RefCell;
use ratatui::Frame;
use ratatui::layout::{Constraint, Direction, Layout, Rect};
use ratatui::widgets::{Block, Borders, List, ListItem, ListState, Paragraph};
use ratatui::text::{Line, Span};
use ratatui::style::{Color, Modifier, Style};
use crossterm::event::KeyCode;
use crate::theme::Theme;
use crate::api::models::{ChunkDetailResponse, DocumentInfo};
use super::View;

pub struct DocumentsView {
    pub documents: Vec<DocumentInfo>,
    pub selected: usize,
    pub chunks: Vec<ChunkDetailResponse>,
    pub chunk_scroll: usize,
    pub filter: String,
    pub filter_active: bool,
    pub list_state: RefCell<ListState>,
    pub marked_for_deletion: Option<String>,
}

impl DocumentsView {
    pub fn new() -> Self {
        let mut ls = ListState::default();
        ls.select(Some(0));
        Self {
            documents: Vec::new(),
            selected: 0,
            chunks: Vec::new(),
            chunk_scroll: 0,
            filter: String::new(),
            filter_active: false,
            list_state: RefCell::new(ls),
            marked_for_deletion: None,
        }
    }

    fn format_size(bytes: i64) -> String {
        if bytes < 1024 {
            format!("{} B", bytes)
        } else if bytes < 1024 * 1024 {
            format!("{} KB", bytes / 1024)
        } else {
            format!("{:.1} MB", bytes as f64 / (1024.0 * 1024.0))
        }
    }

    fn filtered_docs(&self) -> Vec<&DocumentInfo> {
        if self.filter.is_empty() {
            self.documents.iter().collect()
        } else {
            let q = self.filter.to_lowercase();
            self.documents
                .iter()
                .filter(|d| d.filename.to_lowercase().contains(&q))
                .collect()
        }
    }

    fn selected_doc(&self) -> Option<&DocumentInfo> {
        let docs = self.filtered_docs();
        docs.get(self.selected).copied()
    }

    fn render_left(&self, frame: &mut Frame, area: Rect) {
        let docs = self.filtered_docs();
        let count = docs.len();

        // Reserve 3 lines at bottom for filter bar (border + input line + border gap)
        let chunks = Layout::default()
            .direction(Direction::Vertical)
            .constraints([Constraint::Min(0), Constraint::Length(3)])
            .split(area);

        let list_area = chunks[0];
        let filter_area = chunks[1];

        let title = format!(" Documents ({}) ", count);
        let block = Block::default()
            .title(title)
            .borders(Borders::ALL)
            .border_style(Theme::border());

        let items: Vec<ListItem> = if docs.is_empty() {
            vec![ListItem::new(Line::from(Span::styled(
                "No documents loaded",
                Style::default().fg(Theme::DIM),
            )))]
        } else {
            docs.iter()
                .enumerate()
                .map(|(i, doc)| {
                    let size_str = Self::format_size(doc.file_size_bytes);
                    // Pad filename to align size column
                    let name_max = 28usize;
                    let name = if doc.filename.len() > name_max {
                        format!("{}…", &doc.filename[..name_max.saturating_sub(1)])
                    } else {
                        doc.filename.clone()
                    };
                    let line_text = format!("{:<28}  {}", name, size_str);

                    let marked = self
                        .marked_for_deletion
                        .as_deref()
                        .map(|id| id == doc.document_id)
                        .unwrap_or(false);

                    let style = if i == self.selected {
                        Style::default()
                            .bg(Theme::PRIMARY)
                            .fg(Color::Black)
                            .add_modifier(Modifier::BOLD)
                    } else if marked {
                        Style::default().fg(Theme::ERROR)
                    } else {
                        Style::default().fg(Theme::TEXT)
                    };

                    ListItem::new(Line::from(Span::styled(line_text, style)))
                })
                .collect()
        };

        let list = List::new(items).block(block);
        frame.render_stateful_widget(list, list_area, &mut *self.list_state.borrow_mut());

        // Filter bar
        let filter_label = if self.filter_active { "Filter: " } else { "/ to filter" };
        let filter_content = if self.filter_active {
            format!("{}{}_", filter_label, self.filter)
        } else if !self.filter.is_empty() {
            format!("Filter: {}", self.filter)
        } else {
            filter_label.to_string()
        };

        let filter_style = if self.filter_active {
            Style::default().fg(Theme::PRIMARY)
        } else {
            Style::default().fg(Theme::DIM)
        };

        let filter_block = Block::default()
            .borders(Borders::ALL)
            .border_style(if self.filter_active { Theme::border() } else { Style::default().fg(Theme::DIM) });

        let filter_para = Paragraph::new(filter_content)
            .style(filter_style)
            .block(filter_block);
        frame.render_widget(filter_para, filter_area);
    }

    fn render_right(&self, frame: &mut Frame, area: Rect) {
        let doc = self.selected_doc();

        let title = doc
            .map(|d| format!(" {} ", d.filename))
            .unwrap_or_else(|| " Preview ".to_string());

        let block = Block::default()
            .title(title)
            .borders(Borders::ALL)
            .border_style(Theme::border());

        let inner = block.inner(area);
        frame.render_widget(block, area);

        if inner.height == 0 {
            return;
        }

        match doc {
            None => {
                let placeholder = Paragraph::new("Select a document to preview its chunks.")
                    .style(Style::default().fg(Theme::DIM));
                frame.render_widget(placeholder, inner);
            }
            Some(d) => {
                // Metadata section (3 lines)
                let meta_height = 3u16;
                if inner.height <= meta_height {
                    return;
                }
                let sections = Layout::default()
                    .direction(Direction::Vertical)
                    .constraints([
                        Constraint::Length(meta_height),
                        Constraint::Min(0),
                    ])
                    .split(inner);

                let meta_lines = vec![
                    Line::from(vec![
                        Span::styled("Chunks: ", Style::default().fg(Theme::DIM)),
                        Span::styled(d.chunk_count.to_string(), Style::default().fg(Theme::PRIMARY)),
                        Span::raw("   "),
                        Span::styled("Size: ", Style::default().fg(Theme::DIM)),
                        Span::styled(Self::format_size(d.file_size_bytes), Style::default().fg(Theme::TEXT)),
                        Span::raw("   "),
                        Span::styled("Format: ", Style::default().fg(Theme::DIM)),
                        Span::styled(d.file_format.to_uppercase(), Style::default().fg(Theme::TEXT)),
                    ]),
                    Line::from(vec![
                        Span::styled("Tokens: ", Style::default().fg(Theme::DIM)),
                        Span::styled(d.total_tokens.to_string(), Style::default().fg(Theme::TEXT)),
                    ]),
                    Line::from(Span::styled(
                        "─".repeat(inner.width as usize),
                        Style::default().fg(Theme::DIM),
                    )),
                ];
                let meta = Paragraph::new(meta_lines);
                frame.render_widget(meta, sections[0]);

                // Chunk list
                let chunk_area = sections[1];
                if self.chunks.is_empty() {
                    let msg = if d.chunk_count == 0 {
                        "No chunks for this document."
                    } else {
                        "Press Enter to load chunks."
                    };
                    let p = Paragraph::new(msg).style(Style::default().fg(Theme::DIM));
                    frame.render_widget(p, chunk_area);
                } else {
                    let avail_width = chunk_area.width.saturating_sub(2) as usize;
                    let mut lines: Vec<Line> = Vec::new();

                    for chunk in &self.chunks {
                        // Header line
                        lines.push(Line::from(vec![
                            Span::styled(
                                format!("Chunk #{} (tokens: {}): ", chunk.chunk_number, chunk.token_count),
                                Style::default().fg(Theme::PRIMARY).add_modifier(Modifier::BOLD),
                            ),
                        ]));
                        // Text preview — wrap naively at avail_width
                        let text = chunk.text.replace('\n', " ");
                        let mut remaining = text.as_str();
                        while !remaining.is_empty() {
                            let take = remaining
                                .char_indices()
                                .nth(avail_width)
                                .map(|(i, _)| i)
                                .unwrap_or(remaining.len());
                            lines.push(Line::from(Span::styled(
                                remaining[..take].to_string(),
                                Style::default().fg(Theme::TEXT),
                            )));
                            remaining = &remaining[take..];
                        }
                        lines.push(Line::from("")); // blank separator
                    }

                    let total_lines = lines.len() as u16;
                    let scroll = self.chunk_scroll as u16;
                    let clamped = scroll.min(total_lines.saturating_sub(chunk_area.height));

                    let para = Paragraph::new(lines).scroll((clamped, 0));
                    frame.render_widget(para, chunk_area);
                }
            }
        }
    }
}

impl View for DocumentsView {
    fn render(&self, frame: &mut Frame, area: Rect) {
        let panes = Layout::default()
            .direction(Direction::Horizontal)
            .constraints([Constraint::Percentage(45), Constraint::Percentage(55)])
            .split(area);

        self.render_left(frame, panes[0]);
        self.render_right(frame, panes[1]);
    }

    fn handle_key(&mut self, key: KeyCode) {
        if self.filter_active {
            match key {
                KeyCode::Esc => {
                    self.filter_active = false;
                }
                KeyCode::Enter => {
                    self.filter_active = false;
                    self.selected = 0;
                    self.list_state.borrow_mut().select(Some(0));
                }
                KeyCode::Backspace => {
                    self.filter.pop();
                }
                KeyCode::Char(c) => {
                    self.filter.push(c);
                    self.selected = 0;
                    self.list_state.borrow_mut().select(Some(0));
                }
                _ => {}
            }
            return;
        }

        match key {
            KeyCode::Char('j') | KeyCode::Down => {
                let count = self.filtered_docs().len();
                if count > 0 {
                    self.selected = (self.selected + 1).min(count - 1);
                    self.list_state.borrow_mut().select(Some(self.selected));
                    self.chunk_scroll = 0;
                }
            }
            KeyCode::Char('k') | KeyCode::Up => {
                if self.selected > 0 {
                    self.selected -= 1;
                    self.list_state.borrow_mut().select(Some(self.selected));
                    self.chunk_scroll = 0;
                }
            }
            KeyCode::Enter => {
                // Chunk loading is triggered externally by the app layer
                // which watches for selection changes. Nothing to do here
                // beyond marking that the user confirmed selection.
            }
            KeyCode::Char('/') => {
                self.filter_active = true;
            }
            KeyCode::Esc => {
                if !self.filter.is_empty() {
                    self.filter.clear();
                    self.selected = 0;
                    self.list_state.borrow_mut().select(Some(0));
                } else {
                    self.marked_for_deletion = None;
                }
            }
            KeyCode::Char('d') => {
                if let Some(doc) = self.selected_doc() {
                    self.marked_for_deletion = Some(doc.document_id.clone());
                }
            }
            // Chunk scroll
            KeyCode::Char('J') | KeyCode::PageDown => {
                self.chunk_scroll = self.chunk_scroll.saturating_add(5);
            }
            KeyCode::Char('K') | KeyCode::PageUp => {
                self.chunk_scroll = self.chunk_scroll.saturating_sub(5);
            }
            _ => {}
        }
    }

    fn name(&self) -> &str {
        "Documents"
    }
}
