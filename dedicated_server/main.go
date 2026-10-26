package main

import (
	"bufio"
	"context"
	"crypto/tls"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"log"
	"net"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"sync"
	"sync/atomic"
	"syscall"
	"time"

	"github.com/amazon-gamelift/amazon-gamelift-servers-go-server-sdk/v5/model"
	"github.com/amazon-gamelift/amazon-gamelift-servers-go-server-sdk/v5/server"
)

type peer struct {
	connection net.Conn
	packets    chan []byte
	player     string
}
type game struct {
	clients sync.Map
	input   io.WriteCloser
	writeMu sync.Mutex
	healthy atomic.Bool
	active  atomic.Bool
	next    atomic.Uint64
	local   bool
	lift    liftAPI
}

func (g *game) sendAction(player string, data any) {
	packet, err := json.Marshal(map[string]any{"player": player, "data": data})
	if err != nil {
		return
	}
	g.writeMu.Lock()
	defer g.writeMu.Unlock()
	if _, err = g.input.Write(append(packet, '\n')); err != nil {
		g.healthy.Store(false)
	}
}
func (g *game) handle(c net.Conn) {
	defer c.Close()
	_ = c.SetDeadline(time.Now().Add(15 * time.Second))
	scan := bufio.NewScanner(c)
	scan.Buffer(make([]byte, 4096), 4096)
	if !scan.Scan() {
		return
	}
	var hello struct {
		Type     string `json:"type"`
		Protocol string `json:"protocol"`
		Session  string `json:"player_session_id"`
	}
	if json.Unmarshal(scan.Bytes(), &hello) != nil || hello.Type != "join" || hello.Protocol != "cube-json-tls-v1" || len(hello.Session) > 150 {
		return
	}
	if !g.active.Load() {
		return
	}
	if !g.local {
		if err := g.lift.accept(hello.Session); err != nil {
			return
		}
		defer g.lift.remove(hello.Session)
	}
	p := &peer{c, make(chan []byte, 4), fmt.Sprintf("guest-%d", g.next.Add(1))}
	// GameLift reserves slots, while this cap also bounds local resource usage.
	n := 0
	g.clients.Range(func(_, _ any) bool { n++; return true })
	if n >= 4 {
		return
	}
	g.clients.Store(p, p)
	defer g.clients.Delete(p)
	defer g.sendAction(p.player, map[string]string{"action": "disconnect"})
	_ = c.SetDeadline(time.Time{})
	stopped := make(chan struct{})
	defer close(stopped)
	go func() {
		for {
			select {
			case packet := <-p.packets:
				_ = c.SetWriteDeadline(time.Now().Add(3 * time.Second))
				if _, err := c.Write(packet); err != nil {
					c.Close()
					return
				}
			case <-stopped:
				return
			}
		}
	}()
	window := time.Now()
	total, heavy := 0, 0
	for {
		_ = c.SetReadDeadline(time.Now().Add(90 * time.Second))
		if !scan.Scan() {
			return
		}
		if time.Since(window) >= time.Second {
			window = time.Now()
			total = 0
			heavy = 0
		}
		total++
		if total > 90 {
			return
		}
		var action struct {
			Type string         `json:"type"`
			Data map[string]any `json:"data"`
		}
		if json.Unmarshal(scan.Bytes(), &action) != nil || action.Type != "action" {
			continue
		}
		kind, _ := action.Data["action"].(string)
		switch kind {
		case "drag_start", "drag_move", "drag_end":
		case "spawn", "burst", "spawn_rain", "event":
			heavy++
			if heavy > 8 {
				continue
			}
		default:
			continue
		}
		g.sendAction(p.player, action.Data)
	}
}
func main() {
	local := flag.Bool("local", false, "Local integration only; bind loopback and bypass GameLift reservations")
	port := flag.Int("port", 27100, "Game TCP port")
	python := flag.String("python", "python3", "Headless Python runtime")
	worker := flag.String("worker", "worker.py", "Physics worker path")
	certPath := flag.String("cert", "", "Local TLS certificate")
	keyPath := flag.String("key", "", "Local TLS private key")
	logPath := flag.String("log-file", filepath.Join(os.TempDir(), "cube-server-logs", fmt.Sprintf("server-%d.log", os.Getpid())), "Private startup/worker/SDK diagnostic log")
	flag.Parse()
	absoluteLogPath, err := filepath.Abs(*logPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, "Invalid diagnostic log path:", err)
		os.Exit(1)
	}
	*logPath = absoluteLogPath
	// The SDK's default logger creates ./logs and calls log.Fatal if the game
	// directory is read-only. Use our writable log and never depend on the cwd.
	closeLog, err := configureDiagnostics(*logPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, "Cannot open dedicated-server diagnostic log:", err)
		os.Exit(1)
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	options := hostOptions{local: *local, port: *port, command: []string{*python, *worker}, cert: *certPath, key: *keyPath, logPath: *logPath, startupTimeout: 60 * time.Second}
	err = run(ctx, options, realLift())
	stop()
	if err != nil {
		log.Printf("host_failed: %v", err)
	}
	closeLog()
	if err != nil {
		os.Exit(1)
	}
}

