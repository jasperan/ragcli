// Package session holds the non-secret connection settings for the Go
// front-end, plus the one mechanism used to hand an Oracle password to the
// Python service: environment variables.
//
// Why environment and never argv: a command line is world-readable via
// /proc/<pid>/cmdline, and shell history records it. ragcli's own
// config.yaml.example already interpolates ${ORACLE_PASSWORD} from the
// environment, so this is the codebase's supported channel rather than an
// invention.
package session

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

// Oracle password environment variable, matched to config.yaml.example.
const (
	EnvOraclePassword = "ORACLE_PASSWORD"
	EnvOracleUsername = "ORACLE_USERNAME"
	EnvOracleDSN      = "ORACLE_DSN"

	DefaultPort      = 8000
	DefaultOracleUse = "RAGCLI"
	DefaultOracleDSN = "localhost:1521/FREEPDB1"
)

// Settings are the persisted, NON-SECRET connection settings. There is
// deliberately no password field: see the package comment.
type Settings struct {
	BaseURL      string `json:"base_url"`
	LaunchServer bool   `json:"launch_server"`
	Port         int    `json:"port"`
	OracleUser   string `json:"oracle_user"`
	OracleDSN    string `json:"oracle_dsn"`
}

// Defaults returns the settings a first run should start from.
func Defaults() Settings {
	return Settings{
		BaseURL:      "http://127.0.0.1:8000",
		LaunchServer: false,
		Port:         DefaultPort,
		OracleUser:   DefaultOracleUse,
		OracleDSN:    DefaultOracleDSN,
	}
}

// ConfigPath is where Settings live. The file is written 0600 and holds no
// secret, so a leaked copy reveals only a URL.
func ConfigPath() (string, error) {
	dir, err := os.UserConfigDir()
	if err != nil {
		return "", fmt.Errorf("locate config dir: %w", err)
	}
	return filepath.Join(dir, "ragcli", "gotui.json"), nil
}

// Load reads Settings, falling back to Defaults when there is no file yet.
func Load() (Settings, error) {
	path, err := ConfigPath()
	if err != nil {
		return Defaults(), err
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return Defaults(), nil
		}
		return Defaults(), fmt.Errorf("read %s: %w", path, err)
	}
	settings := Defaults()
	if err := json.Unmarshal(raw, &settings); err != nil {
		return Defaults(), fmt.Errorf("parse %s: %w", path, err)
	}
	return settings, nil
}

// Save writes Settings with 0600 permissions. It refuses to write anything
// that looks like a credential, so a future edit cannot silently start
// persisting a secret.
func Save(settings Settings) error {
	path, err := ConfigPath()
	if err != nil {
		return err
	}
	if strings.Contains(strings.ToLower(settings.OracleUser), "password=") {
		return errors.New("refusing to persist what looks like a credential")
	}

	encoded, err := json.MarshalIndent(settings, "", "  ")
	if err != nil {
		return fmt.Errorf("encode settings: %w", err)
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return fmt.Errorf("create %s: %w", filepath.Dir(path), err)
	}
	if err := os.WriteFile(path, append(encoded, '\n'), 0o600); err != nil {
		return fmt.Errorf("write %s: %w", path, err)
	}
	return nil
}

// PasswordFromEnv returns the Oracle password from the environment, if any.
//
// This is how a user avoids typing it at all: export ORACLE_PASSWORD once and
// every flow below picks it up.
func PasswordFromEnv() string {
	return os.Getenv(EnvOraclePassword)
}

// ValidatePort rejects a port huh could have accepted as text.
func ValidatePort(raw string) error {
	value, err := strconv.Atoi(strings.TrimSpace(raw))
	if err != nil {
		return errors.New("use a number between 1 and 65535")
	}
	if value < 1 || value > 65535 {
		return errors.New("use a number between 1 and 65535")
	}
	return nil
}

// ParsePort converts a validated port string.
func ParsePort(raw string) int {
	value, err := strconv.Atoi(strings.TrimSpace(raw))
	if err != nil || value < 1 || value > 65535 {
		return DefaultPort
	}
	return value
}

// ServerEnv builds the environment for the spawned Python service.
//
// The password is placed in the child's environment only. It is never an
// argument, never written to disk, and never logged.
func ServerEnv(oracleUser, oraclePassword, oracleDSN string) []string {
	env := os.Environ()
	if oracleUser != "" {
		env = append(env, EnvOracleUsername+"="+oracleUser)
	}
	if oraclePassword != "" {
		env = append(env, EnvOraclePassword+"="+oraclePassword)
	}
	if oracleDSN != "" {
		env = append(env, EnvOracleDSN+"="+oracleDSN)
	}
	return env
}

// Server is a spawned ragcli API process.
type Server struct {
	cmd    *exec.Cmd
	stderr strings.Builder
}

// Stop terminates the spawned service.
func (s *Server) Stop() {
	if s == nil || s.cmd == nil || s.cmd.Process == nil {
		return
	}
	_ = s.cmd.Process.Kill()
	_, _ = s.cmd.Process.Wait()
}

// Stderr returns whatever the service logged, for error reporting.
func (s *Server) Stderr() string { return s.stderr.String() }

// ServerArgs is the exact argv used to start the service.
//
// It is exported so a test can assert that no credential can ever appear here:
// /proc/<pid>/cmdline is world readable, so a secret in argv would leak it to
// every user on the box regardless of file permissions.
func ServerArgs(port int) []string {
	return []string{"uv", "run", "ragcli", "api", "--host", "127.0.0.1", "--port", strconv.Itoa(port)}
}

// LaunchServer starts the repo's own CLI as the service, using the interface
// the repo already documents (ragcli api --port N) rather than reimplementing
// it. The child inherits env, so ORACLE_PASSWORD reaches the service through
// config.yaml's ${ORACLE_PASSWORD} interpolation.
func LaunchServer(ctx context.Context, projectRoot string, port int, env []string) (*Server, error) {
	cmd := exec.Command(ServerArgs(port)[0], ServerArgs(port)[1:]...)
	cmd.Dir = projectRoot
	cmd.Env = env

	server := &Server{cmd: cmd}
	cmd.Stdout = io_discard{}
	cmd.Stderr = &server.stderr
	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("start ragcli api: %w", err)
	}
	return server, nil
}

// io_discard swallows the service's stdout; the TUI owns the screen.
type io_discard struct{}

func (io_discard) Write(p []byte) (int, error) { return len(p), nil }

// WaitForPort polls until the service accepts TCP connections, so the TUI
// shows a deterministic "starting" state instead of a connection error.
func WaitForPort(ctx context.Context, host string, port int, timeout time.Duration) error {
	deadline := time.Now().Add(timeout)
	address := net.JoinHostPort(host, strconv.Itoa(port))
	for {
		conn, err := net.DialTimeout("tcp", address, 500*time.Millisecond)
		if err == nil {
			_ = conn.Close()
			return nil
		}
		if time.Now().After(deadline) {
			return fmt.Errorf("service did not accept connections on %s within %s", address, timeout)
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(250 * time.Millisecond):
		}
	}
}
