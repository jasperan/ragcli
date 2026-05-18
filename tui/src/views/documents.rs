use super::text::{truncate_end, wrap_text};
use super::View;
use crate::api::models::{ChunkDetailResponse, DocumentInfo};
use crate::theme::Theme;
use crossterm::event::KeyCode;
use ratatui::layout::{Constraint, Direction, Layout, Rect};
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, List, ListItem, ListState, Paragraph};
use ratatui::Frame;
use std::cell::RefCell;

pub struct DocumentsView {
    pub documents: Vec<DocumentInfo>,
    pub total_count: i64,
    pub selected: usize,
    pub chunks: Vec<ChunkDetailResponse>,
    pub chunk_scroll: usize,
    pub filter: String,
    pub filter_active: bool,
    pub list_state: RefCell<ListState>,
    pub marked_for_deletion: Option<String>,
    pub loading: bool,
    pub chunks_loading: bool,
    pub error: Option<String>,
    pub pending_refresh: bool,
    pub pending_chunk_load: Option<String>,
    pub loading_chunks_for: Option<String>,
    pub pending_delete: Option<String>,
}

impl DocumentsView {
    pub fn new() -> Self {
        let mut ls = ListState::default();
        ls.select(Some(0));
        Self {
            documents: Vec::new(),
            total_count: 0,
            selected: 0,
            chunks: Vec::new(),
            chunk_scroll: 0,
            filter: String::new(),
            filter_active: false,
            list_state: RefCell::new(ls),
            marked_for_deletion: None,
            loading: true,
            chunks_loading: false,
            error: None,
            pending_refresh: true,
            pending_chunk_load: None,
            loading_chunks_for: None,
            pending_delete: None,
        }
    }

    pub fn take_refresh_request(&mut self) -> bool {
        std::mem::take(&mut self.pending_refresh)
    }

    pub fn take_chunk_load_request(&mut self) -> Option<String> {
        self.pending_chunk_load.take()
    }

    pub fn take_delete_request(&mut self) -> Option<String> {
        self.pending_delete.take()
    }

    pub fn set_documents(&mut self, documents: Vec<DocumentInfo>, total_count: i64) {
        self.documents = documents;
        self.total_count = total_count;
        self.loading = false;
        self.error = None;
        self.sync_selection();
    }

    fn reset_selection(&mut self) {
        self.selected = 0;
        self.clear_chunk_preview();
        self.sync_selection();
    }

    fn clear_chunk_preview(&mut self) {
        self.chunks.clear();
        self.chunks_loading = false;
        self.loading_chunks_for = None;
        self.chunk_scroll = 0;
    }

    fn sync_selection(&mut self) {
        let count = self.filtered_docs().len();
        if count == 0 {
            self.selected = 0;
            self.list_state.borrow_mut().select(None);
        } else {
            self.selected = self.selected.min(count - 1);
            self.list_state.borrow_mut().select(Some(self.selected));
        }
    }

    pub fn set_chunks(&mut self, doc_id: &str, chunks: Vec<ChunkDetailResponse>) -> bool {
        if self.loading_chunks_for.as_deref() != Some(doc_id) {
            return false;
        }

        self.chunks = chunks;
        self.chunks_loading = false;
        self.loading_chunks_for = None;
        self.error = None;
        self.chunk_scroll = 0;
        true
    }

    pub fn remove_document(&mut self, doc_id: &str) {
        self.documents.retain(|doc| doc.document_id != doc_id);
        self.chunks.clear();
        self.loading_chunks_for = None;
        self.marked_for_deletion = None;
        self.sync_selection();
    }

