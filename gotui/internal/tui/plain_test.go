package tui

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/jasperan/ragcli/gotui/internal/api"
	"github.com/jasperan/ragcli/gotui/internal/session"
)

// ACCESSIBLE mode is verified by a BOUNDED shell run, not from this suite.
//
// huh's accessible rendering only exists inside Form.Run, and Run loops back to
// the same prompt when its reader hits EOF. A strings.Reader therefore never
// terminates the form, and an in-suite test of it hangs the package (each of
// the three tests that tried it had to be killed at 20s). The run that does
// prove it is in the report:
//
//	printf 'http://127.0.0.1:8000\nn\n8000\n\n\n\n' | ACCESSIBLE=1 timeout 30 ./ragcli-tui
//
// which prints the plain prompts (Service URL, [y/N] confirms, a numbered
// "Enter a number between 1 and 5:" list for the similarity Select) and then
// continues into the question form. What is asserted here instead is the part
// that can be checked without blocking: the answers -> settings mapping.

func TestConnectAnswersMapToSettings(t *testing.T) {
	answers := ConnectAnswers{
		BaseURL:      "https://rag.example:9443/",
		LaunchServer: true,
		Port:         "9443",
		OracleUser:   "ORACLEUSER",
		OracleDSN:    "mydb:1521/XEPDB1",
	}

	settings := answers.toSettings()
	if settings.BaseURL != "https://rag.example:9443/" {
		t.Fatalf("BaseURL = %q", settings.BaseURL)
	}
	if !settings.LaunchServer || settings.Port != 9443 {
		t.Fatalf("unexpected launch settings: %+v", settings)
	}
	if settings.OracleUser != "ORACLEUSER" || settings.OracleDSN != "mydb:1521/XEPDB1" {
		t.Fatalf("unexpected Oracle settings: %+v", settings)
	}
}

// TestConnectAnswersFillDocumentedDefaults keeps the accessible path free of
// blank-setting surprises: a skipped optional field cannot become an empty
// environment variable for the spawned service.
func TestConnectAnswersFillDocumentedDefaults(t *testing.T) {
	settings := ConnectAnswers{BaseURL: "   ", Port: "not a port"}.toSettings()

	if settings.BaseURL != api.DefaultBaseURL {
		t.Fatalf("BaseURL should fall back to the service default, got %q", settings.BaseURL)
	}
	if settings.Port != session.DefaultPort {
		t.Fatalf("Port should fall back to the default, got %d", settings.Port)
	}
	if settings.OracleUser != session.DefaultOracleUse {
		t.Fatalf("OracleUser should fall back to the default, got %q", settings.OracleUser)
	}
	if settings.OracleDSN != session.DefaultOracleDSN {
		t.Fatalf("OracleDSN should fall back to the default, got %q", settings.OracleDSN)
	}
}

// --- scripted actions --------------------------------------------------------------

func stubClient(t *testing.T, handler http.HandlerFunc) *api.Client {
	t.Helper()
	server := httptest.NewServer(handler)
	t.Cleanup(server.Close)
	return api.NewClient(server.URL)
}

func TestRunActionQueryPrintsTheAnswer(t *testing.T) {
	client := stubClient(t, func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{
			"response": "the stored answer",
			"chunks": []map[string]any{
				{"chunk_id": "c1", "text": "an excerpt", "similarity_score": 0.75, "chunk_number": 1},
			},
		})
	})

	var out bytes.Buffer
	err := RunAction(context.Background(), client, ActionRequest{
		Action: ActionQuery,
		Query:  "what?",
		TopK:   5,
	}, &out)
	if err != nil {
		t.Fatalf("RunAction: %v", err)
	}
	for _, want := range []string{"the stored answer", "1 chunk(s) retrieved", "0.750"} {
		if !strings.Contains(out.String(), want) {
			t.Fatalf("output missing %q:\n%s", want, out.String())
		}
	}
}

func TestRunActionQueryJSON(t *testing.T) {
	client := stubClient(t, func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{"response": "json answer", "chunks": []any{}})
	})

	var out bytes.Buffer
	if err := RunAction(context.Background(), client, ActionRequest{
		Action: ActionQuery, Query: "what?", TopK: 5, JSON: true,
	}, &out); err != nil {
		t.Fatalf("RunAction: %v", err)
	}

	var decoded map[string]any
	if err := json.Unmarshal(out.Bytes(), &decoded); err != nil {
		t.Fatalf("expected valid JSON, got %q: %v", out.String(), err)
	}
	if decoded["response"] != "json answer" {
		t.Fatalf("unexpected payload %v", decoded)
	}
}

