package tui

import (
	"strconv"
	"strings"

	"charm.land/lipgloss/v2"
	"github.com/jasperan/ragcli/gotui/internal/api"
	"github.com/jasperan/ragcli/gotui/internal/huhstyle"
)

// The pane palette is DERIVED FROM THE THEME, never declared here. Writing a
// colour literal in this file would fail scripts/tui-shot/check_palette.py and
// would also fork the palette away from the single source of truth in
// internal/huhstyle. Reading it back out of the compiled styles keeps one
// definition of every token.
func palette() (primary, text, subtext, muted, danger lipgloss.Style) {
	styles := huhstyle.Styles()
	return lipgloss.NewStyle().Foreground(styles.Focused.Title.GetForeground()),
		lipgloss.NewStyle().Foreground(styles.Focused.Option.GetForeground()),
		lipgloss.NewStyle().Foreground(styles.Focused.Description.GetForeground()),
		lipgloss.NewStyle().Foreground(styles.Focused.TextInput.Placeholder.GetForeground()),
		lipgloss.NewStyle().Foreground(styles.Focused.ErrorMessage.GetForeground())
}

// Pane renders a titled panel: rounded border, generous padding, primary title.
func Pane(title, body string, width int) string {
	primary, text, _, _, _ := palette()

	if width < 24 {
		width = 24
	}

	heading := ""
	if title != "" {
		heading = primary.Bold(true).Render(title) + "\n"
	}
	return lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder()).
		Padding(1, 2).
		Width(width).
		Render(heading + text.Render(body))
}

// PaneError renders an error panel. A failed API call is a normal state in this
// front-end, not a crash: the user gets the cause and a way onward.
func PaneError(title string, err error, width int) string {
	_, _, _, _, danger := palette()
	message := "unknown error"
	if err != nil {
		message = err.Error()
	}
	return Pane(title, danger.Render(message), width)
}

// Fog renders low-emphasis text.
func Fog(body string) string {
	_, _, subtext, _, _ := palette()
	return subtext.Render(body)
}

// Subtle renders metadata text.
func Subtle(body string) string {
	_, _, _, muted, _ := palette()
	return muted.Render(body)
}

// Stat renders one "label: value" line for the readouts.
func Stat(label, value string) string {
	_, text, subtext, _, _ := palette()
	return subtext.Render(label+": ") + text.Render(value)
}

// DocumentRows renders the document list as an aligned table.
func DocumentRows(docs []api.DocumentInfo) string {
	if len(docs) == 0 {
		return "No documents are stored yet."
	}
	_, text, _, muted, _ := palette()

	var out strings.Builder
	out.WriteString(muted.Render("  filename                            format  chunks  tokens") + "\n")
	for _, doc := range docs {
		out.WriteString(text.Render(Pad(Truncate(doc.Filename, 34), 34)) + "  ")
		out.WriteString(text.Render(Pad(doc.FileFormat, 6)) + "  ")
		out.WriteString(text.Render(Pad(strconv.Itoa(int(doc.ChunkCount)), 6)) + "  ")
		out.WriteString(text.Render(strconv.FormatInt(doc.TotalTokens, 10)) + "\n")
	}
	return strings.TrimRight(out.String(), "\n")
}

// ChunkRows renders retrieved chunks with their similarity scores.
func ChunkRows(chunks []api.ChunkResult) string {
	if len(chunks) == 0 {
		return "No chunks were retrieved."
	}
	_, text, subtext, muted, _ := palette()

	var out strings.Builder
	for i, chunk := range chunks {
		out.WriteString(muted.Render("chunk "+strconv.Itoa(i+1)+"  similarity ") +
			subtext.Render(strconv.FormatFloat(chunk.SimilarityScore, 'f', 3, 64)) + "\n")
		out.WriteString(text.Render(Truncate(strings.ReplaceAll(chunk.Text, "\n", " "), 220)) + "\n\n")
	}
	return strings.TrimRight(out.String(), "\n")
}

// Header is the persistent identity bar.
func Header(baseURL string, width int) string {
	primary, _, subtext, _, _ := palette()
	title := primary.Bold(true).Render("ragcli") + " " + subtext.Render("Go front-end")
	right := subtext.Render(baseURL)
	gap := width - lipgloss.Width(title) - lipgloss.Width(right) - 4
	if gap < 1 {
		gap = 1
	}
	return title + strings.Repeat(" ", gap) + right
}

// Footer is the key-hint bar.
func Footer(hint string, width int) string {
	_, _, subtext, _, _ := palette()
	if lipgloss.Width(hint) > width-2 {
		hint = Truncate(hint, width-2)
	}
	return subtext.Render(hint)
}

// Pad right-pads to n columns.
func Pad(s string, n int) string {
	if len(s) >= n {
		return s
	}
	return s + strings.Repeat(" ", n-len(s))
}

// Truncate shortens s to n runes, adding an ellipsis when it cuts.
func Truncate(s string, n int) string {
	if n <= 1 {
		return s
	}
	runes := []rune(s)
	if len(runes) <= n {
		return s
	}
	return string(runes[:n-1]) + "~"
}
