use anyhow::Result;
use reqwest::Client;
use serde_json::json;
use super::models::*;

pub struct ApiClient {
    client: Client,
    base_url: String,
}

impl ApiClient {
    pub fn new(port: u16) -> Self {
        Self {
            client: Client::new(),
            base_url: format!("http://localhost:{}", port),
        }
    }

    pub async fn health(&self) -> Result<SystemStatus> {
        Ok(self.client.get(format!("{}/api/status", self.base_url)).send().await?.json().await?)
    }

    pub async fn stats(&self) -> Result<SystemStats> {
        Ok(self.client.get(format!("{}/api/stats", self.base_url)).send().await?.json().await?)
    }

    pub async fn query(&self, query: &str, session_id: Option<&str>, top_k: i32, include_embeddings: bool) -> Result<QueryResponse> {
        let mut body = json!({"query": query, "top_k": top_k, "include_embeddings": include_embeddings});
        if let Some(sid) = session_id {
            body["session_id"] = json!(sid);
        }
        Ok(self.client.post(format!("{}/api/query", self.base_url)).json(&body).send().await?.json().await?)
    }

    pub async fn documents(&self, limit: i32, offset: i32) -> Result<DocumentListResponse> {
        Ok(self.client.get(format!("{}/api/documents?limit={}&offset={}", self.base_url, limit, offset)).send().await?.json().await?)
    }

    pub async fn delete_document(&self, doc_id: &str) -> Result<()> {
        self.client.delete(format!("{}/api/documents/{}", self.base_url, doc_id)).send().await?;
        Ok(())
    }

    pub async fn models(&self) -> Result<ModelsResponse> {
        Ok(self.client.get(format!("{}/api/models", self.base_url)).send().await?.json().await?)
    }

    pub async fn sessions(&self) -> Result<SessionListResponse> {
        Ok(self.client.get(format!("{}/api/sessions", self.base_url)).send().await?.json().await?)
    }

    pub async fn session_turns(&self, session_id: &str, limit: i32) -> Result<SessionTurnListResponse> {
        Ok(self.client.get(format!("{}/api/sessions/{}/turns?limit={}", self.base_url, session_id, limit)).send().await?.json().await?)
    }

    pub async fn feedback_stats(&self) -> Result<FeedbackStatsResponse> {
        Ok(self.client.get(format!("{}/api/feedback/stats", self.base_url)).send().await?.json().await?)
    }

    pub async fn eval_runs(&self) -> Result<EvalRunListResponse> {
        Ok(self.client.get(format!("{}/api/eval/runs", self.base_url)).send().await?.json().await?)
    }

    pub async fn kg_entities(&self, limit: i32, offset: i32) -> Result<KgEntityListResponse> {
        Ok(self.client.get(format!("{}/api/knowledge/entities?limit={}&offset={}", self.base_url, limit, offset)).send().await?.json().await?)
    }

    pub async fn kg_neighbors(&self, entity_id: &str) -> Result<KgNeighborhood> {
        Ok(self.client.get(format!("{}/api/knowledge/entities/{}/neighbors", self.base_url, entity_id)).send().await?.json().await?)
    }

    pub async fn document_chunks(&self, doc_id: &str, limit: i32, offset: i32) -> Result<ChunkListResponse> {
        Ok(self.client.get(format!("{}/api/documents/{}/chunks?limit={}&offset={}", self.base_url, doc_id, limit, offset)).send().await?.json().await?)
    }

    pub async fn latency_stats(&self, limit: i32) -> Result<LatencyResponse> {
        Ok(self.client.get(format!("{}/api/stats/latency?limit={}", self.base_url, limit)).send().await?.json().await?)
    }
}
