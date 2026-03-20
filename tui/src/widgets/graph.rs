use std::collections::HashMap;

#[derive(Clone)]
pub struct GraphNode {
    pub id: String,
    pub label: String,
    pub node_type: String,
    pub x: f64,
    pub y: f64,
    pub vx: f64,
    pub vy: f64,
}

#[derive(Clone)]
pub struct GraphEdge {
    pub source: String,
    pub target: String,
    pub label: String,
}

pub struct ForceLayout {
    pub nodes: Vec<GraphNode>,
    pub edges: Vec<GraphEdge>,
}

impl ForceLayout {
    pub fn new(nodes: Vec<GraphNode>, edges: Vec<GraphEdge>) -> Self {
        Self { nodes, edges }
    }

    /// Run n iterations of force-directed layout.
    pub fn step(&mut self, iterations: usize, width: f64, height: f64) {
        let repulsion = 500.0;
        let attraction = 0.01;
        let damping = 0.9;

        for _ in 0..iterations {
            // Repulsion between all node pairs
            let positions: Vec<(f64, f64)> = self.nodes.iter().map(|n| (n.x, n.y)).collect();
            for i in 0..self.nodes.len() {
                for j in (i + 1)..self.nodes.len() {
                    let dx = positions[i].0 - positions[j].0;
                    let dy = positions[i].1 - positions[j].1;
                    let dist = (dx * dx + dy * dy).sqrt().max(1.0);
                    let force = repulsion / (dist * dist);
                    let fx = (dx / dist) * force;
                    let fy = (dy / dist) * force;
                    self.nodes[i].vx += fx;
                    self.nodes[i].vy += fy;
                    self.nodes[j].vx -= fx;
                    self.nodes[j].vy -= fy;
                }
            }

            // Attraction along edges — resolve indices first to avoid borrow conflicts
            let node_idx: HashMap<String, usize> = self.nodes.iter().enumerate()
                .map(|(i, n)| (n.id.clone(), i)).collect();
            let edge_pairs: Vec<(usize, usize)> = self.edges.iter()
                .filter_map(|e| {
                    let si = node_idx.get(&e.source).copied()?;
                    let ti = node_idx.get(&e.target).copied()?;
                    Some((si, ti))
                })
                .collect();
            for (si, ti) in edge_pairs {
                let dx = self.nodes[ti].x - self.nodes[si].x;
                let dy = self.nodes[ti].y - self.nodes[si].y;
                let fx = dx * attraction;
                let fy = dy * attraction;
                self.nodes[si].vx += fx;
                self.nodes[si].vy += fy;
                self.nodes[ti].vx -= fx;
                self.nodes[ti].vy -= fy;
            }

            // Center gravity
            let cx = width / 2.0;
            let cy = height / 2.0;
            for node in &mut self.nodes {
                node.vx += (cx - node.x) * 0.001;
                node.vy += (cy - node.y) * 0.001;
            }

            // Apply velocity with damping and clamp to bounds
            for node in &mut self.nodes {
                node.vx *= damping;
                node.vy *= damping;
                node.x += node.vx;
                node.y += node.vy;
                node.x = node.x.clamp(2.0, width - 2.0);
                node.y = node.y.clamp(1.0, height - 1.0);
            }
        }
    }

    /// Initialize positions deterministically from node id hash.
    pub fn randomize(&mut self, width: f64, height: f64) {
        use std::collections::hash_map::DefaultHasher;
        use std::hash::{Hash, Hasher};
        for node in &mut self.nodes {
            let mut hasher = DefaultHasher::new();
            node.id.hash(&mut hasher);
            let h = hasher.finish();
            node.x = (h % (width as u64).max(1)) as f64;
            node.y = ((h >> 32) % (height as u64).max(1)) as f64;
            node.vx = 0.0;
            node.vy = 0.0;
        }
    }
}
