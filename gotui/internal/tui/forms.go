package tui

import (
	"errors"
	"strconv"
	"strings"

	"charm.land/huh/v2"
	"github.com/jasperan/ragcli/gotui/internal/api"
	"github.com/jasperan/ragcli/gotui/internal/huhstyle"
	"github.com/jasperan/ragcli/gotui/internal/session"
)

// SimilarityLevels are the min_similarity choices. They are a STATIC slice on
// purpose: huh's OptionsFunc is evaluated lazily, and in accessible mode
// (Form.Run with WithAccessible) the resolved slice is read before any async
// evaluation runs, which renders an empty list. Static options are the only
// shape that works in both modes.
var SimilarityLevels = []huh.Option[string]{
	huh.NewOption("0.00 - return everything", "0.00"),
	huh.NewOption("0.25 - loose", "0.25"),
	huh.NewOption("0.50 - balanced (server default)", "0.50"),
	huh.NewOption("0.75 - strict", "0.75"),
	huh.NewOption("0.90 - near-exact", "0.90"),
}

// ConnectAnswers are the connection form's values.
type ConnectAnswers struct {
	BaseURL        string
	LaunchServer   bool
	Port           string
	OracleUser     string
	OraclePassword string
	OracleDSN      string
}

// ConnectDefaults seeds the form from persisted, non-secret settings.
func ConnectDefaults(settings session.Settings) ConnectAnswers {
	return ConnectAnswers{
		BaseURL:      settings.BaseURL,
		LaunchServer: settings.LaunchServer,
		Port:         strconv.Itoa(settings.Port),
		OracleUser:   settings.OracleUser,
		OracleDSN:    settings.OracleDSN,
	}
}

// toSettings converts the connection answers into persistable settings,
// filling in the documented defaults. The password is deliberately absent.
func (a ConnectAnswers) toSettings() session.Settings {
	settings := session.Settings{
		BaseURL:      strings.TrimSpace(a.BaseURL),
		LaunchServer: a.LaunchServer,
		Port:         session.ParsePort(a.Port),
		OracleUser:   strings.TrimSpace(a.OracleUser),
		OracleDSN:    strings.TrimSpace(a.OracleDSN),
	}
	if settings.BaseURL == "" {
		settings.BaseURL = api.DefaultBaseURL
	}
	if settings.OracleUser == "" {
		settings.OracleUser = session.DefaultOracleUse
	}
	if settings.OracleDSN == "" {
		settings.OracleDSN = session.DefaultOracleDSN
	}
	return settings
}

// connectFields are the connection questions.
//
// They are separated from ConnectForm so the accessibility path can place them
// in a single form together with the query questions: huh's accessible Run
// buffers its reader, so two sequential forms cannot share stdin (the second
// one sees EOF and every answer comes back empty).
func connectFields(answers *ConnectAnswers, passwordFromEnv bool) []huh.Field {
	passwordNote := "Stored only in this process, passed to the service through the environment."
	if passwordFromEnv {
		passwordNote = "Already set in " + session.EnvOraclePassword + "; leave blank to use it."
	}

	return []huh.Field{
		huh.NewInput().
			Title("Service URL").
			Description("Where the ragcli FastAPI service is listening.").
			Placeholder(api.DefaultBaseURL).
			Value(&answers.BaseURL).
			Validate(ValidateDefaultedValue(answers.BaseURL, api.ValidateBaseURL)),

		huh.NewConfirm().
			Title("Start a local service for me?").
			Description("Runs the repo's own CLI: uv run ragcli api --port <port>.").
			Value(&answers.LaunchServer),

		huh.NewInput().
			Title("Service port").
			Description("Used only when starting a local service.").
			Placeholder("8000").
			Value(&answers.Port).
			Validate(ValidateDefaultedValue(answers.Port, session.ValidatePort)),

		huh.NewInput().
			Title("Oracle user (optional)").
			Description("Sets " + session.EnvOracleUsername + " for the started service.").
			Placeholder(session.DefaultOracleUse).
			Value(&answers.OracleUser),

		huh.NewInput().
			Title("Oracle password (optional)").
			Description(passwordNote).
			EchoMode(huh.EchoModePassword).
			Value(&answers.OraclePassword),

		huh.NewInput().
			Title("Oracle DSN (optional)").
			Description("Sets " + session.EnvOracleDSN + " for the started service.").
			Placeholder(session.DefaultOracleDSN).
			Value(&answers.OracleDSN),
	}
}

