use ratatui::buffer::Buffer;
use ratatui::layout::Rect;
use ratatui::style::{Color, Style};
use ratatui::widgets::Widget;

/// Renders a vector as a horizontal color strip.
/// Each terminal cell covers ceil(dims/available_width) dimensions.
/// Colors: red = positive, blue = negative, dark = near-zero.
pub struct EmbeddingStrip<'a> {
    pub data: &'a [f64],
    pub label: &'a str,
    pub scroll_offset: usize,
}

impl<'a> Widget for EmbeddingStrip<'a> {
    fn render(self, area: Rect, buf: &mut Buffer) {
        if area.width < 2 || self.data.is_empty() {
            return;
        }

        let label_width = (self.label.len().min(20)) as u16;
        let label_style = Style::default().fg(Color::Rgb(226, 232, 240));
        let display_label: String = self.label.chars().take(label_width as usize).collect();
        buf.set_string(area.x, area.y, &display_label, label_style);

        let strip_start = area.x + label_width + 1;
        let strip_width = area.width.saturating_sub(label_width + 1) as usize;
        if strip_width == 0 {
            return;
        }

        let dims_per_cell = ((self.data.len() as f64) / (strip_width as f64))
            .ceil()
            .max(1.0) as usize;

        for col in 0..strip_width {
            let start = self.scroll_offset + col * dims_per_cell;
            let end = (start + dims_per_cell).min(self.data.len());
            if start >= self.data.len() {
                break;
            }

            let slice = &self.data[start..end];
            let avg: f64 = slice.iter().sum::<f64>() / slice.len() as f64;
            let color = value_to_color(avg);

            buf.set_string(
                strip_start + col as u16,
                area.y,
                "█",
                Style::default().fg(color),
            );
        }
    }
}

/// Compute contribution (element-wise product) between two vectors.
pub fn compute_contribution(a: &[f64], b: &[f64]) -> Vec<f64> {
    a.iter().zip(b.iter()).map(|(x, y)| x * y).collect()
}

fn value_to_color(v: f64) -> Color {
    let intensity = (v.abs() * 255.0 * 4.0).min(255.0) as u8;
    if v > 0.01 {
        Color::Rgb(intensity, 20, 20)
    } else if v < -0.01 {
        Color::Rgb(20, 20, intensity)
    } else {
        Color::Rgb(30, 30, 30)
    }
}
