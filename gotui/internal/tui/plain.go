package tui

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"strings"
	"time"

	"github.com/jasperan/ragcli/gotui/internal/api"
	"github.com/jasperan/ragcli/gotui/internal/session"
)

// PlainOptions drive the non-full-screen path.
//
// This path is used when ACCESSIBLE is set and when stdin is not a terminal.
// It reuses the SAME form builders as the TUI, so the two front-ends cannot
// drift apart in what they ask or what they validate.
type PlainOptions struct {
	ProjectRoot string
	Settings    session.Settings
	Input       io.Reader
	Output      io.Writer
}

// RunPlainPrompts runs the whole accessible flow as ONE pass of plain prompts.
//
// One form, one read of the reader. huh's accessible Form.Run wraps the reader
// in its own scanner, which buffers ahead; a second form built over the same
// stdin therefore starts at EOF and returns empty answers for everything. That
// is why connection and question are two groups of a single form here rather
// than two sequential forms.
func RunPlainPrompts(opts PlainOptions) (session.Settings, string, QueryAnswers, error) {
	in, out := opts.Input, opts.Output
	if in == nil {
		in = os.Stdin
	}
	if out == nil {
		out = os.Stdout
	}

	answers := PlainAnswers{
		Connect: ConnectDefaults(opts.Settings),
		Query:   QueryDefaults(),
	}
	form := PlainForm(&answers, session.PasswordFromEnv() != "").
		WithInput(in).
		WithOutput(out)

	if err := form.Run(); err != nil {
		return session.Settings{}, "", QueryAnswers{}, err
	}

	password := answers.Connect.OraclePassword
	if password == "" {
		password = session.PasswordFromEnv()
	}
	return answers.Connect.toSettings(), password, answers.Query, nil
}

// StartServiceIfRequested honours the connection form's launch answer.
func StartServiceIfRequested(ctx context.Context, settings session.Settings, password, projectRoot string, out io.Writer) (*session.Server, error) {
	if !settings.LaunchServer {
		return nil, nil
	}
	fmt.Fprintf(out, "Starting ragcli API on port %d...\n", settings.Port)
	server, err := session.LaunchServer(ctx, projectRoot, settings.Port,
		session.ServerEnv(settings.OracleUser, password, settings.OracleDSN))
	if err != nil {
		return nil, err
	}
	if err := session.WaitForPort(ctx, "127.0.0.1", settings.Port, 45*time.Second); err != nil {
		server.Stop()
		return nil, err
	}
	return server, nil
}

// ActionRequest is a scripted, non-interactive request.
type ActionRequest struct {
	Action    string
	Query     string
	TopK      int
	MinSim    float64
	DocID     string
	Path      string
	Confirmed bool
	JSON      bool
}

