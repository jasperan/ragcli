package api

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// DefaultBaseURL is where ragcli's FastAPI service listens by default
// (ragcli/api/server.py:start_server defaults to 127.0.0.1:8000).
const DefaultBaseURL = "http://127.0.0.1:8000"

// ErrUnreachable reports that the service could not be contacted at all. It is
// distinct from an HTTP error status so the UI can say "start the server"
// instead of showing a stack trace.
var ErrUnreachable = errors.New("ragcli API unreachable")

// Client is a read-mostly client for the ragcli FastAPI service.
type Client struct {
	baseURL string
	http    *http.Client
}

// NewClient builds a client for baseURL. A trailing slash is tolerated.
func NewClient(baseURL string) *Client {
	return &Client{
		baseURL: strings.TrimRight(baseURL, "/"),
		http:    &http.Client{Timeout: 120 * time.Second},
	}
}

// BaseURL returns the configured service root.
func (c *Client) BaseURL() string { return c.baseURL }

// ValidateBaseURL rejects anything that is not an absolute http(s) URL with a
// host, so a typo is caught in the form rather than at request time.
func ValidateBaseURL(raw string) error {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return errors.New("a base URL is required")
	}
	u, err := url.Parse(raw)
	if err != nil {
		return fmt.Errorf("not a valid URL: %w", err)
	}
	if u.Scheme != "http" && u.Scheme != "https" {
		return errors.New("use an http:// or https:// URL")
	}
	if u.Host == "" {
		return errors.New("the URL needs a host, for example 127.0.0.1:8000")
	}
	return nil
}

// do performs a request and decodes a JSON body into out.
func (c *Client) do(ctx context.Context, method, path string, body any, out any) error {
	var reader io.Reader
	if body != nil {
		encoded, err := json.Marshal(body)
		if err != nil {
			return fmt.Errorf("encode request: %w", err)
		}
		reader = bytes.NewReader(encoded)
	}

	req, err := http.NewRequestWithContext(ctx, method, c.baseURL+path, reader)
	if err != nil {
		return fmt.Errorf("build request: %w", err)
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	resp, err := c.http.Do(req)
	if err != nil {
		return fmt.Errorf("%w: %v", ErrUnreachable, err)
	}
	defer resp.Body.Close()

	payload, err := io.ReadAll(io.LimitReader(resp.Body, 32<<20))
	if err != nil {
		return fmt.Errorf("read response: %w", err)
	}

	if resp.StatusCode < 200 || resp.StatusCode > 299 {
		return fmt.Errorf("%s %s: HTTP %d: %s", method, path, resp.StatusCode, detail(payload))
	}

	if out == nil {
		return nil
	}
	if err := json.Unmarshal(payload, out); err != nil {
		return fmt.Errorf("decode %s body: %w", path, err)
	}
	return nil
}

// detail pulls FastAPI's {"detail": ...} string, falling back to a truncated
// body so an unexpected error page is still diagnosable.
func detail(payload []byte) string {
	var envelope struct {
		Detail any `json:"detail"`
	}
	if err := json.Unmarshal(payload, &envelope); err == nil && envelope.Detail != nil {
		if s, ok := envelope.Detail.(string); ok {
			return s
		}
		if encoded, err := json.Marshal(envelope.Detail); err == nil {
			return string(encoded)
		}
	}
	trimmed := strings.TrimSpace(string(payload))
	if len(trimmed) > 300 {
		trimmed = trimmed[:300] + "..."
	}
	if trimmed == "" {
		return "(empty response)"
	}
	return trimmed
}

// Status calls GET /api/status.
func (c *Client) Status(ctx context.Context) (*SystemStatus, error) {
	var out SystemStatus
	if err := c.do(ctx, http.MethodGet, "/api/status", nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Stats calls GET /api/stats.
func (c *Client) Stats(ctx context.Context) (*SystemStats, error) {
	var out SystemStats
	if err := c.do(ctx, http.MethodGet, "/api/stats", nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Documents calls GET /api/documents.
func (c *Client) Documents(ctx context.Context, limit, offset int) (*DocumentListResponse, error) {
	if limit <= 0 {
		limit = 100
	}
	var out DocumentListResponse
	path := fmt.Sprintf("/api/documents?limit=%d&offset=%d", limit, offset)
	if err := c.do(ctx, http.MethodGet, path, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Models calls GET /api/models.
func (c *Client) Models(ctx context.Context) (*ModelsResponse, error) {
	var out ModelsResponse
	if err := c.do(ctx, http.MethodGet, "/api/models", nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Query calls POST /api/query.
func (c *Client) Query(ctx context.Context, req QueryRequest) (*QueryResponse, error) {
	if strings.TrimSpace(req.Query) == "" {
		return nil, errors.New("the question is empty")
	}
	if req.TopK <= 0 {
		req.TopK = 5
	}
	var out QueryResponse
	if err := c.do(ctx, http.MethodPost, "/api/query", req, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// DeleteDocument calls DELETE /api/documents/{doc_id}.
func (c *Client) DeleteDocument(ctx context.Context, docID string) (*DeleteResponse, error) {
	if strings.TrimSpace(docID) == "" {
		return nil, errors.New("a document id is required")
	}
	var out DeleteResponse
	if err := c.do(ctx, http.MethodDelete, "/api/documents/"+url.PathEscape(docID), nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// UploadDocument calls POST /api/documents/upload with a multipart body.
func (c *Client) UploadDocument(ctx context.Context, filePath string) (*DocumentUploadResponse, error) {
	info, err := os.Stat(filePath)
	if err != nil {
		return nil, fmt.Errorf("cannot read %s: %w", filePath, err)
	}
	if info.IsDir() {
		return nil, fmt.Errorf("%s is a directory", filePath)
	}

	file, err := os.Open(filePath)
	if err != nil {
		return nil, fmt.Errorf("cannot open %s: %w", filePath, err)
	}
	defer file.Close()

	var body bytes.Buffer
	writer := multipart.NewWriter(&body)
	part, err := writer.CreateFormFile("file", filepath.Base(filePath))
	if err != nil {
		return nil, fmt.Errorf("build upload: %w", err)
	}
	if _, err := io.Copy(part, file); err != nil {
		return nil, fmt.Errorf("read %s: %w", filePath, err)
	}
	if err := writer.Close(); err != nil {
		return nil, fmt.Errorf("build upload: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+"/api/documents/upload", &body)
	if err != nil {
		return nil, fmt.Errorf("build request: %w", err)
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())

	resp, err := c.http.Do(req)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrUnreachable, err)
	}
	defer resp.Body.Close()

	payload, err := io.ReadAll(io.LimitReader(resp.Body, 32<<20))
	if err != nil {
		return nil, fmt.Errorf("read response: %w", err)
	}
	if resp.StatusCode < 200 || resp.StatusCode > 299 {
		return nil, fmt.Errorf("upload: HTTP %d: %s", resp.StatusCode, detail(payload))
	}

	var out DocumentUploadResponse
	if err := json.Unmarshal(payload, &out); err != nil {
		return nil, fmt.Errorf("decode upload body: %w", err)
	}
	return &out, nil
}
