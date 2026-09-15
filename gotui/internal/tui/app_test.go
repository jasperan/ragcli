package tui

import (
	"strings"
	"testing"

	"charm.land/bubbletea/v2"
	"charm.land/huh/v2"
	"github.com/jasperan/ragcli/gotui/internal/api"
	"github.com/jasperan/ragcli/gotui/internal/session"
)

// These tests drive the model by handing it messages directly. They never drain
// tea.Cmd, because huh re-arms the text input's cursor blink on every update and
// each blink tick sleeps for about half a second; a naive drain makes the suite
// hang. Commands are inspected for their type instead.

func testOptions(t *testing.T) Options {
	t.Helper()
	t.Setenv("XDG_CONFIG_HOME", t.TempDir())
	t.Setenv("HOME", t.TempDir())
	return Options{ProjectRoot: t.TempDir(), Settings: session.Defaults()}
}

func TestNewStartsOnTheConnectForm(t *testing.T) {
	model := New(testOptions(t))
	// Render the way a running program does. huh only builds a group's view
	// once Form.Init has activated it, and it is Init that the bubbletea
	// runtime calls before the first paint.
	_ = model.Init()
	_, _ = model.Update(tea.WindowSizeMsg{Width: 100, Height: 30})

	if model.screen != ScreenConnect {
		t.Fatalf("expected the connect screen, got %v", model.screen)
	}
	if model.form == nil {
		t.Fatal("the connect form must be built up front")
	}
	if model.form.State != huh.StateNormal {
		t.Fatalf("expected a normal form state, got %v", model.form.State)
	}
	if view := model.View().Content; !strings.Contains(view, "Service URL") {
		t.Fatalf("the connect form should render its first question, got %q", view)
	}
}

// TestKeyReleaseDoesNotAdvanceTheForm pins the bubbletea v2 press/release bug:
// handling both would fire every binding twice per keystroke.
func TestKeyReleaseDoesNotAdvanceTheForm(t *testing.T) {
	model := New(testOptions(t))

	_, _ = model.Update(tea.KeyReleaseMsg{Code: 'a'})
	if model.form == nil {
		t.Fatal("a key release must not complete or clear the form")
	}

	_, _ = model.Update(tea.KeyPressMsg{Code: 'q', Text: "q"})
	if model.screen != ScreenConnect {
		t.Fatalf("typing must stay on the connect screen, got %v", model.screen)
	}
}

func TestStatusResultDoesNotPanicAndRenders(t *testing.T) {
	model := New(testOptions(t))
	model.screen = ScreenStatus
	model.busy = "Loading status"

	_, _ = model.Update(statusLoadedMsg{
		status: &api.SystemStatus{
			Healthy:  true,
			Database: api.ComponentStatus{Status: "up", Message: "26ai reachable"},
			Ollama:   api.ComponentStatus{Status: "down", Message: "not running"},
		},
		stats: &api.SystemStats{TotalDocuments: 3, TotalVectors: 12, EmbeddingDimension: 768},
	})

	model.notice = ""
	view := model.View().Content
	for _, want := range []string{"Service status", "26ai reachable", "not running", "768"} {
		if !strings.Contains(view, want) {
			t.Fatalf("status view is missing %q:\n%s", want, view)
		}
	}
	if model.form == nil {
		t.Fatal("the readout must hand control back with a form")
	}
}

// TestUnreachableServiceShowsAnActionableError is the default path in a sandbox:
// nothing is listening, and the UI must explain that instead of freezing.
func TestUnreachableServiceShowsAnActionableError(t *testing.T) {
	model := New(testOptions(t))
	model.screen = ScreenStatus
	model.busy = "Loading status"

	_, _ = model.Update(statusLoadedMsg{err: api.ErrUnreachable})

	if model.failure == nil {
		t.Fatal("expected a failure to be recorded")
	}
	if !strings.Contains(model.failure.Error(), "start the service") {
		t.Fatalf("the error should tell the user what to do, got %q", model.failure.Error())
	}
	view := model.View().Content
	if !strings.Contains(view, "Problem") {
		t.Fatalf("the error should be rendered: %q", view)
	}
}

func TestDocumentsLoadSwitchesScreenAndOptions(t *testing.T) {
	model := New(testOptions(t))
	model.screen = ScreenDocuments

	docs := []api.DocumentInfo{
		{DocumentID: "d1", Filename: "alpha.md", FileFormat: "md", ChunkCount: 4},
		{DocumentID: "d2", Filename: "beta.pdf", FileFormat: "pdf", ChunkCount: 9},
	}
	_, _ = model.Update(documentsLoadedMsg{documents: docs})

	if model.screen != ScreenDocuments {
		t.Fatalf("expected the documents screen, got %v", model.screen)
	}
	if len(model.documents) != 2 {
		t.Fatalf("expected both documents, got %d", len(model.documents))
	}
	if model.form == nil {
		t.Fatal("the documents form must be rebuilt after a load")
	}
	view := model.View().Content
	for _, want := range []string{"alpha.md", "beta.pdf"} {
		if !strings.Contains(view, want) {
			t.Fatalf("documents view is missing %q:\n%s", want, view)
		}
	}
}

