use futures_util::StreamExt;
use serde::Deserialize;

#[derive(Debug, Deserialize, Clone)]
pub struct SseChunkEvent {
    pub chunk_id: String,
    pub document_id: String,
    pub text: String,
    pub similarity_score: f64,
    pub chunk_number: i32,
}

#[derive(Debug, Clone)]
pub enum SseEvent {
    Chunks(Vec<SseChunkEvent>),
    Token(String),
    Done,
    Error(String),
}

/// Parse SSE frames from a reqwest response stream.
/// Returns a channel receiver that emits parsed events.
pub fn parse_sse_stream(response: reqwest::Response) -> tokio::sync::mpsc::UnboundedReceiver<SseEvent> {
    let (tx, rx) = tokio::sync::mpsc::unbounded_channel();
    tokio::spawn(async move {
        let mut stream = response.bytes_stream();
        let mut buffer = String::new();
        while let Some(Ok(bytes)) = stream.next().await {
            buffer.push_str(&String::from_utf8_lossy(&bytes));
            while let Some(pos) = buffer.find("\n\n") {
                let frame = buffer[..pos].to_string();
                buffer = buffer[pos + 2..].to_string();

                let mut event_type = String::new();
                let mut data = String::new();
                for line in frame.lines() {
                    if let Some(et) = line.strip_prefix("event: ") {
                        event_type = et.to_string();
                    } else if let Some(d) = line.strip_prefix("data: ") {
                        data = d.to_string();
                    }
                }

                let evt = match event_type.as_str() {
                    "chunks" => {
                        match serde_json::from_str(&data) {
                            Ok(chunks) => SseEvent::Chunks(chunks),
                            Err(e) => SseEvent::Error(e.to_string()),
                        }
                    }
                    "token" => {
                        #[derive(Deserialize)]
                        struct TokenData { token: String }
                        match serde_json::from_str::<TokenData>(&data) {
                            Ok(t) => SseEvent::Token(t.token),
                            Err(e) => SseEvent::Error(e.to_string()),
                        }
                    }
                    "done" => SseEvent::Done,
                    "error" => SseEvent::Error(data),
                    _ => continue,
                };
                let _ = tx.send(evt);
            }
        }
    });
    rx
}
