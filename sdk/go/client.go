// Package browsermesh is a small, dependency-free Go client for the BrowserMesh
// control plane. It covers the browser lifecycle (create/list/get/delete) and
// the CDP endpoint used to drive a browser.
package browsermesh

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"strings"
	"time"
)

// Client talks to a BrowserMesh control plane, or (in serverless mode) to a
// single standalone Cloud Run browser.
type Client struct {
	baseURL    string
	apiKey     string
	serverless bool
	http       *http.Client
}

// NewClient builds a control-plane client. Both the base URL and the API key
// are required.
//
//	baseURL: e.g. "http://127.0.0.1:30080"
//	apiKey:  a key created in the dashboard, e.g. "bmsk_..."
func NewClient(baseURL, apiKey string) (*Client, error) {
	if strings.TrimSpace(baseURL) == "" {
		return nil, errors.New("browsermesh: base URL is required")
	}
	if strings.TrimSpace(apiKey) == "" {
		return nil, errors.New("browsermesh: API key is required")
	}
	return newClient(baseURL, apiKey, false), nil
}

// NewServerlessClient builds a client for a single Cloud Run browser. There is
// no control plane (no create/list/delete): the service URL *is* one on-demand
// browser. apiKey is optional — pass one only if the service requires auth.
func NewServerlessClient(baseURL, apiKey string) (*Client, error) {
	if strings.TrimSpace(baseURL) == "" {
		return nil, errors.New("browsermesh: base URL is required")
	}
	return newClient(baseURL, apiKey, true), nil
}

func newClient(baseURL, apiKey string, serverless bool) *Client {
	return &Client{
		baseURL:    strings.TrimRight(baseURL, "/"),
		apiKey:     apiKey,
		serverless: serverless,
		http:       &http.Client{Timeout: 30 * time.Second},
	}
}

func (c *Client) requireControlPlane() error {
	if c.serverless {
		return errors.New("browsermesh: not available in serverless mode (no control plane)")
	}
	return nil
}

// do sends a JSON request and decodes the response into out.
func (c *Client) do(ctx context.Context, method, path string, body, out any) error {
	var rdr io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			return err
		}
		rdr = bytes.NewReader(b)
	}

	req, err := http.NewRequestWithContext(ctx, method, c.baseURL+path, rdr)
	if err != nil {
		return err
	}
	if c.apiKey != "" {
		req.Header.Set("Authorization", "Bearer "+c.apiKey)
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	res, err := c.http.Do(req)
	if err != nil {
		return err
	}
	defer res.Body.Close()

	if res.StatusCode >= 300 {
		return parseError(res)
	}
	if out == nil {
		return nil
	}
	return json.NewDecoder(res.Body).Decode(out)
}