type hostOptions struct {
	local              bool
	port               int
	command            []string
	cert, key, logPath string
	startupTimeout     time.Duration
}

// Only the adapter calls AWS. Tests exercise the managed lifecycle with a fake
// adapter; no test can create a fleet or spend on hosting.
type liftAPI struct {
	init                      func() error
	certificateDirectory      func() (string, error)
	ready                     func(server.ProcessParameters) error
	activate, ending, destroy func() error
	accept, remove            func(string) error
}

func realLift() liftAPI {
	return liftAPI{
		init: func() error {
			server.SetLoggerInterface(sdkDiagnostics{})
			return server.InitSDK(server.ServerParameters{})
		},
		certificateDirectory: func() (string, error) {
			certificate, err := server.GetComputeCertificate()
			return certificate.CertificatePath, err
		},
		ready: server.ProcessReady, activate: server.ActivateGameSession,
		ending: server.ProcessEnding, destroy: server.Destroy,
		accept: server.AcceptPlayerSession, remove: server.RemovePlayerSession,
	}
}

func run(ctx context.Context, options hostOptions, lift liftAPI) error {
	log.Printf("stage=host_start mode_local=%t", options.local)
	if len(options.command) == 0 {
		return errors.New("worker_start: no command configured")
	}
	g := &game{local: options.local, lift: lift}
	defer func() { g.active.Store(false); g.healthy.Store(false) }()
	cmd := exec.Command(options.command[0], options.command[1:]...)
	cmd.Stderr = log.Writer()
	input, err := cmd.StdinPipe()
	if err != nil {
		return fmt.Errorf("worker_stdin: %w", err)
	}
	defer input.Close()
	g.input = input
	output, err := cmd.StdoutPipe()
	if err != nil {
		return fmt.Errorf("worker_stdout: %w", err)
	}
	if err = cmd.Start(); err != nil {
		return fmt.Errorf("worker_start: %w", err)
	}
	log.Print("stage=worker_started")
	ready := make(chan struct{})
	workerDone := make(chan error, 1)
	workerStopped := make(chan struct{})
	defer func() {
		input.Close()
		select {
		case <-workerStopped:
		case <-time.After(3 * time.Second):
			_ = cmd.Process.Kill()
			<-workerStopped
		}
		log.Print("stage=worker_stopped")
	}()
	go func() {
		scan := bufio.NewScanner(output)
		scan.Buffer(make([]byte, 65536), 1024*1024)
		first := true
		for scan.Scan() {
			packet := append(append([]byte{}, scan.Bytes()...), '\n')
			var header struct {
				Type string `json:"type"`
			}
			if json.Unmarshal(packet, &header) != nil {
				continue
			}
			if first && header.Type == "ready" {
				first = false
				g.healthy.Store(true)
				close(ready)
				continue
			}
			if header.Type != "snapshot" {
				continue
			}
			g.clients.Range(func(_, value any) bool {
				p := value.(*peer)
				select {
				case p.packets <- packet:
				default:
					p.connection.Close()
				}
				return true
			})
		}
		g.healthy.Store(false)
		scanErr := scan.Err()
		waitErr := cmd.Wait()
		if scanErr != nil {
			waitErr = scanErr
		}
		workerDone <- waitErr
		close(workerStopped)
	}()
	timer := time.NewTimer(options.startupTimeout)
	defer timer.Stop()
	select {
	case <-ready:
		log.Print("stage=physics_ready")
	case err := <-workerDone:
		return fmt.Errorf("worker_exit_before_ready: %v", err)
	case <-ctx.Done():
		return nil
	case <-timer.C:
		return errors.New("physics_startup_timeout")
	}
	var chain []byte
	if !options.local {
		log.Print("stage=sdk_init_begin")
		// Destroy also cleans up a partially initialized SDK on InitSDK failure.
		defer func() { logCleanup("sdk_destroy", lift.destroy()) }()
		if err = lift.init(); err != nil {
			return fmt.Errorf("sdk_init: %w", err)
		}
		log.Print("stage=sdk_initialized")
		// The callback only closes the listener; this common defer sends
		// ProcessEnding once, even if startup or a worker later fails.
		defer func() { logCleanup("process_ending", lift.ending()) }()
		log.Print("stage=certificate_request_begin")
		directory, err := lift.certificateDirectory()
		if err != nil {
			return fmt.Errorf("compute_certificate: %w", err)
		}
		if directory == "" {
			return errors.New("compute_certificate: empty directory")
		}
		options.cert = filepath.Join(directory, "certificate.pem")
		options.key = filepath.Join(directory, "privateKey.pem")
		chain, err = os.ReadFile(filepath.Join(directory, "certificateChain.pem"))
		if err != nil {
			return fmt.Errorf("certificate_chain_read: %w", err)
		}
	} else {
		g.active.Store(true)
	}
	certPEM, err := os.ReadFile(options.cert)
	if err != nil {
		return fmt.Errorf("certificate_read: %w", err)
	}
	keyPEM, err := os.ReadFile(options.key)
	if err != nil {
		return fmt.Errorf("private_key_read: %w", err)
	}
	certificate, err := tls.X509KeyPair(append(append(certPEM, '\n'), chain...), keyPEM)
	if err != nil {
		return fmt.Errorf("tls_key_pair: %w", err)
	}
	log.Print("stage=tls_certificate_loaded")
	address := fmt.Sprintf(":%d", options.port)
	if options.local {
		address = "127.0.0.1" + address
	}
	listener, err := tls.Listen("tcp", address, &tls.Config{Certificates: []tls.Certificate{certificate}, MinVersion: tls.VersionTLS12})
	if err != nil {
		return fmt.Errorf("tls_listen: %w", err)
	}
	defer listener.Close()
	defer g.clients.Range(func(_, value any) bool { value.(*peer).connection.Close(); return true })
	log.Print("stage=tls_listening")
	if !options.local {
		log.Print("stage=process_ready_begin")
		err = lift.ready(server.ProcessParameters{
			OnStartGameSession: func(model.GameSession) {
				if e := lift.activate(); e == nil {
					g.active.Store(true)
				} else {
					g.healthy.Store(false)
					log.Printf("activate_game_session_failed: %v", e)
				}
			},
			OnUpdateGameSession: func(model.UpdateGameSession) {},
			OnProcessTerminate:  func() { g.active.Store(false); g.healthy.Store(false); listener.Close() },
			OnHealthCheck:       func() bool { return g.healthy.Load() }, Port: options.port,
			LogParameters: server.LogParameters{LogPaths: []string{options.logPath}},
		})
		if err != nil {
			return fmt.Errorf("process_ready: %w", err)
		}
		log.Print("stage=process_ready_complete")
	}
	servingDone := make(chan struct{})
	defer close(servingDone)
	serveErr := make(chan error, 1)
	go func() {
		select {
		case <-ctx.Done():
			serveErr <- nil
		case err := <-workerDone:
			serveErr <- fmt.Errorf("worker_exit_while_serving: %v", err)
		case <-servingDone:
			return
		}
		g.healthy.Store(false)
		listener.Close()
	}()
	log.Printf("Dedicated server ready on port %d", options.port)
	admission := make(chan struct{}, 32)
	for {
		connection, e := listener.Accept()
		if e != nil {
			select {
			case err := <-serveErr:
				return err
			default:
				if errors.Is(e, net.ErrClosed) {
					return nil
				}
				return fmt.Errorf("tls_accept: %w", e)
			}
		}
		select {
		case admission <- struct{}{}:
			go func() { defer func() { <-admission }(); g.handle(connection) }()
		default:
			connection.Close()
		}
	}
}
