package tui

import (
	"bytes"
	"errors"
	"strings"
	"testing"

	"charm.land/huh/v2"

	"github.com/jasperan/ragcli/gotui/internal/api"
	"github.com/jasperan/ragcli/gotui/internal/session"
)

// This file covers the accessible (screen-reader) path.
//
// Why it exists: huh's accessible prompts run a field's validator on the raw line and only
// afterwards substitute the field's default, and they never print that default. A pre-filled
// field whose validator rejects "" therefore re-prompts on every bare Enter, so a
// screen-reader user cannot accept a value they cannot see.
//
// These tests drive the modules' own field builders through huh's real accessible entry point
// (huh.Field.RunAccessible) rather than re-declaring the fields, so they pin the actual
// wiring. Field.RunAccessible is used instead of Form.Run because each accessible prompt
// builds its own buffered scanner over the reader, so only the first prompt of a multi-field
// form can be fed a real answer; per-field driving is the only way to exercise the rest.

var errBlank = errors.New("blank answer rejected")

// runFieldAccessible drives one real field, built by the module's own field builder, through
// huh's accessible path with a single blank line.
func runFieldAccessible(t *testing.T, f huh.Field, input string) string {
	t.Helper()
	var out bytes.Buffer
	if err := f.RunAccessible(&out, strings.NewReader(input)); err != nil {
		// A field whose echo mode needs a tty reports here; the form ignores it too.
		t.Logf("RunAccessible returned %v (ignored, as huh.Form does)", err)
	}
	return out.String()
}

// TestValidateDefaultedAcceptsBlank is the unit half of the fix.
func TestValidateDefaultedAcceptsBlank(t *testing.T) {
	inner := func(s string) error {
		if strings.TrimSpace(s) == "" {
			return errBlank
		}
		if s == "bad" {
			return errors.New("not usable")
		}
		return nil
	}
	wrapped := ValidateDefaulted(inner)

	for _, in := range []string{"", "   ", "\t"} {
		if err := wrapped(in); err != nil {
			t.Errorf("ValidateDefaulted(inner)(%q) = %v, want nil", in, err)
		}
	}
	if err := wrapped("bad"); err == nil {
		t.Error(`ValidateDefaulted(inner)("bad") = nil, want the inner validator's error`)
	}
	if err := wrapped("8000"); err != nil {
		t.Errorf(`ValidateDefaulted(inner)("8000") = %v, want nil`, err)
	}
}

// TestValidateDefaultedValueOnlyRelaxesWhenSomethingIsKept is the guard: ConnectDefaults
// passes through whatever was persisted, so a field may have nothing to keep.
func TestValidateDefaultedValueOnlyRelaxesWhenSomethingIsKept(t *testing.T) {
	inner := func(s string) error {
		if strings.TrimSpace(s) == "" {
			return errBlank
		}
		return nil
	}

	if err := ValidateDefaultedValue("", inner)(""); err == nil {
		t.Error("empty pre-fill accepted a blank answer; a required field was weakened")
	}
	if err := ValidateDefaultedValue("   ", inner)(""); err == nil {
		t.Error("whitespace-only pre-fill accepted a blank answer")
	}
	if err := ValidateDefaultedValue("http://127.0.0.1:8000", inner)(""); err != nil {
		t.Errorf("pre-filled field rejected blank: %v", err)
	}
}

// TestAccessibleBlankAnswerKeepsThePrefilledValue drives the real connect and query fields.
func TestAccessibleBlankAnswerKeepsThePrefilledValue(t *testing.T) {
	t.Run("seeded service url", func(t *testing.T) {
		settings := session.Defaults()
		answers := ConnectDefaults(settings)
		fields := connectFields(&answers, false)
		seeded := answers.BaseURL
		if seeded == "" {
			t.Fatal("service URL is not pre-filled; the test would prove nothing")
		}

		out := runFieldAccessible(t, fields[0], "\n")
		if strings.Contains(out, "a base URL is required") {
			t.Errorf("a blank answer was rejected, so a screen-reader user cannot keep the "+
				"pre-filled service URL.\noutput:\n%s", out)
		}
		if answers.BaseURL != seeded {
			t.Errorf("service URL = %q after a blank answer, want the pre-filled %q", answers.BaseURL, seeded)
		}
	})

	t.Run("seeded port", func(t *testing.T) {
		answers := ConnectDefaults(session.Defaults())
		fields := connectFields(&answers, false)
		seeded := answers.Port
		if seeded == "" {
			t.Fatal("port is not pre-filled; the test would prove nothing")
		}

		out := runFieldAccessible(t, fields[2], "\n")
		if strings.Contains(out, "between 1 and 65535") {
			t.Errorf("a blank answer was rejected, so a screen-reader user cannot keep the "+
				"pre-filled port.\noutput:\n%s", out)
		}
		if answers.Port != seeded {
			t.Errorf("port = %q after a blank answer, want the pre-filled %q", answers.Port, seeded)
		}
	})

	t.Run("seeded top-k", func(t *testing.T) {
		answers := QueryDefaults()
		fields := queryFields(&answers, true)
		seeded := answers.TopK
		if seeded == "" {
			t.Fatal("top-k is not pre-filled; the test would prove nothing")
		}

		out := runFieldAccessible(t, fields[1], "\n")
		if strings.Contains(out, "whole number between 1 and 50") {
			t.Errorf("a blank answer was rejected, so a screen-reader user cannot keep the "+
				"pre-filled top-k.\noutput:\n%s", out)
		}
		if answers.TopK != seeded {
			t.Errorf("top-k = %q after a blank answer, want the pre-filled %q", answers.TopK, seeded)
		}
	})
}

// TestAccessibleStillRejectsBlankWithoutAPrefill is the negative half, on real fields: the
// question and the (unseeded) service URL have nothing to keep, so blank must still fail.
func TestAccessibleStillRejectsBlankWithoutAPrefill(t *testing.T) {
	t.Run("question has no default", func(t *testing.T) {
		answers := QueryDefaults()
		fields := queryFields(&answers, true)

		out := runFieldAccessible(t, fields[0], "\n")
		if !strings.Contains(out, "input cannot be empty") {
			t.Errorf("a required field with no default accepted a blank answer, so the "+
				"blank-pass wrapper leaked.\noutput:\n%s", out)
		}
	})

	t.Run("unseeded service url", func(t *testing.T) {
		answers := ConnectAnswers{} // nothing persisted yet
		fields := connectFields(&answers, false)

		out := runFieldAccessible(t, fields[0], "\n")
		if !strings.Contains(out, "a base URL is required") {
			t.Errorf("an unseeded service URL accepted a blank answer.\noutput:\n%s", out)
		}
		if answers.BaseURL != "" {
			t.Errorf("service URL = %q, want it left empty", answers.BaseURL)
		}
	})
}

// TestConnectDefaultsSeedsEveryNonSecretSetting pins the assumption the tests above rely on:
// the fields they exercise really are pre-filled.
func TestConnectDefaultsSeedsEveryNonSecretSetting(t *testing.T) {
	answers := ConnectDefaults(session.Defaults())
	for name, got := range map[string]string{
		"base url": answers.BaseURL,
		"port":     answers.Port,
	} {
		if strings.TrimSpace(got) == "" {
			t.Errorf("%s is not seeded from settings", name)
		}
	}
	if answers.OraclePassword != "" {
		t.Error("the password must never be seeded from persisted settings")
	}
	if strings.TrimSpace(api.DefaultBaseURL) == "" {
		t.Error("api.DefaultBaseURL is empty; the seeded-URL assertions above rest on it")
	}
}
