// Package api is a peer client for the existing ragcli FastAPI service
// (ragcli/api/server.py). It mirrors the endpoint set the Rust TUI already
// consumes (ragcli/tui/src/api/client.rs) so that a Go user and a Rust user
// see the same answers.
//
// Nothing here reimplements retrieval: every method is a thin HTTP call.
package api

// ComponentStatus is one subsystem's readiness in SystemStatus.
type ComponentStatus struct {
	Status  string `json:"status"`
	Message string `json:"message"`
}

// SystemStatus is GET /api/status.
type SystemStatus struct {
	Healthy   bool            `json:"healthy"`
	Database  ComponentStatus `json:"database"`
	Ollama    ComponentStatus `json:"ollama"`
	Timestamp string          `json:"timestamp"`
}

// SystemStats is GET /api/stats.
type SystemStats struct {
	TotalDocuments     int64  `json:"total_documents"`
	TotalVectors       int64  `json:"total_vectors"`
	TotalTokens        int64  `json:"total_tokens"`
	EmbeddingDimension int64  `json:"embedding_dimension"`
	IndexType          string `json:"index_type"`
}

// DocumentInfo is one row of GET /api/documents.
type DocumentInfo struct {
	DocumentID    string `json:"document_id"`
	Filename      string `json:"filename"`
	FileFormat    string `json:"file_format"`
	FileSizeBytes int64  `json:"file_size_bytes"`
	ChunkCount    int32  `json:"chunk_count"`
	TotalTokens   int64  `json:"total_tokens"`
}

// DocumentListResponse is GET /api/documents.
type DocumentListResponse struct {
	Documents  []DocumentInfo `json:"documents"`
	TotalCount int64          `json:"total_count"`
}

// DocumentUploadResponse is POST /api/documents/upload.
type DocumentUploadResponse struct {
	DocumentID    string `json:"document_id"`
	Filename      string `json:"filename"`
	FileFormat    string `json:"file_format"`
	FileSizeBytes int64  `json:"file_size_bytes"`
	ChunkCount    int32  `json:"chunk_count"`
	TotalTokens   int64  `json:"total_tokens"`
	UploadTimeMS  int64  `json:"upload_time_ms"`
}

// ChunkResult is one retrieved chunk in QueryResponse.
type ChunkResult struct {
	ChunkID         string    `json:"chunk_id"`
	DocumentID      string    `json:"document_id"`
	Text            string    `json:"text"`
	SimilarityScore float64   `json:"similarity_score"`
	ChunkNumber     int32     `json:"chunk_number"`
	Embedding       []float64 `json:"embedding"`
}

// QueryResponse is POST /api/query. Metrics is left as raw JSON because the
// server owns that shape and the TUI only displays it.
type QueryResponse struct {
	Response  string         `json:"response"`
	Chunks    []ChunkResult  `json:"chunks"`
	Metrics   map[string]any `json:"metrics"`
	SessionID string         `json:"session_id"`
	TraceID   string         `json:"trace_id"`
}

// OllamaModel is one entry of ModelsResponse.
type OllamaModel struct {
	Name          string `json:"name"`
	Size          int64  `json:"size"`
	ModifiedAt    string `json:"modified_at"`
	Family        string `json:"family"`
	ParameterSize string `json:"parameter_size"`
}

// ModelsResponse is GET /api/models.
type ModelsResponse struct {
	EmbeddingModels       []OllamaModel `json:"embedding_models"`
	ChatModels            []OllamaModel `json:"chat_models"`
	CurrentEmbeddingModel string        `json:"current_embedding_model"`
	CurrentChatModel      string        `json:"current_chat_model"`
}

// DeleteResponse is DELETE /api/documents/{doc_id}.
type DeleteResponse struct {
	Message       string `json:"message"`
	DocumentID    string `json:"document_id"`
	ChunksDeleted int64  `json:"chunks_deleted"`
}

// QueryRequest is the POST /api/query body. Field names and bounds mirror
// ragcli/api/models.py:QueryRequest.
type QueryRequest struct {
	Query             string   `json:"query"`
	DocumentIDs       []string `json:"document_ids,omitempty"`
	TopK              int      `json:"top_k"`
	MinSimilarity     float64  `json:"min_similarity"`
	IncludeEmbeddings bool     `json:"include_embeddings"`
	SessionID         string   `json:"session_id,omitempty"`
}