// TestRunActionDeleteRefusesWithoutYes is the safety property: a delete can
// never happen because a prompt was skipped or a pipe was mistaken for consent.
func TestRunActionDeleteRefusesWithoutYes(t *testing.T) {
	called := false
	client := stubClient(t, func(w http.ResponseWriter, r *http.Request) {
		called = true
		_ = json.NewEncoder(w).Encode(map[string]any{"message": "deleted"})
	})

	err := RunAction(context.Background(), client, ActionRequest{
		Action: ActionDelete, DocID: "doc-1", Confirmed: false,
	}, &bytes.Buffer{})
	if err == nil {
		t.Fatal("expected a refusal")
	}
	if !strings.Contains(err.Error(), "--yes") {
		t.Fatalf("the refusal should name the flag that authorises it, got %q", err.Error())
	}
	if called {
		t.Fatal("the service must not be contacted without --yes")
	}
}

func TestRunActionDeleteWithYes(t *testing.T) {
	client := stubClient(t, func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodDelete {
			t.Errorf("expected DELETE, got %s", r.Method)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"message":     "Document 'alpha.md' deleted successfully",
			"document_id": "doc-1", "chunks_deleted": 4,
		})
	})

	var out bytes.Buffer
	err := RunAction(context.Background(), client, ActionRequest{
		Action: ActionDelete, DocID: "doc-1", Confirmed: true,
	}, &out)
	if err != nil {
		t.Fatalf("RunAction: %v", err)
	}
	if !strings.Contains(out.String(), "4 chunks deleted") {
		t.Fatalf("unexpected output %q", out.String())
	}
}

func TestRunActionDeleteNeedsAnID(t *testing.T) {
	client := api.NewClient(api.DefaultBaseURL)
	err := RunAction(context.Background(), client, ActionRequest{
		Action: ActionDelete, Confirmed: true,
	}, &bytes.Buffer{})
	if err == nil || !strings.Contains(err.Error(), "document id") {
		t.Fatalf("expected a missing-id error, got %v", err)
	}
}

func TestRunActionDocumentsAndStatus(t *testing.T) {
	client := stubClient(t, func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/api/documents":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"documents": []map[string]any{{
					"document_id": "d1", "filename": "alpha.md", "file_format": "md",
					"chunk_count": 4, "total_tokens": 100,
				}},
				"total_count": 1,
			})
		case "/api/status":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"healthy":  true,
				"database": map[string]string{"status": "up", "message": "ok"},
				"ollama":   map[string]string{"status": "up", "message": "ok"},
			})
		case "/api/stats":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"total_documents": 1, "total_vectors": 4, "total_tokens": 100,
				"embedding_dimension": 768,
			})
		default:
			http.NotFound(w, r)
		}
	})

	var docs bytes.Buffer
	if err := RunAction(context.Background(), client, ActionRequest{Action: ActionDocuments}, &docs); err != nil {
		t.Fatalf("documents: %v", err)
	}
	if !strings.Contains(docs.String(), "alpha.md") {
		t.Fatalf("unexpected documents output %q", docs.String())
	}

	var status bytes.Buffer
	if err := RunAction(context.Background(), client, ActionRequest{Action: ActionStatus}, &status); err != nil {
		t.Fatalf("status: %v", err)
	}
	for _, want := range []string{"healthy      true", "documents    1", "768"} {
		if !strings.Contains(status.String(), want) {
			t.Fatalf("status output missing %q:\n%s", want, status.String())
		}
	}
}

func TestRunActionUnknownAction(t *testing.T) {
	client := api.NewClient(api.DefaultBaseURL)
	err := RunAction(context.Background(), client, ActionRequest{Action: "teleport"}, &bytes.Buffer{})
	if err == nil || !strings.Contains(err.Error(), "unknown action") {
		t.Fatalf("expected an unknown-action error, got %v", err)
	}
}

func TestParseActionFlagsPrecedence(t *testing.T) {
	// The most specific flag wins, so a read flag cannot mask a delete.
	action, ok := ParseActionFlags("", "doc-1", "", true, true)
	if !ok || action != ActionDelete {
		t.Fatalf("expected delete to win, got %q (%v)", action, ok)
	}
	action, ok = ParseActionFlags("", "", "/tmp/a.md", false, true)
	if !ok || action != ActionUpload {
		t.Fatalf("expected upload to win, got %q (%v)", action, ok)
	}
	action, ok = ParseActionFlags("q", "", "", true, true)
	if !ok || action != ActionQuery {
		t.Fatalf("expected query to win, got %q (%v)", action, ok)
	}
	action, ok = ParseActionFlags("", "", "", true, true)
	if !ok || action != ActionStatus {
		t.Fatalf("expected status to win, got %q (%v)", action, ok)
	}
	action, ok = ParseActionFlags("", "", "", false, true)
	if !ok || action != ActionDocuments {
		t.Fatalf("expected documents to win, got %q (%v)", action, ok)
	}
	if _, ok := ParseActionFlags("", "", "", false, false); ok {
		t.Fatal("no flags should mean no scripted action")
	}
}
