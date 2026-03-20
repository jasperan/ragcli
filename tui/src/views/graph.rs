use ratatui::Frame;
use ratatui::layout::{Constraint, Layout, Rect};
use ratatui::widgets::{Block, Borders, Paragraph};
use ratatui::style::{Style, Modifier};
use ratatui::buffer::Buffer;
use crossterm::event::KeyCode;
use crate::theme::Theme;
use crate::api::models::{KgEntity, KgRelationship};
use crate::widgets::graph::{ForceLayout, GraphNode, GraphEdge};
use super::View;

pub struct GraphView {
    pub entities: Vec<KgEntity>,
    pub relationships: Vec<KgRelationship>,
    pub layout: ForceLayout,
    pub focused: usize,
    pub search_query: String,
    pub search_active: bool,
    pub expansion_stack: Vec<String>,
}

impl GraphView {
    pub fn new() -> Self {
        Self {
            entities: Vec::new(),
            relationships: Vec::new(),
            layout: ForceLayout::new(Vec::new(), Vec::new()),
            focused: 0,
            search_query: String::new(),
            search_active: false,
            expansion_stack: Vec::new(),
        }
    }

    pub fn load(&mut self, entities: Vec<KgEntity>, relationships: Vec<KgRelationship>, area_w: f64, area_h: f64) {
        let nodes: Vec<GraphNode> = entities.iter().map(|e| GraphNode {
            id: e.entity_id.clone(),
            label: e.entity_name.clone(),
            node_type: e.entity_type.clone(),
            x: area_w / 2.0,
            y: area_h / 2.0,
            vx: 0.0,
            vy: 0.0,
        }).collect();

        let edges: Vec<GraphEdge> = relationships.iter().map(|r| GraphEdge {
            source: r.source_id.clone(),
            target: r.target_id.clone(),
            label: r.rel_type.clone(),
        }).collect();

        self.entities = entities;
        self.relationships = relationships;
        self.layout = ForceLayout::new(nodes, edges);
        self.layout.randomize(area_w, area_h);
        self.layout.step(50, area_w, area_h);
        self.focused = 0;
    }

    fn focused_entity(&self) -> Option<&KgEntity> {
        self.entities.get(self.focused)
    }

    fn edge_count_for(&self, entity_id: &str) -> usize {
        self.relationships.iter()
            .filter(|r| r.source_id == entity_id || r.target_id == entity_id)
            .count()
    }

    /// Move focus to the node nearest in the given direction.
    fn move_focus(&mut self, dx: i32, dy: i32) {
        if self.layout.nodes.is_empty() {
            return;
        }
        let cur = &self.layout.nodes[self.focused];
        let cx = cur.x;
        let cy = cur.y;

        let mut best_idx = self.focused;
        let mut best_score = f64::MAX;

        for (i, node) in self.layout.nodes.iter().enumerate() {
            if i == self.focused {
                continue;
            }
            let delta_x = node.x - cx;
            let delta_y = node.y - cy;
            // Only consider nodes in the intended direction
            let dir_match = (dx > 0 && delta_x > 0.0)
                || (dx < 0 && delta_x < 0.0)
                || (dy > 0 && delta_y > 0.0)
                || (dy < 0 && delta_y < 0.0);
            if !dir_match {
                continue;
            }
            let dist = (delta_x * delta_x + delta_y * delta_y).sqrt();
            if dist < best_score {
                best_score = dist;
                best_idx = i;
            }
        }
        self.focused = best_idx;
    }

