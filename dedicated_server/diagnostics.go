package main

import (
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
)

// SDK debug messages contain protocol frames. Never record those frames or
// environment dumps: they can contain reservation IDs and authentication data.
type sdkDiagnostics struct{}

func (sdkDiagnostics) Debugf(string, ...any) {}
func (sdkDiagnostics) Warnf(pattern string, args ...any) {
	log.Printf("sdk_warning: "+pattern, args...)
}
func (sdkDiagnostics) Errorf(pattern string, args ...any) { log.Printf("sdk_error: "+pattern, args...) }

type diagnosticWriter struct {
	mu      sync.Mutex
	output  io.Writer
	file    *os.File
	secrets []string
}

var urlQuery = regexp.MustCompile(`(https?|wss?)://[^\s"<>]+`)

func redactDiagnostic(message string, secrets []string) string {
	for _, secret := range secrets {
		if secret != "" {
			message = strings.ReplaceAll(message, secret, "[REDACTED]")
		}
	}
	return urlQuery.ReplaceAllStringFunc(message, func(address string) string {
		if query := strings.IndexByte(address, '?'); query >= 0 {
			return address[:query] + "?[REDACTED]"
		}
		return address
	})
}

func (writer *diagnosticWriter) Write(data []byte) (int, error) {
	writer.mu.Lock()
	defer writer.mu.Unlock()
	message := redactDiagnostic(string(data), writer.secrets)
	if _, err := io.WriteString(writer.output, message); err != nil {
		return 0, err
	}
	// Startup breadcrumbs survive an unexpected process exit.
	if writer.file != nil {
		if err := writer.file.Sync(); err != nil {
			return 0, err
		}
	}
	return len(data), nil
}

func configureDiagnostics(path string) (func(), error) {
	if err := os.MkdirAll(filepath.Dir(path), 0700); err != nil {
		return nil, err
	}
	file, err := os.OpenFile(path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0600)
	if err != nil {
		return nil, err
	}
	var secrets []string
	for _, name := range []string{"GAMELIFT_SDK_AUTH_TOKEN", "GAMELIFT_ACCESS_KEY", "GAMELIFT_SECRET_KEY", "GAMELIFT_SESSION_TOKEN", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"} {
		if value := os.Getenv(name); value != "" {
			secrets = append(secrets, value)
		}
	}
	previous, previousFlags := log.Writer(), log.Flags()
	log.SetOutput(&diagnosticWriter{output: io.MultiWriter(os.Stderr, file), file: file, secrets: secrets})
	log.SetFlags(log.LstdFlags | log.LUTC | log.Lmicroseconds)
	log.Printf("stage=diagnostics_open file=%s", path)
	return func() { log.SetOutput(previous); log.SetFlags(previousFlags); file.Close() }, nil
}

func logCleanup(stage string, err error) {
	if err != nil {
		log.Print(fmt.Sprintf("stage=%s failed: %v", stage, err))
		return
	}
	log.Printf("stage=%s complete", stage)
}
