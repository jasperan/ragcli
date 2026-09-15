package session

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// withConfigDir redirects os.UserConfigDir so tests never touch the real
// settings file.
func withConfigDir(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	t.Setenv("XDG_CONFIG_HOME", dir)
	t.Setenv("HOME", dir)
	return dir
}

func TestLoadFallsBackToDefaults(t *testing.T) {
	withConfigDir(t)

	settings, err := Load()
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if settings != Defaults() {
		t.Fatalf("expected defaults, got %+v", settings)
	}
}

func TestSaveThenLoadRoundTrips(t *testing.T) {
	withConfigDir(t)

	want := Settings{
		BaseURL:      "http://127.0.0.1:9000",
		LaunchServer: true,
		Port:         9000,
		OracleUser:   "RAGCLI",
		OracleDSN:    "db.example:1521/FREEPDB1",
	}
	if err := Save(want); err != nil {
		t.Fatalf("Save: %v", err)
	}

	got, err := Load()
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if got != want {
		t.Fatalf("round trip mismatch: got %+v want %+v", got, want)
	}
}

// TestSettingsFileIsPrivateAndSecretFree is the proof for the credential rule:
// the persisted file is 0600 AND contains no password, so a leaked copy reveals
// only a URL.
func TestSettingsFileIsPrivateAndSecretFree(t *testing.T) {
	withConfigDir(t)

	settings := Defaults()
	settings.OracleUser = "RAGCLI"
	if err := Save(settings); err != nil {
		t.Fatalf("Save: %v", err)
	}

	path, err := ConfigPath()
	if err != nil {
		t.Fatalf("ConfigPath: %v", err)
	}

	info, err := os.Stat(path)
	if err != nil {
		t.Fatalf("stat settings: %v", err)
	}
	if perm := info.Mode().Perm(); perm != 0o600 {
		t.Fatalf("settings must be 0600, got %o", perm)
	}

	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read settings: %v", err)
	}
	lowered := strings.ToLower(string(raw))
	for _, forbidden := range []string{"password", "secret", "token", "apikey", "api_key"} {
		if strings.Contains(lowered, forbidden) {
			t.Fatalf("settings file must not mention %q; contents were %s", forbidden, raw)
		}
	}
}

func TestSaveRefusesCredentialShapedInput(t *testing.T) {
	withConfigDir(t)

	settings := Defaults()
	settings.OracleUser = "user password=hunter2"
	if err := Save(settings); err == nil {
		t.Fatal("expected Save to refuse credential-shaped input")
	}
}

// TestPasswordComesFromTheEnvironmentOnly pins the transport for the one secret
// this front-end handles: the child process environment, never argv.
func TestPasswordComesFromTheEnvironmentOnly(t *testing.T) {
	t.Setenv(EnvOraclePassword, "hunter2")
	if got := PasswordFromEnv(); got != "hunter2" {
		t.Fatalf("expected the environment password, got %q", got)
	}

	os.Unsetenv(EnvOraclePassword)
	if got := PasswordFromEnv(); got != "" {
		t.Fatalf("expected an empty password, got %q", got)
	}
}

func TestServerEnvCarriesCredentialsOutOfBand(t *testing.T) {
	t.Setenv("PATH", "/usr/bin")

	env := ServerEnv("RAGCLI", "hunter2", "db:1521/XEPDB1")

	joined := strings.Join(env, "\n")
	for _, want := range []string{
		EnvOracleUsername + "=RAGCLI",
		EnvOraclePassword + "=hunter2",
		EnvOracleDSN + "=db:1521/XEPDB1",
	} {
		if !strings.Contains(joined, want) {
			t.Fatalf("environment is missing %q", want)
		}
	}
	// The password must travel as its own environment entry, not glued into a
	// command line.
	for _, entry := range env {
		if strings.HasPrefix(entry, EnvOraclePassword+"=") {
			if entry != EnvOraclePassword+"=hunter2" {
				t.Fatalf("unexpected password entry %q", entry)
			}
			return
		}
	}
	t.Fatalf("no %s entry was produced", EnvOraclePassword)
}

// TestLaunchServerKeepsTheSecretOutOfArgv asserts on the exact argv the service
// is started with. /proc/<pid>/cmdline is world readable, so a password in argv
// would leak regardless of file permissions.
func TestLaunchServerKeepsTheSecretOutOfArgv(t *testing.T) {
	secret := "hunter2"
	argv := ServerArgs(8000)

	for _, arg := range argv {
		if strings.Contains(arg, secret) {
			t.Fatalf("secret leaked into argv: %v", argv)
		}
		if strings.Contains(arg, EnvOraclePassword) || strings.Contains(arg, "password") {
			t.Fatalf("argv must not reference a credential: %v", argv)
		}
	}

	// The argv must still be the interface the repo documents.
	joined := strings.Join(argv, " ")
	if !strings.Contains(joined, "ragcli api") {
		t.Fatalf("argv should start the repo's own CLI: %v", argv)
	}
	if !strings.Contains(joined, "--port 8000") {
		t.Fatalf("argv should carry the chosen port: %v", argv)
	}

	// And the secret must be present in the environment instead.
	env := ServerEnv("RAGCLI", secret, "db:1521/XEPDB1")
	found := false
	for _, entry := range env {
		if entry == EnvOraclePassword+"="+secret {
			found = true
		}
	}
	if !found {
		t.Fatalf("the secret must travel in the environment; got %d entries", len(env))
	}
}

func TestValidatePort(t *testing.T) {
	good := []string{"1", "8000", "65535", " 8080 "}
	for _, raw := range good {
		if err := ValidatePort(raw); err != nil {
			t.Errorf("%q should be valid: %v", raw, err)
		}
	}

	bad := []string{"", "abc", "0", "65536", "-1", "80.5"}
	for _, raw := range bad {
		if err := ValidatePort(raw); err == nil {
			t.Errorf("%q should be rejected", raw)
		}
	}
}

func TestParsePortFallsBack(t *testing.T) {
	if got := ParsePort("8080"); got != 8080 {
		t.Fatalf("expected 8080, got %d", got)
	}
	if got := ParsePort("nonsense"); got != DefaultPort {
		t.Fatalf("expected the default, got %d", got)
	}
}

func TestConfigPathIsUnderTheConfigDir(t *testing.T) {
	dir := withConfigDir(t)

	path, err := ConfigPath()
	if err != nil {
		t.Fatalf("ConfigPath: %v", err)
	}
	if !strings.HasPrefix(path, dir) {
		t.Fatalf("expected %s under %s", path, dir)
	}
	if filepath.Base(path) != "gotui.json" {
		t.Fatalf("unexpected file name %s", path)
	}
}
