package api

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
)

// newTestClient points a client at a stub service. Nothing in this file needs a
// live ragcli service, Ollama or Oracle: the offline path is the default path.
func newTestClient(t *testing.T, handler http.HandlerFunc) *Client {
	t.Helper()
	server := httptest.NewServer(handler)
	t.Cleanup(server.Close)
	return NewClient(server.URL)
}

func TestStatusDecodes(t *testing.T) {
	client := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/status" {
			t.Errorf("unexpected path %s", r.URL.Path)
		}
		writeJSON(t, w, map[string]any{
			"healthy":  true,
			"database": map[string]string{"status": "up", "message": "26ai reachable"},
			"ollama":   map[string]string{"status": "up", "message": "models loaded"},
		})
	})

	status, err := client.Status(context.Background())
	if err != nil {
		t.Fatalf("Status: %v", err)
	}
	if !status.Healthy || status.Database.Status != "up" || status.Ollama.Status != "up" {
		t.Fatalf("unexpected status %+v", status)
	}
}

func TestStatsDecodes(t *testing.T) {
	client := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		writeJSON(t, w, map[string]any{
			"total_documents":     7,
			"total_vectors":       128,
			"total_tokens":        4096,
			"embedding_dimension": 768,
			"index_type":          "HNSW",
		})
	})

	stats, err := client.Stats(context.Background())
	if err != nil {
		t.Fatalf("Stats: %v", err)
	}
	if stats.TotalDocuments != 7 || stats.TotalVectors != 128 || stats.EmbeddingDimension != 768 {
		t.Fatalf("unexpected stats %+v", stats)
	}
}

func TestDocumentsAsksForAPage(t *testing.T) {
	var query string
	client := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		query = r.URL.RawQuery
		writeJSON(t, w, map[string]any{
			"documents": []map[string]any{{
				"document_id": "doc-1", "filename": "notes.md", "file_format": "md",
				"file_size_bytes": 2048, "chunk_count": 3, "total_tokens": 512,
			}},
			"total_count": 1,
		})
	})

	page, err := client.Documents(context.Background(), 0, 0)
	if err != nil {
		t.Fatalf("Documents: %v", err)
	}
	if !strings.Contains(query, "limit=100") {
		t.Fatalf("expected a default limit in the query, got %q", query)
	}
	if len(page.Documents) != 1 || page.Documents[0].Filename != "notes.md" {
		t.Fatalf("unexpected documents %+v", page)
	}
}

func TestQueryRejectsEmptyQuestionBeforeCallingTheService(t *testing.T) {
	called := false
	client := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		called = true
		writeJSON(t, w, map[string]any{})
	})

	if _, err := client.Query(context.Background(), QueryRequest{Query: "   "}); err == nil {
		t.Fatal("expected an error for a blank question")
	}
	if called {
		t.Fatal("a blank question must not reach the service")
	}
}

func TestQuerySendsServerShapedBody(t *testing.T) {
	var body QueryRequest
	client := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Errorf("decode body: %v", err)
		}
		writeJSON(t, w, map[string]any{
			"response": "because the docs say so",
			"chunks": []map[string]any{{
				"chunk_id": "c1", "document_id": "doc-1", "text": "excerpt",
				"similarity_score": 0.81, "chunk_number": 1,
			}},
			"metrics": map[string]any{"latency_ms": 12.5},
		})
	})

	answer, err := client.Query(context.Background(), QueryRequest{
		Query:         "why?",
		TopK:          9,
		MinSimilarity: 0.75,
	})
	if err != nil {
		t.Fatalf("Query: %v", err)
	}
	if body.Query != "why?" || body.TopK != 9 || body.MinSimilarity != 0.75 {
		t.Fatalf("request did not carry the answers: %+v", body)
	}
	if answer.Response != "because the docs say so" || len(answer.Chunks) != 1 {
		t.Fatalf("unexpected answer %+v", answer)
	}
	if answer.Chunks[0].SimilarityScore != 0.81 {
		t.Fatalf("similarity not decoded: %+v", answer.Chunks[0])
	}
}

func TestDeleteEscapesTheDocumentID(t *testing.T) {
	var escpath string
	client := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		escpath = r.URL.EscapedPath()
		writeJSON(t, w, map[string]any{
			"message": "gone", "document_id": "doc/1", "chunks_deleted": 4,
		})
	})

	response, err := client.DeleteDocument(context.Background(), "doc/1")
	if err != nil {
		t.Fatalf("DeleteDocument: %v", err)
	}
	// A slash inside an id must not create a new path segment, or the service
	// would see a different route. Assert on the wire form: r.URL.Path is
	// already decoded by the time a handler sees it.
	if escpath != "/api/documents/doc%2F1" {
		t.Fatalf("document id was not escaped on the wire: %q", escpath)
	}
	if response.ChunksDeleted != 4 {
		t.Fatalf("unexpected response %+v", response)
	}
}

