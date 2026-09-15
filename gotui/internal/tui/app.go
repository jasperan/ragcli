// Package tui is the Go front-end's terminal UI: a peer client of the ragcli
// FastAPI service, built on charm.land/bubbletea/v2 and charm.land/huh/v2.
package tui

import (
	"context"
	"errors"
	"strconv"
	"strings"
	"time"

	"charm.land/bubbletea/v2"
	"charm.land/huh/v2"
	"github.com/jasperan/ragcli/gotui/internal/api"
	"github.com/jasperan/ragcli/gotui/internal/session"
)

// requestTimeout bounds every network call so a hung service shows an error
// state instead of freezing the UI.
const requestTimeout = 60 * time.Second

// Screen identifies the active view.
type Screen int

// Screens.
const (
	ScreenConnect Screen = iota
	ScreenMenu
	ScreenQuery
	ScreenResult
	ScreenDocuments
	ScreenUpload
	ScreenDelete
	ScreenStatus
)

// Options configure a TUI run.
type Options struct {
	ProjectRoot string
	Settings    session.Settings
}

// Model is the root bubbletea model.
type Model struct {
	width  int
	height int
	opts   Options

	screen Screen
	client *api.Client
	form   *huh.Form

	connect ConnectAnswers
	query   QueryAnswers
	result  ResultAnswers
	docs    DocumentAnswers
	upload  UploadAnswers
	confirm ConfirmAnswers
	statusA StatusAnswers
	menu    string

	documents []api.DocumentInfo
	status    *api.SystemStatus
	stats     *api.SystemStats
	answer    *api.QueryResponse
	chunks    []api.ChunkResult

	// server is non-nil when this front-end started the Python service, so it
	// can stop it again on exit.
	server *session.Server
	// password lives in memory only. It is never written to disk and never
	// passed as a command-line argument.
	password string

	busy    string
	failure error
	notice  string
}

// New builds the root model and shows the connection form.
func New(opts Options) *Model {
	m := &Model{
		opts:    opts,
		width:   100,
		height:  30,
		client:  api.NewClient(opts.Settings.BaseURL),
		connect: ConnectDefaults(opts.Settings),
		query:   QueryDefaults(),
		screen:  ScreenConnect,
	}
	m.form = ConnectForm(&m.connect, session.PasswordFromEnv() != "")
	m.resize()
	return m
}

// setForm installs a freshly built form, sizes it, and returns its first
// command. Every screen transition goes through here so no form can ever be
// left at huh's default zero width (which renders as blank lines).
func (m *Model) setForm(form *huh.Form) tea.Cmd {
	m.form = form
	m.resize()
	return m.form.Init()
}

// resize applies the current window size to the form.
//
// huh.NewForm leaves the form at width 0 until something sets it, and a
// zero-width field renders as blank lines. Calling this from New means the form
// is visible even before bubbletea delivers its first WindowSizeMsg.
func (m *Model) resize() {
	if m.form == nil {
		return
	}
	m.form = m.form.WithWidth(m.width - 4)
}

// Init implements tea.Model.
func (m *Model) Init() tea.Cmd { return m.form.Init() }

// Close stops any service this front-end started.
func (m *Model) Close() {
	if m.server != nil {
		m.server.Stop()
		m.server = nil
	}
}

// --- async results -----------------------------------------------------------------

type statusLoadedMsg struct {
	status *api.SystemStatus
	stats  *api.SystemStats
	err    error
}

type documentsLoadedMsg struct {
	documents []api.DocumentInfo
	err       error
}

type queryDoneMsg struct {
	answer *api.QueryResponse
	err    error
}

type chunksLoadedMsg struct {
	chunks []api.ChunkResult
	err    error
}

type deleteDoneMsg struct {
	response *api.DeleteResponse
	err      error
}

type uploadDoneMsg struct {
	response *api.DocumentUploadResponse
	err      error
}

// --- commands ----------------------------------------------------------------------

func loadStatusCmd(client *api.Client) tea.Cmd {
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), requestTimeout)
		defer cancel()
		status, err := client.Status(ctx)
		if err != nil {
			return statusLoadedMsg{err: err}
		}
		stats, err := client.Stats(ctx)
		if err != nil {
			return statusLoadedMsg{status: status, err: err}
		}
		return statusLoadedMsg{status: status, stats: stats}
	}
}