// RunAction executes a scripted request and writes its result.
//
// Destructive work (delete) requires Confirmed, which only the --yes flag
// sets. A prompt is never the only route through a delete, and a pipe is never
// mistaken for consent.
func RunAction(ctx context.Context, client *api.Client, req ActionRequest, out io.Writer) error {
	switch req.Action {
	case ActionStatus:
		return runStatusAction(ctx, client, req, out)

	case ActionDocuments:
		return runDocumentsAction(ctx, client, req, out)

	case ActionQuery:
		answer, err := client.Query(ctx, api.QueryRequest{
			Query:         req.Query,
			TopK:          req.TopK,
			MinSimilarity: req.MinSim,
		})
		if err != nil {
			return err
		}
		if req.JSON {
			return writeJSON(out, answer)
		}
		fmt.Fprintln(out, answer.Response)
		fmt.Fprintln(out)
		fmt.Fprintf(out, "%d chunk(s) retrieved\n", len(answer.Chunks))
		for i, chunk := range answer.Chunks {
			fmt.Fprintf(out, "  %d. similarity %.3f  %s\n", i+1, chunk.SimilarityScore,
				Truncate(strings.ReplaceAll(chunk.Text, "\n", " "), 140))
		}
		return nil

	case ActionDelete:
		if !req.Confirmed {
			return errors.New("refusing to delete without --yes: deletion removes the document and all its chunks")
		}
		if strings.TrimSpace(req.DocID) == "" {
			return errors.New("delete needs a document id: --delete <doc_id> --yes")
		}
		response, err := client.DeleteDocument(ctx, req.DocID)
		if err != nil {
			return err
		}
		if req.JSON {
			return writeJSON(out, response)
		}
		fmt.Fprintf(out, "%s (%d chunks deleted)\n", response.Message, response.ChunksDeleted)
		return nil

	case ActionUpload:
		if strings.TrimSpace(req.Path) == "" {
			return errors.New("upload needs a path: --upload <file>")
		}
		response, err := client.UploadDocument(ctx, req.Path)
		if err != nil {
			return err
		}
		if req.JSON {
			return writeJSON(out, response)
		}
		fmt.Fprintf(out, "Uploaded %s as %s (%d chunks)\n", response.Filename,
			response.DocumentID, response.ChunkCount)
		return nil

	case "health":
		status, err := client.Status(ctx)
		if err != nil {
			return err
		}
		if req.JSON {
			return writeJSON(out, status)
		}
		fmt.Fprintf(out, "healthy=%t database=%s ollama=%s\n", status.Healthy,
			status.Database.Status, status.Ollama.Status)
		return nil
	}

	return fmt.Errorf("unknown action %q", req.Action)
}

func runStatusAction(ctx context.Context, client *api.Client, req ActionRequest, out io.Writer) error {
	status, err := client.Status(ctx)
	if err != nil {
		return err
	}
	stats, err := client.Stats(ctx)
	if err != nil {
		return err
	}
	if req.JSON {
		return writeJSON(out, map[string]any{"status": status, "stats": stats})
	}
	fmt.Fprintf(out, "healthy      %t\n", status.Healthy)
	fmt.Fprintf(out, "database     %s - %s\n", status.Database.Status, status.Database.Message)
	fmt.Fprintf(out, "ollama       %s - %s\n", status.Ollama.Status, status.Ollama.Message)
	fmt.Fprintf(out, "documents    %d\n", stats.TotalDocuments)
	fmt.Fprintf(out, "vectors      %d\n", stats.TotalVectors)
	fmt.Fprintf(out, "tokens       %d\n", stats.TotalTokens)
	fmt.Fprintf(out, "dimension    %d\n", stats.EmbeddingDimension)
	return nil
}

func runDocumentsAction(ctx context.Context, client *api.Client, req ActionRequest, out io.Writer) error {
	page, err := client.Documents(ctx, 200, 0)
	if err != nil {
		return err
	}
	if req.JSON {
		return writeJSON(out, page)
	}
	if len(page.Documents) == 0 {
		fmt.Fprintln(out, "No documents are stored yet.")
		return nil
	}
	fmt.Fprintf(out, "%d document(s)\n", page.TotalCount)
	for _, doc := range page.Documents {
		fmt.Fprintf(out, "  %s  %-8s %5d chunks  %s\n", doc.DocumentID, doc.FileFormat,
			doc.ChunkCount, doc.Filename)
	}
	return nil
}

// writeJSON emits an indented JSON document for scripting.
func writeJSON(out io.Writer, value any) error {
	encoded, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return fmt.Errorf("encode json: %w", err)
	}
	_, err = out.Write(append(encoded, '\n'))
	return err
}

// ParseActionFlags decides which scripted action a flag set requests.
//
// The order matters: the most specific flag wins so "--documents --delete x"
// cannot silently degrade into a read.
func ParseActionFlags(query, docID, uploadPath string, statusFlag, documentsFlag bool) (string, bool) {
	switch {
	case strings.TrimSpace(docID) != "":
		return ActionDelete, true
	case strings.TrimSpace(uploadPath) != "":
		return ActionUpload, true
	case strings.TrimSpace(query) != "":
		return ActionQuery, true
	case statusFlag:
		return ActionStatus, true
	case documentsFlag:
		return ActionDocuments, true
	}
	return "", false
}
