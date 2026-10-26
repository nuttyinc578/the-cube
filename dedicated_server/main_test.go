package main

import (
	"context"
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"errors"
	"fmt"
	"io"
	"math/big"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/amazon-gamelift/amazon-gamelift-servers-go-server-sdk/v5/model"
	"github.com/amazon-gamelift/amazon-gamelift-servers-go-server-sdk/v5/server"
)

// A normal child process, standing in for Python only in lifecycle unit tests.
// The separate two-player integration check runs the real Python CPE worker.
func TestPhysicsHelper(t *testing.T) {
	if len(os.Args) < 3 || os.Args[len(os.Args)-2] != "cube-worker-helper" {
		return
	}
	mode := os.Args[len(os.Args)-1]
	if mode == "exit-before-ready" {
		os.Exit(7)
	}
	if mode != "no-ready" {
		fmt.Println(`{"type":"ready"}`)
	}
	if mode == "exit-after-ready" {
		time.Sleep(200 * time.Millisecond)
		os.Exit(9)
	}
	_, _ = io.Copy(io.Discard, os.Stdin)
	os.Exit(0)
}

func certificateFixture(t *testing.T) string {
	t.Helper()
	directory := t.TempDir()
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatal(err)
	}
	template := &x509.Certificate{SerialNumber: big.NewInt(1), Subject: pkix.Name{CommonName: "localhost"}, DNSNames: []string{"localhost"}, NotBefore: time.Now().Add(-time.Hour), NotAfter: time.Now().Add(time.Hour), KeyUsage: x509.KeyUsageDigitalSignature | x509.KeyUsageKeyEncipherment, ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth}}
	der, err := x509.CreateCertificate(rand.Reader, template, template, &key.PublicKey, key)
	if err != nil {
		t.Fatal(err)
	}
	certificate := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: der})
	privateKey := pem.EncodeToMemory(&pem.Block{Type: "RSA PRIVATE KEY", Bytes: x509.MarshalPKCS1PrivateKey(key)})
	for name, data := range map[string][]byte{"certificate.pem": certificate, "certificateChain.pem": certificate, "privateKey.pem": privateKey} {
		if err := os.WriteFile(filepath.Join(directory, name), data, 0600); err != nil {
			t.Fatal(err)
		}
	}
	return directory
}

func TestManagedLifecycle(t *testing.T) {
	directory := certificateFixture(t)
	for _, scenario := range []struct{ name, worker, failure, expected string }{
		{"terminate-callback", "ready", "", ""},
		{"context-shutdown", "ready", "", ""},
		{"sdk-init-failure", "ready", "init", "sdk_init:"},
		{"certificate-request-failure", "ready", "certificate", "compute_certificate:"},
		{"certificate-file-failure", "ready", "directory", "certificate_chain_read:"},
		{"process-ready-failure", "ready", "ready", "process_ready:"},
		{"worker-exit-before-ready", "exit-before-ready", "", "worker_exit_before_ready:"},
		{"worker-exit-while-serving", "exit-after-ready", "", "worker_exit_while_serving:"},
		{"worker-timeout", "no-ready", "", "physics_startup_timeout"},
	} {
		t.Run(scenario.name, func(t *testing.T) {
			ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			defer cancel()
			var calls []string
			call := func(name string) error {
				calls = append(calls, name)
				if scenario.failure == name {
					return errors.New("simulated dependency unavailable")
				}
				return nil
			}
			logPath := filepath.Join(t.TempDir(), "startup.log")
			lift := liftAPI{
				init: func() error { return call("init") },
				certificateDirectory: func() (string, error) {
					err := call("certificate")
					if scenario.failure == "directory" {
						return t.TempDir(), nil
					}
					return directory, err
				},
				activate: func() error { return call("activate") },
				ending:   func() error { return call("ending") },
				destroy:  func() error { return call("destroy") },
			}
			lift.ready = func(parameters server.ProcessParameters) error {
				if !parameters.OnHealthCheck() {
					t.Error("worker must be healthy before ProcessReady")
				}
				if len(parameters.LogParameters.LogPaths) != 1 || parameters.LogParameters.LogPaths[0] != logPath {
					t.Error("diagnostic log not registered for collection")
				}
				if err := call("ready"); err != nil {
					return err
				}
				parameters.OnStartGameSession(model.GameSession{})
				if scenario.name == "context-shutdown" {
					cancel()
				} else if scenario.worker == "ready" {
					parameters.OnProcessTerminate()
				}
				return nil
			}
			timeout := 3 * time.Second
			if scenario.worker == "no-ready" {
				timeout = 100 * time.Millisecond
			}
			options := hostOptions{command: []string{os.Args[0], "-test.run=^TestPhysicsHelper$", "--", "cube-worker-helper", scenario.worker}, port: 0, logPath: logPath, startupTimeout: timeout}
			err := run(ctx, options, lift)
			if scenario.expected == "" && err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if scenario.expected != "" && (err == nil || !strings.Contains(err.Error(), scenario.expected)) {
				t.Fatalf("expected %q; got %v", scenario.expected, err)
			}
			var want []string
			switch {
			case strings.HasPrefix(scenario.worker, "exit-before"), scenario.worker == "no-ready":
			case scenario.failure == "init":
				want = []string{"init", "destroy"}
			case scenario.failure == "certificate", scenario.failure == "directory":
				want = []string{"init", "certificate", "ending", "destroy"}
			case scenario.failure == "ready":
				want = []string{"init", "certificate", "ready", "ending", "destroy"}
			default:
				want = []string{"init", "certificate", "ready", "activate", "ending", "destroy"}
			}
			if strings.Join(calls, ",") != strings.Join(want, ",") {
				t.Fatalf("lifecycle order: got %v, want %v", calls, want)
			}
		})
	}
}

func TestWorkerStartFailure(t *testing.T) {
	err := run(context.Background(), hostOptions{command: []string{filepath.Join(t.TempDir(), "absent-worker")}}, liftAPI{})
	if err == nil || !strings.Contains(err.Error(), "worker_start:") {
		t.Fatalf("missing worker diagnostic: %v", err)
	}
}

func TestPrivateDiagnostics(t *testing.T) {
	const fakeToken = "unit-test-secret-not-a-real-token"
	t.Setenv("GAMELIFT_SDK_AUTH_TOKEN", fakeToken)
	path := filepath.Join(t.TempDir(), "private-logs", "server.log")
	closeLog, err := configureDiagnostics(path)
	if err != nil {
		t.Fatal(err)
	}
	sdkDiagnostics{}.Warnf("example %s wss://localhost/path?auth_token=hidden", fakeToken)
	sdkDiagnostics{}.Debugf("protocol frame must not be logged")
	closeLog()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	message := string(data)
	if strings.Contains(message, fakeToken) || strings.Contains(message, "auth_token=hidden") || strings.Contains(message, "protocol frame") {
		t.Fatalf("sensitive diagnostics recorded")
	}
	if !strings.Contains(message, "[REDACTED]") || !strings.Contains(message, "stage=diagnostics_open") {
		t.Error("missing sanitized diagnostic")
	}
}