func loadDocumentsCmd(client *api.Client) tea.Cmd {
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), requestTimeout)
		defer cancel()
		page, err := client.Documents(ctx, 200, 0)
		if err != nil {
			return documentsLoadedMsg{err: err}
		}
		return documentsLoadedMsg{documents: page.Documents}
	}
}

func loadChunksCmd(client *api.Client, docID string) tea.Cmd {
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), requestTimeout)
		defer cancel()
		answer, err := client.Query(ctx, api.QueryRequest{
			Query:       "summarise the stored content of this document",
			DocumentIDs: []string{docID},
			TopK:        20,
		})
		if err != nil {
			return chunksLoadedMsg{err: err}
		}
		return chunksLoadedMsg{chunks: answer.Chunks}
	}
}

func runQueryCmd(client *api.Client, answers QueryAnswers) tea.Cmd {
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), requestTimeout)
		defer cancel()
		answer, err := client.Query(ctx, api.QueryRequest{
			Query:             answers.Question,
			TopK:              ParseTopK(answers.TopK),
			MinSimilarity:     ParseMinSimilarity(answers.MinSimilarity),
			IncludeEmbeddings: answers.IncludeEmbeddings,
		})
		return queryDoneMsg{answer: answer, err: err}
	}
}

func deleteDocumentCmd(client *api.Client, docID string) tea.Cmd {
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), requestTimeout)
		defer cancel()
		response, err := client.DeleteDocument(ctx, docID)
		return deleteDoneMsg{response: response, err: err}
	}
}

func uploadDocumentCmd(client *api.Client, path string) tea.Cmd {
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), requestTimeout)
		defer cancel()
		response, err := client.UploadDocument(ctx, path)
		return uploadDoneMsg{response: response, err: err}
	}
}

// --- update ------------------------------------------------------------------------

// Update implements tea.Model.
func (m *Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		m.resize()
		return m, nil

	case statusLoadedMsg:
		m.busy = ""
		m.status, m.stats = msg.status, msg.stats
		m.failure = explain(msg.err)
		if msg.err == nil {
			m.statusA = StatusAnswers{}
			return m, m.setForm(StatusForm(&m.statusA))
		}
		return m, nil

	case documentsLoadedMsg:
		m.busy = ""
		m.failure = explain(msg.err)
		if msg.err == nil {
			m.documents = msg.documents
			// A fresh field is built per load: huh ignores an empty Options
			// slice, so reusing the field would keep stale entries.
			m.docs = DocumentAnswers{}
			m.screen = ScreenDocuments
			return m, m.setForm(DocumentForm(&m.docs, m.documents))
		}
		return m, nil

	case chunksLoadedMsg:
		m.busy = ""
		m.failure = explain(msg.err)
		if msg.err == nil {
			m.chunks = msg.chunks
		}
		m.statusA = StatusAnswers{}
		return m, m.setForm(StatusForm(&m.statusA))

	case queryDoneMsg:
		m.busy = ""
		m.failure = explain(msg.err)
		if msg.err == nil {
			m.answer = msg.answer
			m.chunks = msg.answer.Chunks
			m.result = ResultAnswers{}
			m.screen = ScreenResult
			return m, m.setForm(QueryResultForm(&m.result))
		}
		m.screen = ScreenQuery
		return m, m.setForm(QueryForm(&m.query))

	case deleteDoneMsg:
		m.busy = ""
		m.failure = explain(msg.err)
		if msg.err == nil && msg.response != nil {
			m.notice = msg.response.Message
		}
		return m, loadDocumentsCmd(m.client)

	case uploadDoneMsg:
		m.busy = ""
		m.failure = explain(msg.err)
		if msg.err == nil && msg.response != nil {
			m.notice = "Uploaded " + msg.response.Filename + " (" +
				Truncate(msg.response.DocumentID, 12) + ")"
		}
		return m, loadDocumentsCmd(m.client)

	case tea.KeyPressMsg:
		// Only key PRESSES are handled. bubbletea v2 also delivers key
		// releases, and acting on both would fire every binding twice.
		switch msg.String() {
		case "ctrl+c":
			return m, tea.Quit
		}
		m.notice = ""
	}

	if m.form == nil {
		return m, nil
	}

	updated, cmd := m.form.Update(msg)
	if form, ok := updated.(*huh.Form); ok {
		m.form = form
	}
	if m.form.State != huh.StateNormal {
		return m, m.advance()
	}
	return m, cmd
}

