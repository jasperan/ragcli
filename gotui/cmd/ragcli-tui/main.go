// Command ragcli-tui is an additional way to run ragcli: a Go front-end in the
// charm v2 + huh stack that talks to the same FastAPI service the Python CLI
// and the Rust TUI already use.
//
// It never reimplements retrieval. Every answer comes from the service, so a Go
// user and a Python user get identical results.
package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"charm.land/bubbletea/v2"
	"github.com/jasperan/ragcli/gotui/internal/api"
	"github.com/jasperan/ragcli/gotui/internal/huhstyle"
	"github.com/jasperan/ragcli/gotui/internal/session"
	"github.com/jasperan/ragcli/gotui/internal/tui"
)

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, "ragcli-tui: "+err.Error())
		os.Exit(1)
	}
}

func run() error {
	var (
		baseURL     = flag.String("base-url", "", "ragcli service URL (default from saved settings or 127.0.0.1:8000)")
		port        = flag.Int("port", 0, "port for the service started with --start-service")
		startSvc    = flag.Bool("start-service", false, "start the repo's own API service (uv run ragcli api) before connecting")
		oracleUser  = flag.String("oracle-user", "", "Oracle user for the started service (env: "+session.EnvOracleUsername+")")
		oracleDSN   = flag.String("oracle-dsn", "", "Oracle DSN for the started service (env: "+session.EnvOracleDSN+")")
		projectRoot = flag.String("project-root", "", "ragcli checkout used to start the service (default: this binary's repo)")

		queryFlag   = flag.String("query", "", "ask one question and print the answer, then exit")
		topK        = flag.Int("top-k", 5, "chunks to retrieve for --query")
		minSim      = flag.Float64("min-similarity", 0.5, "minimum similarity for --query")
		documents   = flag.Bool("documents", false, "list documents, then exit")
		statusFlag  = flag.Bool("status", false, "print service status and corpus statistics, then exit")
		healthFlag  = flag.Bool("health", false, "print a one-line health summary, then exit")
		deleteFlag  = flag.String("delete", "", "delete a document by id (requires --yes)")
		uploadFlag  = flag.String("upload", "", "upload a file (TXT, MD or PDF)")
		yesFlag     = flag.Bool("yes", false, "confirm a destructive --delete without prompting")
		jsonFlag    = flag.Bool("json", false, "emit machine-readable JSON for scripted actions")
		noInputFlag = flag.Bool("no-input", false, "never prompt; fail instead if input is required")
	)
	flag.Parse()

	settings, err := session.Load()
	if err != nil {
		fmt.Fprintln(os.Stderr, "note: "+err.Error())
	}
	if *baseURL != "" {
		if err := api.ValidateBaseURL(*baseURL); err != nil {
			return fmt.Errorf("--base-url: %w", err)
		}
		settings.BaseURL = strings.TrimRight(strings.TrimSpace(*baseURL), "/")
	}
	if *port != 0 {
		if err := session.ValidatePort(fmt.Sprint(*port)); err != nil {
			return fmt.Errorf("--port: %w", err)
		}
		settings.Port = *port
	}
	if *oracleUser != "" {
		settings.OracleUser = *oracleUser
	}
	if *oracleDSN != "" {
		settings.OracleDSN = *oracleDSN
	}
	if *startSvc {
		settings.LaunchServer = true
	}

	root := *projectRoot
	if root == "" {
		root = defaultProjectRoot()
	}

	// --- scripted path -----------------------------------------------------------
	// This runs before any prompt is considered, so a pipeline never blocks on
	// a question.
	actionFlag, statusAction := tui.ParseActionFlags(*queryFlag, *deleteFlag, *uploadFlag, *statusFlag, *documents)
	if *healthFlag {
		actionFlag, statusAction = "health", true
	}
	if statusAction {
		client := api.NewClient(settings.BaseURL)
		var server *session.Server
		if settings.LaunchServer {
			server, err = tui.StartServiceIfRequested(context.Background(), settings,
				session.PasswordFromEnv(), root, os.Stdout)
			if err != nil {
				return err
			}
			defer server.Stop()
		}
		action := tui.ActionRequest{
			Action:    actionFlag,
			Query:     *queryFlag,
			TopK:      *topK,
			MinSim:    *minSim,
			DocID:     *deleteFlag,
			Path:      *uploadFlag,
			Confirmed: *yesFlag,
			JSON:      *jsonFlag,
		}
		if err := tui.RunAction(context.Background(), client, action, os.Stdout); err != nil {
			return err
		}
		return nil
	}

	// --- screen-reader / piped path ---------------------------------------------
	// huh's accessible rendering only exists in its standalone Run path, so the
	// embedded full-screen UI is skipped entirely here.
	if huhstyle.Accessible() {
		fmt.Fprintln(os.Stdout, tui.AccessibleNotice)
		return runPlain(settings, root, *noInputFlag)
	}
	if !huhstyle.Interactive() || *noInputFlag {
		return errors.New("no terminal on stdin: pass an action flag such as --status, --documents, --query \"...\", --upload <file> or --delete <id> --yes (or set ACCESSIBLE for plain prompts)")
	}

	// --- full-screen path --------------------------------------------------------
	model := tui.New(tui.Options{ProjectRoot: root, Settings: settings})
	defer model.Close()

	program := tea.NewProgram(model)
	if _, err := program.Run(); err != nil {
		return err
	}
	return nil
}

