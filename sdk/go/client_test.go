package browsermesh

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestNewClientValidation(t *testing.T) {
	if _, err := NewClient("", "k"); err == nil {
		t.Fatal("expected error for empty base URL")
	}
	if _, err := NewClient("http://x", ""); err == nil {
		t.Fatal("expected error for empty API key")
	}
	if _, err := NewClient("http://x", "k"); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestCreateGetDeleteAndAuth(t *testing.T) {
	var gotAuth string
	mux := http.NewServeMux()
	mux.HandleFunc("POST /browsers", func(w http.ResponseWriter, r *http.Request) {
		gotAuth = r.Header.Get("Authorization")
		w.Write([]byte(`{"browser_id":"abc123","name":"br-abc123","status":"starting","type":"cloak"}`))
	})
	mux.HandleFunc("GET /browsers/abc123", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"browser_id":"abc123","name":"br-abc123","status":"Running","pod_ip":"10.0.0.1"}`))
	})
	mux.HandleFunc("DELETE /browsers/abc123", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"browser_id":"abc123","status":"deleted"}`))
	})
	srv := httptest.NewServer(mux)
	defer srv.Close()

	c, err := NewClient(srv.URL, "bmsk_test")
	if err != nil {
		t.Fatal(err)
	}
	ctx := context.Background()

	created, err := c.Create(ctx, CreateOptions{Type: "cloak"})
	if err != nil || created.ID != "abc123" {
		t.Fatalf("create: %v %+v", err, created)
	}
	if gotAuth != "Bearer bmsk_test" {
		t.Fatalf("expected bearer auth, got %q", gotAuth)
	}

	b, err := c.WaitReady(ctx, "abc123") // first Get already Running
	if err != nil || b.Status != "Running" {
		t.Fatalf("waitReady: %v %+v", err, b)
	}
	if err := c.Delete(ctx, "abc123"); err != nil {
		t.Fatalf("delete: %v", err)
	}
}

func TestAPIError(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNotFound)
		w.Write([]byte(`{"error":"http_error","detail":"Browser not found"}`))
	}))
	defer srv.Close()

	c, _ := NewClient(srv.URL, "bmsk_test")
	_, err := c.Get(context.Background(), "nope")
	apiErr, ok := err.(*APIError)
	if !ok {
		t.Fatalf("expected *APIError, got %T", err)
	}
	if !apiErr.IsNotFound() || apiErr.Detail != "Browser not found" {
		t.Fatalf("bad error: %+v", apiErr)
	}
}

func TestCDPURL(t *testing.T) {
	c, _ := NewClient("http://127.0.0.1:30080", "bmsk_abc")
	u, err := c.CDPURL("xyz")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.HasPrefix(u, "ws://127.0.0.1:30080/browsers/xyz/cdp?") || !strings.Contains(u, "api_key=bmsk_abc") {
		t.Fatalf("unexpected CDP url: %s", u)
	}
}
