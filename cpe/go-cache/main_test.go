package main

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestCacheRoundTrip(t *testing.T) {
	server := httptest.NewServer(newHandler(newCacheStore()))
	defer server.Close()

	payload := []byte(`{"engine":"CPE","cache_source":"cube_core","bodies":[{"id":7}],"particle_count":12}`)
	response, err := http.Post(server.URL+"/cache", "application/json", bytes.NewReader(payload))
	if err != nil {
		t.Fatal(err)
	}
	if response.StatusCode != http.StatusAccepted {
		t.Fatalf("expected 202, got %d", response.StatusCode)
	}
	_ = response.Body.Close()

	response, err = http.Get(server.URL + "/cache")
	if err != nil {
		t.Fatal(err)
	}
	defer response.Body.Close()
	var result struct {
		OK      bool            `json:"ok"`
		Version uint64          `json:"version"`
		State   json.RawMessage `json:"state"`
	}
	if err := json.NewDecoder(response.Body).Decode(&result); err != nil {
		t.Fatal(err)
	}
	if !result.OK || result.Version != 1 || !bytes.Contains(result.State, []byte(`"cube_core"`)) {
		t.Fatalf("unexpected cache response: %+v", result)
	}
}

func TestRejectsInvalidJSON(t *testing.T) {
	request := httptest.NewRequest(http.MethodPost, "/cache", bytes.NewBufferString("not-json"))
	response := httptest.NewRecorder()
	newHandler(newCacheStore()).ServeHTTP(response, request)
	if response.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", response.Code)
	}
}
