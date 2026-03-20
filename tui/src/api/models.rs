use serde::Deserialize;

// Health/Status
#[derive(Debug, Deserialize, Clone)]
pub struct ComponentStatus {
    pub status: String,
    pub message: String,
}

#[derive(Debug, Deserialize, Clone)]
pub struct SystemStatus {
    pub healthy: bool,
    pub database: ComponentStatus,
    pub ollama: ComponentStatus,
}

#[derive(Debug, Deserialize, Clone)]
pub struct SystemStats {
    pub total_documents: i64,
    pub total_vectors: i64,
    pub total_tokens: i64,
    pub embedding_dimension: i64,
    pub index_type: Option<String>,
}

// Query
#[derive(Debug, Deserialize, Clone)]
pub struct ChunkResult {
    pub chunk_id: String,
    pub document_id: String,
    pub text: String,
    pub similarity_score: f64,
    pub chunk_number: i32,
    pub embedding: Option<Vec<f64>>,
}

#[derive(Debug, Deserialize, Clone)]
pub struct QueryResponse {
    pub response: String,
    pub chunks: Vec<ChunkResult>,
    pub query_embedding: Option<Vec<f64>>,
    pub metrics: serde_json::Value,
    pub session_id: Option<String>,
    pub trace_id: Option<String>,
}

// Documents
#[derive(Debug, Deserialize, Clone)]
pub struct DocumentInfo {
    pub document_id: String,
    pub filename: String,
    pub file_format: String,
    pub file_size_bytes: i64,
    pub chunk_count: i32,
    pub total_tokens: i64,
}

#[derive(Debug, Deserialize, Clone)]
pub struct DocumentListResponse {
    pub documents: Vec<DocumentInfo>,
    pub total_count: i64,
}

// Models
#[derive(Debug, Deserialize, Clone)]
pub struct OllamaModel {
    pub name: String,
    pub size: i64,
    pub modified_at: String,
    pub family: Option<String>,
    pub parameter_size: Option<String>,
}

#[derive(Debug, Deserialize, Clone)]
pub struct ModelsResponse {
    pub embedding_models: Vec<OllamaModel>,
    pub chat_models: Vec<OllamaModel>,
    pub current_embedding_model: String,
    pub current_chat_model: String,
}

// Sessions
#[derive(Debug, Deserialize, Clone)]
pub struct SessionResponse {
    pub session_id: String,
    pub title: Option<String>,
    pub summary: Option<String>,
}

#[derive(Debug, Deserialize, Clone)]
pub struct SessionListResponse {
    pub sessions: Vec<SessionResponse>,
}

#[derive(Debug, Deserialize, Clone)]
pub struct SessionTurnResponse {
    pub turn_id: String,
    pub turn_number: i32,
    pub user_query: String,
    pub rewritten_query: Option<String>,
    pub response_text: String,
}

#[derive(Debug, Deserialize, Clone)]
pub struct SessionTurnListResponse {
    pub turns: Vec<SessionTurnResponse>,
}

// Knowledge Graph (for future API endpoints)
#[derive(Debug, Deserialize, Clone)]
pub struct KgEntity {
    pub entity_id: String,
    pub entity_name: String,
    pub entity_type: String,
    pub description: Option<String>,
    pub mention_count: i32,
}

#[derive(Debug, Deserialize, Clone)]
pub struct KgRelationship {
    pub rel_id: String,
    pub source_id: String,
    pub target_id: String,
    pub rel_type: String,
    pub weight: f64,
}

#[derive(Debug, Deserialize, Clone)]
pub struct KgNeighborhood {
    pub entity: KgEntity,
    pub neighbors: Vec<KgEntity>,
    pub relationships: Vec<KgRelationship>,
}

#[derive(Debug, Deserialize, Clone)]
pub struct KgEntityListResponse {
    pub entities: Vec<KgEntity>,
    pub total_count: i64,
}

// Feedback
#[derive(Debug, Deserialize, Clone)]
pub struct FeedbackStatsResponse {
    pub total_feedback: i64,
    pub avg_rating: f64,
    pub total_chunk_feedback: i64,
    pub total_answer_feedback: i64,
}

// Eval
#[derive(Debug, Deserialize, Clone)]
pub struct EvalRunResponse {
    pub run_id: String,
    pub eval_mode: String,
    pub avg_faithfulness: Option<f64>,
    pub avg_relevance: Option<f64>,
    pub avg_context_precision: Option<f64>,
    pub avg_context_recall: Option<f64>,
    pub total_pairs: i32,
}

#[derive(Debug, Deserialize, Clone)]
pub struct EvalRunListResponse {
    pub runs: Vec<EvalRunResponse>,
}

// Document chunks (for future API endpoint)
#[derive(Debug, Deserialize, Clone)]
pub struct ChunkDetailResponse {
    pub chunk_id: String,
    pub chunk_number: i32,
    pub text: String,
    pub token_count: i32,
    pub character_count: i32,
}

#[derive(Debug, Deserialize, Clone)]
pub struct ChunkListResponse {
    pub chunks: Vec<ChunkDetailResponse>,
    pub total_count: i64,
}

// Latency (for future API endpoint)
#[derive(Debug, Deserialize, Clone)]
pub struct LatencyDataPoint {
    pub query_id: String,
    pub total_time_ms: f64,
    pub search_time_ms: f64,
    pub generation_time_ms: f64,
}

#[derive(Debug, Deserialize, Clone)]
pub struct LatencyResponse {
    pub data_points: Vec<LatencyDataPoint>,
}