func TestQueryResultSwitchesToTheContinuePrompt(t *testing.T) {
	model := New(testOptions(t))
	model.screen = ScreenResult

	_, _ = model.Update(queryDoneMsg{answer: &api.QueryResponse{
		Response: "the answer",
		Chunks:   []api.ChunkResult{{ChunkID: "c1", Text: "excerpt", SimilarityScore: 0.9}},
	}})

	if model.screen != ScreenResult {
		t.Fatalf("expected to stay on the result screen, got %v", model.screen)
	}
	if model.form == nil {
		t.Fatal("a continue prompt is required, otherwise the model has no way on")
	}
	view := model.View().Content
	for _, want := range []string{"the answer", "Retrieved chunks", "0.900"} {
		if !strings.Contains(view, want) {
			t.Fatalf("answer view is missing %q:\n%s", want, view)
		}
	}
}

func TestFailedQueryReturnsToTheQueryForm(t *testing.T) {
	model := New(testOptions(t))
	model.screen = ScreenResult

	_, _ = model.Update(queryDoneMsg{err: api.ErrUnreachable})

	if model.screen != ScreenQuery {
		t.Fatalf("a failed query should return to the query form, got %v", model.screen)
	}
	if model.form == nil {
		t.Fatal("the query form must be restored so the user can retry")
	}
}

func TestFinishMenuRoutesEveryAction(t *testing.T) {
	cases := map[string]Screen{
		ActionQuery:     ScreenQuery,
		ActionDocuments: ScreenDocuments,
		ActionStatus:    ScreenStatus,
		ActionReconnect: ScreenConnect,
	}

	for action, want := range cases {
		model := New(testOptions(t))
		model.screen = ScreenMenu
		model.menu = action

		cmd := model.finishMenu()
		if model.screen != want {
			t.Fatalf("action %q: expected screen %v, got %v", action, want, model.screen)
		}
		if cmd == nil && action != ActionQuit {
			t.Fatalf("action %q should schedule work", action)
		}
	}
}

func TestDeleteNeedsTheExactFilenameTyped(t *testing.T) {
	doc := api.DocumentInfo{DocumentID: "d1", Filename: "alpha.md", ChunkCount: 4}

	if err := DeleteConfirmationValidator(doc)("alpha.md"); err != nil {
		t.Fatalf("the exact filename should be accepted: %v", err)
	}
	if err := DeleteConfirmationValidator(doc)("beta.md"); err == nil {
		t.Fatal("a mismatched filename must be rejected")
	}
	if err := DeleteConfirmationValidator(doc)("  alpha.md  "); err != nil {
		t.Fatalf("surrounding whitespace should be tolerated: %v", err)
	}
}

func TestDeleteFormRenderNamesBothFilenameAndChunks(t *testing.T) {
	model := New(testOptions(t))
	model.documents = []api.DocumentInfo{{DocumentID: "d1", Filename: "alpha.md", ChunkCount: 4}}
	model.docs = DocumentAnswers{DocumentID: "d1", Action: ActionDelete}
	model.screen = ScreenDocuments

	cmd := model.finishDocuments()
	if cmd == nil {
		t.Fatal("selecting delete should schedule the confirmation")
	}
	if model.screen != ScreenDelete {
		t.Fatalf("expected the delete screen, got %v", model.screen)
	}
	view := model.View().Content
	for _, want := range []string{"alpha.md", "4 chunks"} {
		if !strings.Contains(view, want) {
			t.Fatalf("the confirmation must state what is destroyed, missing %q:\n%s", want, view)
		}
	}
}

func TestDeclinedDeleteDoesNotScheduleAnything(t *testing.T) {
	model := New(testOptions(t))
	model.screen = ScreenDelete
	model.docs = DocumentAnswers{DocumentID: "d1", Action: ActionDelete}
	model.confirm = ConfirmAnswers{Confirmed: false}
	model.form = DeleteForm(&model.confirm, api.DocumentInfo{DocumentID: "d1", Filename: "alpha.md"})

	cmd := model.advance()
	if cmd == nil {
		t.Fatal("declining should still refresh the list, not stall")
	}
	if model.screen != ScreenDocuments {
		t.Fatalf("expected to return to documents, got %v", model.screen)
	}
}

func TestChunksLoadedHandsControlBack(t *testing.T) {
	model := New(testOptions(t))
	model.screen = ScreenStatus
	model.busy = "Loading chunks"

	_, _ = model.Update(chunksLoadedMsg{chunks: []api.ChunkResult{{ChunkID: "c1", Text: "body"}}})

	if model.form == nil {
		t.Fatal("the readout must be continuable after loading chunks")
	}
	if !strings.Contains(model.View().Content, "body") {
		t.Fatal("the loaded chunks should be rendered")
	}
}

func TestWindowResizeIsTolerated(t *testing.T) {
	model := New(testOptions(t))

	for _, size := range []tea.WindowSizeMsg{{Width: 200, Height: 60}, {Width: 24, Height: 10}} {
		_, _ = model.Update(size)
		if view := model.View().Content; view == "" {
			t.Fatalf("a %dx%d window rendered nothing", size.Width, size.Height)
		}
	}
}

func TestNoticeIsClearedOnTheNextKey(t *testing.T) {
	model := New(testOptions(t))
	model.notice = "Uploaded alpha.md"

	_, _ = model.Update(tea.KeyPressMsg{Code: 'a', Text: "a"})

	if model.notice != "" {
		t.Fatalf("the notice should clear on the next keystroke, got %q", model.notice)
	}
}

func TestCloseStopsAStartedService(t *testing.T) {
	model := New(testOptions(t))
	model.Close()
	if model.server != nil {
		t.Fatal("Close should clear any service handle")
	}
}
