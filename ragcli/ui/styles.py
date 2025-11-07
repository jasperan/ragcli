"""Custom styles for ragcli web UI."""

CUSTOM_CSS = """
/* Theme: Dark mode with Oracle cyan */
:root {
  --primary-color: #00D9FF;
  --accent-color: #FF6B6B;
  --background-color: #0A0E27;
  --secondary-background: #1E2749;
  --text-color: #E0E0E0;
  --text-secondary: #A0A0A0;
  --border-color: #2A2E4A;
  --shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

/* Headings */
h1, h2, h3, h4, h5, h6 {
  font-family: 'Inter', sans-serif;
  font-weight: bold;
  color: var(--primary-color);
  margin-bottom: 8px;
}

/* Body text */
body, p, div {
  font-family: 'Inter', sans-serif;
  color: var(--text-color);
  line-height: 1.5;
}

/* Code */
code, pre {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.875rem;
  background: var(--secondary-background);
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  color: var(--text-color);
}

/* Cards */
.gr-box {
  background: var(--secondary-background);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  box-shadow: var(--shadow);
  padding: 1rem;
}

/* Buttons */
.gr-button {
  background: var(--primary-color);
  color: white;
  border-radius: 6px;
  padding: 0.5rem 1rem;
  transition: all 0.2s;
}

.gr-button:hover {
  background: #0099CC;
  transform: translateY(-1px);
}

/* Inputs */
.gr-textbox, .gr-dropdown {
  background: var(--background-color);
  border: 1px solid var(--border-color);
  color: var(--text-color);
  border-radius: 6px;
  padding: 0.5rem;
}

/* Tables */
.gr-dataframe {
  background: var(--secondary-background);
  border: 1px solid var(--border-color);
}

.gr-dataframe th {
  background: var(--primary-color);
  color: white;
}

/* Spacing */
.gr-row, .gr-column {
  padding: 12px;
}

.gr-tab {
  background: var(--secondary-background);
  color: var(--text-color);
}

/* Transitions */
* {
  transition: all 0.2s ease-in-out;
}

/* Max width */
body {
  max-width: 1400px;
  margin: 0 auto;
  padding: 1rem;
}
"""

def get_theme():
    """Get Gradio theme with custom CSS."""
    import gradio as gr
    theme = gr.themes.Soft(primary_hue="cyan", secondary_hue="gray", neutral_hue="slate")
    return theme, CUSTOM_CSS
