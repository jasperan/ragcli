use ratatui::Frame;
use ratatui::layout::{Constraint, Layout, Rect};
use ratatui::widgets::{Block, Borders, Clear, List, ListItem, ListState, Paragraph};
use ratatui::text::{Line, Span};
use ratatui::style::{Style, Modifier};
use crossterm::event::KeyCode;
use crate::theme::Theme;

pub struct PaletteAction {
    pub label: String,
    pub description: String,
    pub tab_index: Option<usize>,
}

pub struct CommandPalette {
    pub visible: bool,
    pub input: String,
    pub actions: Vec<PaletteAction>,
    pub filtered: Vec<usize>,
    pub selected: usize,
    pub list_state: ListState,
}

pub enum PaletteResult {
    SwitchTab(usize),
    Action(String),
    Close,
}

impl CommandPalette {
    pub fn new() -> Self {
        let actions = vec![
            PaletteAction { label: "New Query".into(), description: "Start a new RAG query".into(), tab_index: Some(0) },
            PaletteAction { label: "Upload Document".into(), description: "Upload a file to the knowledge base".into(), tab_index: Some(4) },
            PaletteAction { label: "View Heatmap".into(), description: "Visualize embedding vectors".into(), tab_index: Some(1) },
            PaletteAction { label: "Explore Graph".into(), description: "Browse knowledge graph entities".into(), tab_index: Some(2) },
            PaletteAction { label: "Agent Trace".into(), description: "View CoT reasoning pipeline".into(), tab_index: Some(3) },
            PaletteAction { label: "Browse Documents".into(), description: "Manage uploaded documents".into(), tab_index: Some(4) },
            PaletteAction { label: "System Status".into(), description: "Check service health".into(), tab_index: Some(5) },
            PaletteAction { label: "Refresh Data".into(), description: "Force-refresh all views".into(), tab_index: None },
            PaletteAction { label: "New Session".into(), description: "Start a fresh conversation".into(), tab_index: Some(0) },
            PaletteAction { label: "Search Entities".into(), description: "Find entities in the knowledge graph".into(), tab_index: Some(2) },
        ];
        let filtered: Vec<usize> = (0..actions.len()).collect();
        let mut list_state = ListState::default();
        list_state.select(Some(0));
        Self {
            visible: false,
            input: String::new(),
            actions,
            filtered,
            selected: 0,
            list_state,
        }
    }

    pub fn toggle(&mut self) {
        self.visible = !self.visible;
        if self.visible {
            self.input.clear();
            self.apply_filter();
        }
    }

    fn apply_filter(&mut self) {
        let query = self.input.to_lowercase();
        self.filtered = self.actions.iter().enumerate()
            .filter(|(_, a)| a.label.to_lowercase().contains(&query))
            .map(|(i, _)| i)
            .collect();
        self.selected = 0;
        if self.filtered.is_empty() {
            self.list_state.select(None);
        } else {
            self.list_state.select(Some(0));
        }
    }

    pub fn handle_key(&mut self, key: KeyCode) -> Option<PaletteResult> {
        match key {
            KeyCode::Esc => {
                self.visible = false;
                Some(PaletteResult::Close)
            }
            KeyCode::Enter => {
                if let Some(&action_idx) = self.filtered.get(self.selected) {
                    let action = &self.actions[action_idx];
                    let result = if let Some(tab) = action.tab_index {
                        PaletteResult::SwitchTab(tab)
                    } else {
                        PaletteResult::Action(action.label.clone())
                    };
                    self.visible = false;
                    Some(result)
                } else {
                    self.visible = false;
                    Some(PaletteResult::Close)
                }
            }
            KeyCode::Up => {
                if self.selected > 0 {
                    self.selected -= 1;
                    self.list_state.select(Some(self.selected));
                }
                None
            }
            KeyCode::Down => {
                if !self.filtered.is_empty() && self.selected + 1 < self.filtered.len() {
                    self.selected += 1;
                    self.list_state.select(Some(self.selected));
                }
                None
            }
            KeyCode::Backspace => {
                self.input.pop();
                self.apply_filter();
                None
            }
            KeyCode::Char(c) => {
                self.input.push(c);
                self.apply_filter();
                None
            }
            _ => None,
        }
    }

    pub fn render(&mut self, frame: &mut Frame, area: Rect) {
        let filtered_len = self.filtered.len();
        let height = (filtered_len as u16 + 3).min(15);
        let width = area.width / 2;

        let x = area.x + (area.width - width) / 2;
        let y = area.y + (area.height.saturating_sub(height)) / 3;

        let popup_area = Rect { x, y, width, height };

        frame.render_widget(Clear, popup_area);

        let block = Block::default()
            .title(" Command Palette ")
            .borders(Borders::ALL)
            .border_style(Style::default().fg(Theme::SECONDARY));

        let inner = block.inner(popup_area);
        frame.render_widget(block, popup_area);

        let [input_area, list_area] = Layout::vertical([
            Constraint::Length(1),
            Constraint::Fill(1),
        ]).areas(inner);

        // Input line
        let input_line = Line::from(vec![
            Span::styled("> ", Style::default().fg(Theme::SECONDARY).add_modifier(Modifier::BOLD)),
            Span::raw(&self.input),
        ]);
        frame.render_widget(Paragraph::new(input_line), input_area);

        // Filtered action list
        let items: Vec<ListItem> = self.filtered.iter().map(|&idx| {
            let action = &self.actions[idx];
            ListItem::new(Line::from(vec![
                Span::styled(
                    format!("{:<20}", action.label),
                    Style::default().fg(Theme::PRIMARY).add_modifier(Modifier::BOLD),
                ),
                Span::styled(
                    format!("  {}", action.description),
                    Style::default().fg(Theme::DIM),
                ),
            ]))
        }).collect();

        let list = List::new(items)
            .highlight_style(
                Style::default()
                    .bg(Theme::PRIMARY)
                    .fg(Theme::ACCENT)
                    .add_modifier(Modifier::BOLD),
            );

        frame.render_stateful_widget(list, list_area, &mut self.list_state);
    }
}