// ConnectForm builds the connection form used by the full-screen UI.
//
// Every field lives in ONE group with no WithHideFunc: huh does not skip hidden
// groups in accessible mode, so a conditionally hidden required field would trap
// a screen-reader user on a question they cannot answer. The Oracle fields are
// optional and port/dsn carry valid defaults, so the form is always completable
// as rendered.
func ConnectForm(answers *ConnectAnswers, passwordFromEnv bool) *huh.Form {
	return huh.NewForm(
		huh.NewGroup(connectFields(answers, passwordFromEnv)...).Title("Connect"),
	).WithTheme(huh.ThemeFunc(huhstyle.Theme)).WithAccessible(huhstyle.Accessible())
}

// PlainAnswers holds both pages of the single accessible form.
type PlainAnswers struct {
	Connect ConnectAnswers
	Query   QueryAnswers
}

// PlainForm is the one-pass form used when ACCESSIBLE is set or stdin is not a
// terminal.
//
// It is deliberately a SINGLE group, not two. In accessible mode huh runs only
// the first group of a form and then reports the form complete: with
// "Connect" and "Query" as separate groups, every question in the second group
// was silently left at its default (observed: question="" while all six
// connection answers landed correctly). One group means every question is
// actually asked, exactly once, one line each.
func PlainForm(answers *PlainAnswers, passwordFromEnv bool) *huh.Form {
	fields := connectFields(&answers.Connect, passwordFromEnv)
	fields = append(fields, queryFields(&answers.Query, true)...)

	return huh.NewForm(
		huh.NewGroup(fields...).Title("Connect and ask"),
	).WithTheme(huh.ThemeFunc(huhstyle.Theme)).WithAccessible(huhstyle.Accessible())
}

// MenuActions are the top-level destinations.
var MenuActions = []huh.Option[string]{
	huh.NewOption("Ask a question", ActionQuery),
	huh.NewOption("Documents", ActionDocuments),
	huh.NewOption("Status and statistics", ActionStatus),
	huh.NewOption("Reconnect", ActionReconnect),
	huh.NewOption("Quit", ActionQuit),
}

// Action identifiers shared by the TUI and the plain path.
const (
	ActionQuery     = "query"
	ActionDocuments = "documents"
	ActionStatus    = "status"
	ActionReconnect = "reconnect"
	ActionQuit      = "quit"

	ActionBrowse  = "browse"
	ActionUpload  = "upload"
	ActionDelete  = "delete"
	ActionRefresh = "refresh"
	ActionBack    = "back"
)

// MenuForm builds the main menu.
func MenuForm(choice *string, serviceURL string) *huh.Form {
	return huh.NewForm(
		huh.NewGroup(
			huh.NewSelect[string]().
				Title("What next?").
				Description("Connected to " + serviceURL + ".").
				Options(MenuActions...).
				Value(choice),
		).Title("ragcli"),
	).WithTheme(huh.ThemeFunc(huhstyle.Theme)).WithAccessible(huhstyle.Accessible())
}

// QueryAnswers are the query form's values.
type QueryAnswers struct {
	Question          string
	TopK              string
	MinSimilarity     string
	IncludeEmbeddings bool
}

// QueryDefaults mirrors ragcli/api/models.py:QueryRequest defaults.
func QueryDefaults() QueryAnswers {
	return QueryAnswers{TopK: "5", MinSimilarity: "0.50"}
}

// ValidateDefaulted accepts an empty answer as "keep the value already in the field".
//
// It exists for accessible mode. huh's screen-reader path runs a field's validator on the
// raw line and only afterwards substitutes the field's default
// (internal/accessibility/accessibility.go:PromptString returns
// cmp.Or(strings.TrimSpace(input), defaultValue)), and it never prints that default. A
// pre-filled field whose validator rejects "" therefore keeps re-prompting on a bare
// Enter, so a screen-reader user cannot accept a value they cannot see.
func ValidateDefaulted(inner func(string) error) func(string) error {
	return func(s string) error {
		if strings.TrimSpace(s) == "" {
			return nil
		}
		return inner(s)
	}
}

// ValidateDefaultedValue is ValidateDefaulted for a field whose pre-filled value may
// itself be empty (ConnectDefaults passes through whatever was persisted). Blank stays
// invalid when there is nothing to keep.
func ValidateDefaultedValue(prefilled string, inner func(string) error) func(string) error {
	if strings.TrimSpace(prefilled) == "" {
		return inner
	}
	return ValidateDefaulted(inner)
}