    fn render_graph_canvas(&self, buf: &mut Buffer, area: Rect) {
        let w = area.width as f64;
        let h = area.height as f64;

        // Build a position map for edge drawing
        let pos: Vec<(u16, u16)> = self.layout.nodes.iter().map(|n| {
            let col = (n.x / w * (area.width as f64)).clamp(0.0, (area.width - 1) as f64) as u16;
            let row = (n.y / h * (area.height as f64)).clamp(0.0, (area.height - 1) as f64) as u16;
            (area.left() + col, area.top() + row)
        }).collect();

        // Map node id -> index
        use std::collections::HashMap;
        let idx_map: HashMap<&str, usize> = self.layout.nodes.iter().enumerate()
            .map(|(i, n)| (n.id.as_str(), i))
            .collect();

        // Draw edges first (so nodes paint over them)
        for edge in &self.layout.edges {
            if let (Some(&si), Some(&ti)) = (idx_map.get(edge.source.as_str()), idx_map.get(edge.target.as_str())) {
                let (sx, sy) = pos[si];
                let (tx, ty) = pos[ti];
                let style = Style::default().fg(ratatui::style::Color::DarkGray);

                // Draw horizontal segment then vertical segment
                let (x0, x1) = if sx <= tx { (sx, tx) } else { (tx, sx) };
                let (y0, y1) = if sy <= ty { (sy, ty) } else { (ty, sy) };

                // Horizontal leg at source row
                for x in x0..=x1 {
                    if x < area.right() && sy < area.bottom() {
                        buf[(x, sy)].set_symbol("─").set_style(style);
                    }
                }
                // Vertical leg at target column
                for y in y0..=y1 {
                    if tx < area.right() && y < area.bottom() {
                        buf[(tx, y)].set_symbol("│").set_style(style);
                    }
                }
                // Corner where they meet
                if tx < area.right() && sy < area.bottom() {
                    let corner = if sx <= tx {
                        if sy <= ty { "┐" } else { "┘" }
                    } else {
                        if sy <= ty { "┌" } else { "└" }
                    };
                    buf[(tx, sy)].set_symbol(corner).set_style(style);
                }
            }
        }

        // Draw nodes on top
        for (i, node) in self.layout.nodes.iter().enumerate() {
            let (col, row) = pos[i];
            let label = format!("[{}]", &node.label);
            let is_focused = i == self.focused;
            let style = if is_focused {
                Theme::tab_active().add_modifier(Modifier::BOLD)
            } else {
                Style::default().fg(ratatui::style::Color::White)
            };

            // Truncate label to available width
            let avail = (area.right().saturating_sub(col)) as usize;
            let display = if label.len() > avail { &label[..avail.min(label.len())] } else { &label };
            for (ci, ch) in display.chars().enumerate() {
                let x = col + ci as u16;
                if x < area.right() && row < area.bottom() {
                    buf[(x, row)].set_symbol(&ch.to_string()).set_style(style);
                }
            }
        }
    }

    fn render_detail_strip(&self, frame: &mut Frame, area: Rect) {
        let text = if let Some(e) = self.focused_entity() {
            let edges = self.edge_count_for(&e.entity_id);
            let desc = e.description.as_deref().unwrap_or("—");
            let truncated = if desc.len() > 80 { &desc[..80] } else { desc };
            let search_hint = if self.search_active {
                format!("  search: {}_", self.search_query)
            } else {
                "  [s] search  [f] re-layout  [Enter] expand  [Bsp] collapse".to_string()
            };
            format!(
                " {} | type: {} | mentions: {} | edges: {} | {}{}",
                e.entity_name, e.entity_type, e.mention_count, edges, truncated, search_hint
            )
        } else {
            " No entities loaded — press [f] to refresh".to_string()
        };

        let para = Paragraph::new(text)
            .style(Style::default().fg(ratatui::style::Color::Cyan))
            .block(Block::default().borders(Borders::TOP));
        frame.render_widget(para, area);
    }
}

impl View for GraphView {
    fn render(&self, frame: &mut Frame, area: Rect) {
        // Split: graph canvas + 3-line detail strip
        let chunks = Layout::vertical([
            Constraint::Min(5),
            Constraint::Length(3),
        ]).split(area);

        let canvas_area = chunks[0];
        let detail_area = chunks[1];

        // Outer block for canvas
        let block = Block::default()
            .title(" Knowledge Graph Explorer ")
            .borders(Borders::ALL)
            .border_style(Theme::border());

        let inner = block.inner(canvas_area);
        frame.render_widget(block, canvas_area);

        // Render directly into buffer
        let buf = frame.buffer_mut();
        self.render_graph_canvas(buf, inner);

        // Detail strip needs a mutable frame ref — use render_widget
        self.render_detail_strip(frame, detail_area);
    }

    fn handle_key(&mut self, key: KeyCode) {
        if self.search_active {
            match key {
                KeyCode::Esc => {
                    self.search_active = false;
                }
                KeyCode::Backspace => {
                    self.search_query.pop();
                }
                KeyCode::Char(c) => {
                    self.search_query.push(c);
                    // Find first entity matching query
                    let q = self.search_query.to_lowercase();
                    if let Some(idx) = self.layout.nodes.iter().position(|n| n.label.to_lowercase().contains(&q)) {
                        self.focused = idx;
                    }
                }
                _ => {}
            }
            return;
        }

        match key {
            KeyCode::Left  => self.move_focus(-1, 0),
            KeyCode::Right => self.move_focus(1, 0),
            KeyCode::Up    => self.move_focus(0, -1),
            KeyCode::Down  => self.move_focus(0, 1),
            KeyCode::Enter => {
                if let Some(e) = self.focused_entity() {
                    self.expansion_stack.push(e.entity_id.clone());
                }
            }
            KeyCode::Backspace => {
                self.expansion_stack.pop();
            }
            KeyCode::Char('f') => {
                // Re-run layout with current canvas size estimate
                let w = 120.0_f64;
                let h = 40.0_f64;
                self.layout.step(30, w, h);
            }
            KeyCode::Char('s') => {
                self.search_active = true;
                self.search_query.clear();
            }
            _ => {}
        }
    }

    fn name(&self) -> &str { "Graph" }
}