// advance reacts to a finished form. The screen decides what the answers mean.
func (m *Model) advance() tea.Cmd {
	state := m.form.State
	m.form = nil
	m.failure = nil

	if state == huh.StateAborted {
		return tea.Quit
	}

	switch m.screen {
	case ScreenConnect:
		return m.finishConnect()

	case ScreenMenu:
		return m.finishMenu()

	case ScreenQuery:
		m.busy = "Running the query"
		m.screen = ScreenResult
		return runQueryCmd(m.client, m.query)

	case ScreenResult:
		if m.result.Again {
			m.query = QueryDefaults()
			m.screen = ScreenQuery
			return m.setForm(QueryForm(&m.query))
		}
		return m.toMenu()

	case ScreenDocuments:
		return m.finishDocuments()

	case ScreenUpload:
		if strings.TrimSpace(m.upload.Path) == "" {
			return m.toDocuments()
		}
		m.busy = "Uploading " + m.upload.Path
		return uploadDocumentCmd(m.client, m.upload.Path)

	case ScreenDelete:
		if !m.confirm.Confirmed {
			return m.toDocuments()
		}
		m.busy = "Deleting the document"
		return deleteDocumentCmd(m.client, m.docs.DocumentID)

	case ScreenStatus:
		if m.statusA.Action == ActionRefresh {
			m.busy = "Refreshing"
			return loadStatusCmd(m.client)
		}
		return m.toMenu()
	}
	return nil
}

// finishMenu routes the top-level menu selection.
func (m *Model) finishMenu() tea.Cmd {
	switch m.menu {
	case ActionQuery:
		m.query = QueryDefaults()
		m.screen = ScreenQuery
		return m.setForm(QueryForm(&m.query))

	case ActionDocuments:
		m.busy = "Loading documents"
		m.screen = ScreenDocuments
		return loadDocumentsCmd(m.client)

	case ActionStatus:
		m.busy = "Loading status"
		m.screen = ScreenStatus
		return loadStatusCmd(m.client)

	case ActionReconnect:
		m.connect = ConnectDefaults(m.persistedSettings())
		m.screen = ScreenConnect
		return m.setForm(ConnectForm(&m.connect, session.PasswordFromEnv() != ""))

	default:
		return tea.Quit
	}
}

// finishConnect applies the connection answers and moves to the menu.
func (m *Model) finishConnect() tea.Cmd {
	settings := m.connect.toSettings()

	// A blank password field means "use whatever is already in the
	// environment", which is how a scripted user avoids typing it at all.
	m.password = m.connect.OraclePassword
	if m.password == "" {
		m.password = session.PasswordFromEnv()
	}

	m.opts.Settings = settings
	m.client = api.NewClient(settings.BaseURL)

	// Only non-secret settings are persisted, and a save failure is not fatal.
	if err := session.Save(settings); err != nil {
		m.notice = "Could not save settings: " + err.Error()
	}

	if settings.LaunchServer {
		m.busy = "Starting the service on port " + strconv.Itoa(settings.Port)
		server, err := session.LaunchServer(context.Background(), m.opts.ProjectRoot, settings.Port,
			session.ServerEnv(settings.OracleUser, m.password, settings.OracleDSN))
		if err != nil {
			m.busy = ""
			m.failure = err
			return m.toMenu()
		}
		m.server = server
		if err := session.WaitForPort(context.Background(), "127.0.0.1", settings.Port, 45*time.Second); err != nil {
			m.failure = err
		} else {
			m.notice = "Service started on port " + strconv.Itoa(settings.Port)
		}
		m.busy = ""
	}

	return m.toMenu()
}

// finishDocuments routes the document action.
func (m *Model) finishDocuments() tea.Cmd {
	switch m.docs.Action {
	case ActionDelete:
		doc, ok := FindDocument(m.documents, m.docs.DocumentID)
		if !ok {
			return m.toMenu()
		}
		m.confirm = ConfirmAnswers{}
		m.screen = ScreenDelete
		return m.setForm(DeleteForm(&m.confirm, doc))

	case ActionUpload:
		m.upload = UploadAnswers{}
		m.screen = ScreenUpload
		return m.setForm(UploadForm(&m.upload, m.opts.ProjectRoot))

	case ActionBrowse:
		if m.docs.DocumentID == "" {
			m.notice = "Nothing to inspect."
			return nil
		}
		m.busy = "Loading chunks"
		m.screen = ScreenStatus
		return loadChunksCmd(m.client, m.docs.DocumentID)

	case ActionRefresh:
		m.busy = "Refreshing"
		m.screen = ScreenDocuments
		return loadDocumentsCmd(m.client)

	default:
		return m.toMenu()
	}
}