// ValidateTopK enforces the server's 1..50 bound so a bad value is caught in
// the form rather than as an HTTP 422.
func ValidateTopK(raw string) error {
	value, err := strconv.Atoi(strings.TrimSpace(raw))
	if err != nil {
		return errors.New("use a whole number between 1 and 50")
	}
	if value < 1 || value > 50 {
		return errors.New("use a whole number between 1 and 50")
	}
	return nil
}

// ParseTopK converts a validated top-k string.
func ParseTopK(raw string) int {
	value, err := strconv.Atoi(strings.TrimSpace(raw))
	if err != nil || value < 1 || value > 50 {
		return 5
	}
	return value
}

// ParseMinSimilarity converts a validated similarity choice.
func ParseMinSimilarity(raw string) float64 {
	value, err := strconv.ParseFloat(strings.TrimSpace(raw), 64)
	if err != nil || value < 0 || value > 1 {
		return 0.5
	}
	return value
}

// queryFields are the query questions.
//
// The question field is single-line in accessible mode. A huh Text field is a
// multi-line textarea whose accessible prompt keeps reading until it is
// satisfied, which both defeats a one-answer-per-prompt interaction and makes
// the reader consume lines belonging to the NEXT question. A single-line Input
// is one prompt, one answer, which is also the easier control for a screen
// reader.
func queryFields(answers *QueryAnswers, singleLineQuestion bool) []huh.Field {
	question := huh.Field(huh.NewInput().
		Title("Question").
		Description("Ask the stored corpus.").
		Placeholder("What does the documentation say about ...").
		CharLimit(5000).
		Value(&answers.Question).
		Validate(huh.ValidateNotEmpty()))
	if !singleLineQuestion {
		question = huh.NewText().
			Title("Question").
			Description("Ask the stored corpus. Ctrl+J or alt+enter adds a line.").
			Placeholder("What does the documentation say about ...").
			CharLimit(5000).
			Lines(4).
			Value(&answers.Question).
			Validate(huh.ValidateNotEmpty())
	}

	return []huh.Field{
		question,

		huh.NewInput().
			Title("Chunks to retrieve").
			Description("top_k, between 1 and 50.").
			Placeholder("5").
			Value(&answers.TopK).
			Validate(ValidateDefaultedValue(answers.TopK, ValidateTopK)),

		huh.NewSelect[string]().
			Title("Minimum similarity").
			Options(SimilarityLevels...).
			Value(&answers.MinSimilarity),

		huh.NewConfirm().
			Title("Include chunk embeddings?").
			Description("Large payload; only useful for inspection.").
			Value(&answers.IncludeEmbeddings),
	}
}

// QueryForm builds the query form used by the full-screen UI.
func QueryForm(answers *QueryAnswers) *huh.Form {
	return huh.NewForm(
		huh.NewGroup(queryFields(answers, huhstyle.Accessible())...).Title("Query"),
	).WithTheme(huh.ThemeFunc(huhstyle.Theme)).WithAccessible(huhstyle.Accessible())
}

// ResultAnswers is the post-query continue prompt.
type ResultAnswers struct{ Again bool }

// QueryResultForm builds the "ask another?" prompt.
func QueryResultForm(answers *ResultAnswers) *huh.Form {
	return huh.NewForm(
		huh.NewGroup(
			huh.NewConfirm().
				Title("Ask another question?").
				Affirmative("Yes").
				Negative("Back to the menu").
				Value(&answers.Again),
		),
	).WithTheme(huh.ThemeFunc(huhstyle.Theme)).WithAccessible(huhstyle.Accessible())
}

// DocumentAnswers are the document-action form's values.
type DocumentAnswers struct {
	DocumentID string
	Action     string
}

// DocumentOptions builds the static document option list.
//
// A fresh slice per load is mandatory: huh silently ignores an empty Options
// call, so a refresh that returns nothing would otherwise keep showing the
// previous documents.
func DocumentOptions(docs []api.DocumentInfo) []huh.Option[string] {
	if len(docs) == 0 {
		return []huh.Option[string]{huh.NewOption("(no documents stored)", "")}
	}
	options := make([]huh.Option[string], 0, len(docs))
	for _, doc := range docs {
		label := doc.Filename + "  (" + strconv.Itoa(int(doc.ChunkCount)) + " chunks, " +
			doc.FileFormat + ")"
		options = append(options, huh.NewOption(label, doc.DocumentID))
	}
	return options
}

