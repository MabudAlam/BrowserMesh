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

// Client talks to a BrowserMesh control plane.
type Client struct {
	baseURL string
	apiKey  string
	http    *http.Client
}

// NewClient builds a client. Both the base URL and the API key are required.
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
	return &Client{
		baseURL: strings.TrimRight(baseURL, "/"),
		apiKey:  apiKey,
		http:    &http.Client{Timeout: 30 * time.Second},
	}, nil
}

// do sends a JSON request to the control plane and decodes the response into out.
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
	req.Header.Set("Authorization", "Bearer "+c.apiKey)
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