func (m *Model) toMenu() tea.Cmd {
	m.screen = ScreenMenu
	m.menu = ""
	return m.setForm(MenuForm(&m.menu, m.client.BaseURL()))
}

func (m *Model) toDocuments() tea.Cmd {
	m.screen = ScreenDocuments
	m.busy = "Refreshing"
	return loadDocumentsCmd(m.client)
}

func (m *Model) persistedSettings() session.Settings {
	settings := m.opts.Settings
	if settings.BaseURL == "" {
		settings = session.Defaults()
	}
	return settings
}

// explain turns a transport failure into something actionable. A stopped
// service is the common case here, not an exceptional one.
func explain(err error) error {
	if err == nil {
		return nil
	}
	if errors.Is(err, api.ErrUnreachable) {
		return errors.New(err.Error() + " - start the service, then choose Reconnect")
	}
	return err
}

// --- view --------------------------------------------------------------------------

// View implements tea.Model.
func (m *Model) View() tea.View {
	var body strings.Builder

	body.WriteString(Header(m.client.BaseURL(), m.width))
	body.WriteString("\n\n")

	if m.busy != "" {
		body.WriteString(Pane("Working", m.busy, m.width))
		body.WriteString("\n\n")
	}
	if m.failure != nil {
		body.WriteString(PaneError("Problem", m.failure, m.width))
		body.WriteString("\n\n")
	}
	if m.notice != "" {
		body.WriteString(Pane("Done", m.notice, m.width))
		body.WriteString("\n\n")
	}

	if m.screen == ScreenStatus {
		body.WriteString(m.viewStatus())
	}
	if m.screen == ScreenResult && m.answer != nil {
		body.WriteString(m.viewAnswer())
	}

	if m.form != nil {
		body.WriteString(m.form.View())
		body.WriteString("\n\n")
	}

	body.WriteString(Footer(m.hint(), m.width))

	view := tea.NewView(body.String())
	view.AltScreen = true
	return view
}

func (m *Model) viewStatus() string {
	var out strings.Builder
	if m.status != nil {
		health := "unhealthy"
		if m.status.Healthy {
			health = "healthy"
		}
		out.WriteString(Pane("Service status",
			Stat("overall", health)+"\n"+
				Stat("database", m.status.Database.Status+" - "+m.status.Database.Message)+"\n"+
				Stat("ollama", m.status.Ollama.Status+" - "+m.status.Ollama.Message), m.width))
		out.WriteString("\n\n")
	}
	if m.stats != nil {
		out.WriteString(Pane("Corpus",
			Stat("documents", strconv.FormatInt(m.stats.TotalDocuments, 10))+"\n"+
				Stat("vectors", strconv.FormatInt(m.stats.TotalVectors, 10))+"\n"+
				Stat("tokens", strconv.FormatInt(m.stats.TotalTokens, 10))+"\n"+
				Stat("embedding dimension", strconv.FormatInt(m.stats.EmbeddingDimension, 10)), m.width))
		out.WriteString("\n\n")
	}
	if len(m.chunks) > 0 {
		out.WriteString(Pane("Chunks", ChunkRows(m.chunks), m.width))
		out.WriteString("\n\n")
	}
	out.WriteString(Pane("Documents", DocumentRows(m.documents), m.width))
	out.WriteString("\n")
	return out.String()
}

func (m *Model) viewAnswer() string {
	var out strings.Builder
	out.WriteString(Pane("Answer", m.answer.Response, m.width))
	out.WriteString("\n\n")
	out.WriteString(Pane("Retrieved chunks", ChunkRows(m.chunks), m.width))
	out.WriteString("\n\n")
	return out.String()
}

func (m *Model) hint() string {
	switch m.screen {
	case ScreenConnect:
		return "tab next - shift+tab back - enter submit - ctrl+c quit"
	case ScreenResult:
		return "answer the prompt below to continue - ctrl+c quit"
	case ScreenStatus:
		return "choose an action below - ctrl+c quit"
	default:
		return "arrows move - / filters - enter selects - ctrl+c quits (a service this front-end started is stopped too)"
	}
}

// AccessibleNotice explains the mode switch a screen-reader user gets.
const AccessibleNotice = "ACCESSIBLE is set: using plain prompts instead of the full-screen UI."