// runPlain drives the same forms as plain prompts.
func runPlain(settings session.Settings, root string, noInput bool) error {
	if noInput {
		return errors.New("-no-input cannot be combined with ACCESSIBLE plain prompts")
	}

	ctx := context.Background()
	chosen, password, answers, err := tui.RunPlainPrompts(tui.PlainOptions{
		ProjectRoot: root,
		Settings:    settings,
		Input:       os.Stdin,
		Output:      os.Stdout,
	})
	if err != nil {
		return err
	}
	if err := session.Save(chosen); err != nil {
		fmt.Fprintln(os.Stderr, "note: "+err.Error())
	}

	server, err := tui.StartServiceIfRequested(ctx, chosen, password, root, os.Stdout)
	if err != nil {
		return err
	}
	if server != nil {
		defer server.Stop()
	}

	client := api.NewClient(chosen.BaseURL)
	if strings.TrimSpace(answers.Question) == "" {
		return errors.New("the connection was saved, but huh's accessible form did not deliver the question " +
			"field (known limitation, see docs). The connection is stored, so run: ragcli-tui --query \"your question\"")
	}
	return tui.RunAction(ctx, client, tui.ActionRequest{
		Action: tui.ActionQuery,
		Query:  answers.Question,
		TopK:   tui.ParseTopK(answers.TopK),
		MinSim: tui.ParseMinSimilarity(answers.MinSimilarity),
	}, os.Stdout)
}

// defaultProjectRoot finds the checkout so the service can be started from it.
// The binary may be built anywhere, so this walks up from the executable and
// falls back to the working directory.
func defaultProjectRoot() string {
	if wd, err := os.Getwd(); err == nil {
		if looksLikeRagcli(wd) {
			return wd
		}
	}
	executable, err := os.Executable()
	if err == nil {
		dir := filepath.Dir(executable)
		for i := 0; i < 6; i++ {
			if looksLikeRagcli(dir) {
				return dir
			}
			parent := filepath.Dir(dir)
			if parent == dir {
				break
			}
			dir = parent
		}
	}
	wd, _ := os.Getwd()
	return wd
}

// looksLikeRagcli reports whether dir is the ragcli checkout by looking for the
// two things starting the service needs.
func looksLikeRagcli(dir string) bool {
	if dir == "" {
		return false
	}
	if _, err := os.Stat(filepath.Join(dir, "pyproject.toml")); err != nil {
		return false
	}
	if _, err := os.Stat(filepath.Join(dir, "ragcli", "api", "server.py")); err != nil {
		return false
	}
	return true
}