    pub fn set_error(&mut self, message: String) {
        self.loading = false;
        self.chunks_loading = false;
        self.loading_chunks_for = None;
        self.error = Some(message);
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

        let title = if self.total_count > count as i64 {
            format!(" Documents ({}/{}) ", count, self.total_count)
        } else {
            format!(" Documents ({}) ", count)
        };
        let block = Block::default()
            .title(title)
            .borders(Borders::ALL)
            .border_style(Theme::border());

        let items: Vec<ListItem> = if self.loading {
            vec![ListItem::new(Line::from(Span::styled(
                "Loading documents...",
                Style::default().fg(Theme::DIM),
            )))]
        } else if let Some(error) = &self.error {
            vec![ListItem::new(Line::from(Span::styled(
                format!("Error: {}", error),
                Style::default().fg(Theme::ERROR),
            )))]
        } else if docs.is_empty() {
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
                    let name = truncate_end(&doc.filename, 28);
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
        let filter_label = if self.filter_active {
            "Filter: "
        } else {
            "f filter  r refresh"
        };
        let filter_content = if self.filter_active {
            format!("{}{}_", filter_label, self.filter)
        } else if let Some(id) = &self.marked_for_deletion {
            format!("Delete {}? press d again, Esc cancels", id)
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

        let filter_block =
            Block::default()
                .borders(Borders::ALL)
                .border_style(if self.filter_active {
                    Theme::border()
                } else {
                    Style::default().fg(Theme::DIM)
                });

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
                    .constraints([Constraint::Length(meta_height), Constraint::Min(0)])
                    .split(inner);

                let meta_lines = vec![
                    Line::from(vec![
                        Span::styled("Chunks: ", Style::default().fg(Theme::DIM)),
                        Span::styled(
                            d.chunk_count.to_string(),
                            Style::default().fg(Theme::PRIMARY),
                        ),
                        Span::raw("   "),
                        Span::styled("Size: ", Style::default().fg(Theme::DIM)),
                        Span::styled(
                            Self::format_size(d.file_size_bytes),
                            Style::default().fg(Theme::TEXT),
                        ),
                        Span::raw("   "),
                        Span::styled("Format: ", Style::default().fg(Theme::DIM)),
                        Span::styled(
                            d.file_format.to_uppercase(),
                            Style::default().fg(Theme::TEXT),
                        ),
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
                    let msg = if self.chunks_loading {
                        "Loading chunks..."
                    } else if d.chunk_count == 0 {
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
                        lines.push(Line::from(vec![Span::styled(
                            format!(
                                "Chunk #{} (tokens: {}): ",
                                chunk.chunk_number, chunk.token_count
                            ),
                            Style::default()
                                .fg(Theme::PRIMARY)
                                .add_modifier(Modifier::BOLD),
                        )]));

                        for wrapped in wrap_text(&chunk.text, avail_width) {
                            lines.push(Line::from(Span::styled(
                                wrapped,
                                Style::default().fg(Theme::TEXT),
                            )));
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
        let direction = if area.width < 90 {
            Direction::Vertical
        } else {
            Direction::Horizontal
        };
        let panes = Layout::default()
            .direction(direction)
            .constraints(match direction {
                Direction::Vertical => [Constraint::Percentage(45), Constraint::Percentage(55)],
                Direction::Horizontal => [Constraint::Percentage(45), Constraint::Percentage(55)],
            })
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
                    self.reset_selection();
                }
                KeyCode::Backspace => {
                    self.filter.pop();
                }
                KeyCode::Char(c) => {
                    self.filter.push(c);
                    self.reset_selection();
                }
                _ => {}
            }
            return;
        }

        match key {
            KeyCode::Char('j') | KeyCode::Down => {
                let count = self.filtered_docs().len();
                if count > 0 {
                    let next = (self.selected + 1).min(count - 1);
                    if next != self.selected {
                        self.selected = next;
                        self.clear_chunk_preview();
                        self.list_state.borrow_mut().select(Some(self.selected));
                    }
                }
            }
            KeyCode::Char('k') | KeyCode::Up => {
                if self.selected > 0 {
                    self.selected -= 1;
                    self.clear_chunk_preview();
                    self.list_state.borrow_mut().select(Some(self.selected));
                }
            }
            KeyCode::Enter => {
                if let Some(doc_id) = self.selected_doc().map(|doc| doc.document_id.clone()) {
                    self.chunks_loading = true;
                    self.loading_chunks_for = Some(doc_id.clone());
                    self.chunks.clear();
                    self.chunk_scroll = 0;
                    self.pending_chunk_load = Some(doc_id);
                }
            }
            KeyCode::Char('f') | KeyCode::Char('/') => {
                self.filter_active = true;
            }
            KeyCode::Char('r') => {
                self.loading = true;
                self.pending_refresh = true;
            }
            KeyCode::Esc => {
                if !self.filter.is_empty() {
                    self.filter.clear();
                    self.reset_selection();
                } else {
                    self.marked_for_deletion = None;
                }
            }
            KeyCode::Char('d') => {
                if let Some(doc_id) = self.selected_doc().map(|doc| doc.document_id.clone()) {
                    if self.marked_for_deletion.as_deref() == Some(doc_id.as_str()) {
                        self.pending_delete = Some(doc_id);
                    } else {
                        self.marked_for_deletion = Some(doc_id);
                    }
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

    fn as_any_mut(&mut self) -> &mut dyn std::any::Any {
        self
    }

    fn keybindings(&self) -> Vec<(&'static str, &'static str)> {
        vec![
            ("j/k", "Navigate list"),
            ("Enter", "Load chunks"),
            ("f", "Filter"),
            ("r", "Refresh list"),
            ("d,d", "Confirm delete"),
            ("J/K", "Scroll chunks"),
        ]
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crossterm::event::KeyCode;

    fn document(id: &str) -> DocumentInfo {
        DocumentInfo {
            document_id: id.to_string(),
            filename: format!("{id}.txt"),
            file_format: "txt".to_string(),
            file_size_bytes: 10,
            chunk_count: 1,
            total_tokens: 3,
        }
    }

    fn chunk(id: &str) -> ChunkDetailResponse {
        ChunkDetailResponse {
            chunk_id: id.to_string(),
            chunk_number: 1,
            text: "chunk".to_string(),
            token_count: 1,
            character_count: 5,
        }
    }

    #[test]
    fn loading_another_document_clears_stale_chunks() {
        let mut view = DocumentsView::new();
        view.set_documents(vec![document("doc-a"), document("doc-b")], 2);
        view.loading_chunks_for = Some("doc-a".to_string());
        assert!(view.set_chunks("doc-a", vec![chunk("chunk-a")]));

        view.handle_key(KeyCode::Down);
        assert!(view.chunks.is_empty());
        assert_eq!(view.loading_chunks_for, None);

        view.handle_key(KeyCode::Enter);

        assert!(view.chunks.is_empty());
        assert_eq!(view.loading_chunks_for.as_deref(), Some("doc-b"));
        assert_eq!(view.take_chunk_load_request().as_deref(), Some("doc-b"));
    }

    #[test]
    fn stale_chunk_response_is_ignored() {
        let mut view = DocumentsView::new();
        view.set_documents(vec![document("doc-a"), document("doc-b")], 2);
        view.chunks_loading = true;
        view.loading_chunks_for = Some("doc-b".to_string());

        assert!(!view.set_chunks("doc-a", vec![chunk("stale")]));
        assert!(view.chunks.is_empty());
        assert!(view.chunks_loading);
    }
}