func TestDeleteRequiresAnID(t *testing.T) {
	client := NewClient(DefaultBaseURL)
	if _, err := client.DeleteDocument(context.Background(), "  "); err == nil {
		t.Fatal("expected an error for a blank document id")
	}
}

func TestUploadPostsMultipart(t *testing.T) {
	var (
		contentType string
		filename    string
	)
	client := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		contentType = r.Header.Get("Content-Type")
		if err := r.ParseMultipartForm(4 << 20); err != nil {
			t.Errorf("parse multipart: %v", err)
		}
		_, header, err := r.FormFile("file")
		if err != nil {
			t.Errorf("form file: %v", err)
		} else {
			filename = header.Filename
		}
		writeJSON(t, w, map[string]any{
			"document_id": "doc-9", "filename": "sample.md", "file_format": "md",
			"chunk_count": 2, "total_tokens": 30, "upload_time_ms": 5,
		})
	})

	path := t.TempDir() + "/sample.md"
	if err := os.WriteFile(path, []byte("# hello\n"), 0o644); err != nil {
		t.Fatalf("prepare file: %v", err)
	}

	response, err := client.UploadDocument(context.Background(), path)
	if err != nil {
		t.Fatalf("UploadDocument: %v", err)
	}
	if !strings.HasPrefix(contentType, "multipart/form-data") {
		t.Fatalf("expected multipart, got %q", contentType)
	}
	if filename != "sample.md" {
		t.Fatalf("expected the base filename, got %q", filename)
	}
	if response.DocumentID != "doc-9" || response.ChunkCount != 2 {
		t.Fatalf("unexpected response %+v", response)
	}
}

func TestUploadRejectsADirectory(t *testing.T) {
	client := NewClient(DefaultBaseURL)
	if _, err := client.UploadDocument(context.Background(), t.TempDir()); err == nil {
		t.Fatal("expected an error when the path is a directory")
	}
}

func TestHTTPErrorSurfacesFastAPIDetail(t *testing.T) {
	client := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNotFound)
		writeJSON(t, w, map[string]any{"detail": "Document not found"})
	})

	_, err := client.DeleteDocument(context.Background(), "missing")
	if err == nil {
		t.Fatal("expected an error")
	}
	if !strings.Contains(err.Error(), "Document not found") {
		t.Fatalf("the service's detail should be surfaced, got %q", err.Error())
	}
}

func TestHTTPErrorWithoutDetailStillExplainsItself(t *testing.T) {
	client := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		_, _ = w.Write([]byte("<html>boom</html>"))
	})

	_, err := client.Status(context.Background())
	if err == nil {
		t.Fatal("expected an error")
	}
	if !strings.Contains(err.Error(), "boom") {
		t.Fatalf("a non-JSON error body should still be quoted, got %q", err.Error())
	}
}

// TestUnreachableServiceIsClassified is the offline path that matters most in a
// sandbox: no service, and the error must be recognisable rather than a raw
// transport string the UI cannot act on.
func TestUnreachableServiceIsClassified(t *testing.T) {
	// Reserve a port, then close it so nothing is listening.
	server := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) {}))
	deadURL := server.URL
	server.Close()

	client := NewClient(deadURL)
	_, err := client.Status(context.Background())
	if err == nil {
		t.Fatal("expected an error when nothing is listening")
	}
	if !errors.Is(err, ErrUnreachable) {
		t.Fatalf("expected ErrUnreachable, got %v", err)
	}
}

func TestValidateBaseURL(t *testing.T) {
	valid := []string{"http://127.0.0.1:8000", "https://rag.internal", "http://localhost:8000/"}
	for _, raw := range valid {
		if err := ValidateBaseURL(raw); err != nil {
			t.Errorf("%q should be valid: %v", raw, err)
		}
	}

	invalid := []string{"", "   ", "127.0.0.1:8000", "ftp://host", "http://"}
	for _, raw := range invalid {
		if err := ValidateBaseURL(raw); err == nil {
			t.Errorf("%q should be rejected", raw)
		}
	}
}

// --- helpers -----------------------------------------------------------------------

func writeJSON(t *testing.T, w http.ResponseWriter, value any) {
	t.Helper()
	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(value); err != nil {
		t.Errorf("encode stub response: %v", err)
	}
}