// DocumentActions are the actions available for a selected document.
var DocumentActions = []huh.Option[string]{
	huh.NewOption("Inspect chunks", ActionBrowse),
	huh.NewOption("Delete this document", ActionDelete),
	huh.NewOption("Upload a file", ActionUpload),
	huh.NewOption("Refresh the list", ActionRefresh),
	huh.NewOption("Back to the menu", ActionBack),
}

// DocumentForm builds the document selection + action form.
func DocumentForm(answers *DocumentAnswers, docs []api.DocumentInfo) *huh.Form {
	return huh.NewForm(
		huh.NewGroup(
			huh.NewSelect[string]().
				Title("Document").
				Options(DocumentOptions(docs)...).
				Value(&answers.DocumentID),

			huh.NewSelect[string]().
				Title("Action").
				Options(DocumentActions...).
				Value(&answers.Action),
		).Title("Documents"),
	).WithTheme(huh.ThemeFunc(huhstyle.Theme)).WithAccessible(huhstyle.Accessible())
}

// UploadAnswers is the upload form's value.
type UploadAnswers struct{ Path string }

// UploadForm builds the file picker form. The PDF/TXT/MD filter matches
// config.yaml.example's supported_formats.
func UploadForm(answers *UploadAnswers, startDirectory string) *huh.Form {
	return huh.NewForm(
		huh.NewGroup(
			huh.NewFilePicker().
				Title("Pick a file to upload").
				Description("Supported formats: TXT, MD, PDF.").
				CurrentDirectory(startDirectory).
				Picking(true).
				FileAllowed(true).
				DirAllowed(false).
				ShowSize(true).
				Height(12).
				AllowedTypes([]string{".txt", ".md", ".pdf"}).
				Value(&answers.Path).
				Validate(func(path string) error {
					if strings.TrimSpace(path) == "" {
						return errors.New("choose a file")
					}
					return nil
				}),
		).Title("Upload"),
	).WithTheme(huh.ThemeFunc(huhstyle.Theme)).WithAccessible(huhstyle.Accessible())
}

// ConfirmAnswers is the delete confirmation.
type ConfirmAnswers struct {
	Confirmed bool
	Typed     string
}

// DeleteConfirmationValidator is the guard behind the destructive action: the
// typed value must equal the filename exactly.
//
// It is exported so the guard can be tested directly rather than through a
// rendered form, which is where the regression risk actually sits.
func DeleteConfirmationValidator(doc api.DocumentInfo) func(string) error {
	return func(typed string) error {
		if strings.TrimSpace(typed) != doc.Filename {
			return errors.New("does not match " + doc.Filename)
		}
		return nil
	}
}

// DeleteForm builds the destructive confirmation for one document.
//
// Deleting a document also deletes every chunk and embedding derived from it,
// so the confirmation names the document and requires its filename to be typed.
func DeleteForm(answers *ConfirmAnswers, doc api.DocumentInfo) *huh.Form {
	return huh.NewForm(
		huh.NewGroup(
			huh.NewInput().
				Title("Type the filename to confirm").
				Description("Deleting " + doc.Filename + " removes " +
					strconv.Itoa(int(doc.ChunkCount)) + " chunks and their embeddings. This cannot be undone.").
				Placeholder(doc.Filename).
				Value(&answers.Typed).
				Validate(DeleteConfirmationValidator(doc)),
		).Title("Confirm delete"),
	).WithTheme(huh.ThemeFunc(huhstyle.Theme)).WithAccessible(huhstyle.Accessible())
}

// FindDocument looks up a document by id.
func FindDocument(docs []api.DocumentInfo, id string) (api.DocumentInfo, bool) {
	for _, doc := range docs {
		if doc.DocumentID == id {
			return doc, true
		}
	}
	return api.DocumentInfo{}, false
}

// StatusAnswers is the readout screen's action choice.
//
// The readout needs a form to hand control back: with m.form == nil the root
// model would have nothing to continue from.
type StatusAnswers struct{ Action string }

// StatusForm builds the readout's continue prompt.
func StatusForm(answers *StatusAnswers) *huh.Form {
	return huh.NewForm(
		huh.NewGroup(
			huh.NewSelect[string]().
				Title("What next?").
				Options(
					huh.NewOption("Refresh", ActionRefresh),
					huh.NewOption("Back to the menu", ActionBack),
				).
				Value(&answers.Action),
		).Title("Status"),
	).WithTheme(huh.ThemeFunc(huhstyle.Theme)).WithAccessible(huhstyle.Accessible())
}
