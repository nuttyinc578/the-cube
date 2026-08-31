package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
)

const maxCacheBytes = 2 << 20

type cacheStore struct {
	mu        sync.RWMutex
	state     json.RawMessage
	updatedAt time.Time
	version   atomic.Uint64
}

func newCacheStore() *cacheStore {
	return &cacheStore{state: json.RawMessage(`{"engine":"CPE","bodies":[],"particles":[]}`)}
}

func (store *cacheStore) put(payload json.RawMessage) uint64 {
	copyOfPayload := append(json.RawMessage(nil), payload...)
	store.mu.Lock()
	store.state = copyOfPayload
	store.updatedAt = time.Now().UTC()
	store.mu.Unlock()
	return store.version.Add(1)
}

func (store *cacheStore) get() (json.RawMessage, time.Time, uint64) {
	store.mu.RLock()
	payload := append(json.RawMessage(nil), store.state...)
	updated := store.updatedAt
	store.mu.RUnlock()
	return payload, updated, store.version.Load()
}

func writeJSON(response http.ResponseWriter, status int, value any) {
	response.Header().Set("Content-Type", "application/json; charset=utf-8")
	response.Header().Set("Cache-Control", "no-store")
	response.Header().Set("Access-Control-Allow-Origin", "*")
	response.Header().Set("Access-Control-Allow-Headers", "Content-Type")
	response.Header().Set("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
	response.WriteHeader(status)
	_ = json.NewEncoder(response).Encode(value)
}

func newHandler(store *cacheStore) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(response http.ResponseWriter, request *http.Request) {
		if request.Method != http.MethodGet {
			writeJSON(response, http.StatusMethodNotAllowed, map[string]any{"ok": false, "error": "method not allowed"})
			return
		}
		writeJSON(response, http.StatusOK, map[string]any{
			"ok":        true,
			"service":   "cpe-go-cache",
			"port_role": "cube_core cache",
			"version":   store.version.Load(),
		})
	})
	mux.HandleFunc("/cache", func(response http.ResponseWriter, request *http.Request) {
		if request.Method == http.MethodOptions {
			writeJSON(response, http.StatusNoContent, map[string]any{})
			return
		}
		switch request.Method {
		case http.MethodPost:
			request.Body = http.MaxBytesReader(response, request.Body, maxCacheBytes)
			payload, err := io.ReadAll(request.Body)
			if err != nil {
				writeJSON(response, http.StatusRequestEntityTooLarge, map[string]any{"ok": false, "error": "cache body is too large"})
				return
			}
			if len(payload) == 0 || !json.Valid(payload) {
				writeJSON(response, http.StatusBadRequest, map[string]any{"ok": false, "error": "cache must be valid JSON"})
				return
			}
			version := store.put(payload)
			writeJSON(response, http.StatusAccepted, map[string]any{"ok": true, "version": version})
		case http.MethodGet:
			payload, updated, version := store.get()
			writeJSON(response, http.StatusOK, map[string]any{
				"ok":         true,
				"version":    version,
				"updated_at": updated,
				"state":      payload,
			})
		default:
			writeJSON(response, http.StatusMethodNotAllowed, map[string]any{"ok": false, "error": "method not allowed"})
		}
	})
	return mux
}

func environmentPort() int {
	value := os.Getenv("CPE_GO_CACHE_PORT")
	if value == "" {
		value = os.Getenv("PORT")
	}
	port, err := strconv.Atoi(value)
	if err != nil || port < 1 || port > 65535 {
		return 4311
	}
	return port
}

func main() {
	host := flag.String("host", "127.0.0.1", "IP address used by the CPE cache service")
	port := flag.Int("port", environmentPort(), "HTTP port used by the CPE cache service")
	flag.Parse()

	server := &http.Server{
		Addr:              fmt.Sprintf("%s:%d", *host, *port),
		Handler:           newHandler(newCacheStore()),
		ReadHeaderTimeout: 3 * time.Second,
		ReadTimeout:       5 * time.Second,
		WriteTimeout:      5 * time.Second,
		IdleTimeout:       30 * time.Second,
	}

	stopped := make(chan os.Signal, 1)
	signal.Notify(stopped, os.Interrupt, syscall.SIGTERM)
	go func() {
		<-stopped
		ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		defer cancel()
		_ = server.Shutdown(ctx)
	}()

	ready, _ := json.Marshal(map[string]any{"ready": true, "service": "cpe-go-cache", "host": *host, "port": *port})
	fmt.Println(string(ready))
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatal(err)
	}
}
