pub fn truncate_end(value: &str, max_chars: usize) -> String {
    let char_count = value.chars().count();
    if char_count <= max_chars {
        return value.to_string();
    }
    if max_chars == 0 {
        return String::new();
    }
    if max_chars == 1 {
        return "…".to_string();
    }

    let prefix: String = value.chars().take(max_chars - 1).collect();
    format!("{prefix}…")
}

pub fn truncate_start(value: &str, max_chars: usize) -> String {
    let char_count = value.chars().count();
    if char_count <= max_chars {
        return value.to_string();
    }
    if max_chars == 0 {
        return String::new();
    }
    if max_chars <= 3 {
        return value.chars().skip(char_count - max_chars).collect();
    }

    let suffix: String = value.chars().skip(char_count - (max_chars - 3)).collect();
    format!("...{suffix}")
}

pub fn wrap_text(text: &str, width: usize) -> Vec<String> {
    let width = width.max(1);
    let flattened = text.replace('\n', " ");
    let chars: Vec<char> = flattened.chars().collect();

    chars
        .chunks(width)
        .map(|chunk| chunk.iter().collect())
        .collect()
}

#[cfg(test)]
mod tests {
    use super::{truncate_end, truncate_start, wrap_text};

    #[test]
    fn wrap_text_uses_minimum_width() {
        assert_eq!(wrap_text("abc", 0), vec!["a", "b", "c"]);
    }

    #[test]
    fn truncate_end_is_char_safe() {
        assert_eq!(truncate_end("résumé", 4), "rés…");
    }

    #[test]
    fn truncate_start_keeps_suffix() {
        assert_eq!(truncate_start("abcdefgh", 5), "...gh");
    }
}
