package browsermesh

import (
	"context"
	"errors"
	"net/url"
)

// Create declares a new browser. The control plane's operator provisions it
// asynchronously; use WaitReady (or WithBrowser) before driving it.
func (c *Client) Create(ctx context.Context, opts CreateOptions) (Browser, error) {
	if err := c.requireControlPlane(); err != nil {
		return Browser{}, err
	}
	body := map[string]any{}
	if opts.Type != "" {
		body["type"] = opts.Type
	}
	if opts.TimeoutSeconds > 0 {
		body["timeout_seconds"] = opts.TimeoutSeconds
	}
	var created struct {
		ID     string `json:"browser_id"`
		Name   string `json:"name"`
		Status string `json:"status"`
	}
	if err := c.do(ctx, "POST", "/browsers", body, &created); err != nil {
		return Browser{}, err
	}
	return Browser{ID: created.ID, Name: created.Name, Status: created.Status}, nil
}

// List returns all known browsers.
func (c *Client) List(ctx context.Context) ([]Browser, error) {
	if err := c.requireControlPlane(); err != nil {
		return nil, err
	}
	var out BrowserList
	if err := c.do(ctx, "GET", "/browsers", nil, &out); err != nil {
		return nil, err
	}
	return out.Browsers, nil
}

// Get returns a single browser by id.
func (c *Client) Get(ctx context.Context, id string) (Browser, error) {
	if err := c.requireControlPlane(); err != nil {
		return Browser{}, err
	}
	var b Browser
	if err := c.do(ctx, "GET", "/browsers/"+url.PathEscape(id), nil, &b); err != nil {
		return Browser{}, err
	}
	return b, nil
}

// Delete stops a browser (the Pod is garbage-collected by the operator).
func (c *Client) Delete(ctx context.Context, id string) error {
	if err := c.requireControlPlane(); err != nil {
		return err
	}
	return c.do(ctx, "DELETE", "/browsers/"+url.PathEscape(id), nil, nil)
}

// ViewerToken mints a short-lived token so a browser can open the noVNC
// WebSocket (which cannot send headers). Append it as ?token= to VNCURL.
func (c *Client) ViewerToken(ctx context.Context, id string) (string, error) {
	if err := c.requireControlPlane(); err != nil {
		return "", err
	}
	var out struct {
		Token string `json:"token"`
	}
	if err := c.do(ctx, "POST", "/browsers/"+url.PathEscape(id)+"/viewer-token", nil, &out); err != nil {
		return "", err
	}
	return out.Token, nil
}

// CDPURL returns the WebSocket URL to drive the browser over CDP.
//
// Control plane: built from the base URL and API key (the key is embedded as
// ?api_key= so header-less clients can authenticate); id is required.
// Serverless: resolved from the container's /json/version, where the gateway
// has rewritten it to wss://<host>/devtools/browser/<id>; id is ignored.
func (c *Client) CDPURL(ctx context.Context, id string) (string, error) {
	if c.serverless {
		return c.resolveCDP(ctx)
	}
	u, err := url.Parse(c.baseURL)
	if err != nil {
		return "", err
	}
	if u.Scheme == "https" {
		u.Scheme = "wss"
	} else {
		u.Scheme = "ws"
	}
	u.Path = "/browsers/" + id + "/cdp"
	q := u.Query()
	q.Set("api_key", c.apiKey)
	u.RawQuery = q.Encode()
	return u.String(), nil
}

// VNCURL returns the live viewer URL. Serverless: the container's self-contained
// viewer at `/watch` (open it to watch the browser). Control-plane: use
// ViewerToken(id) and append ?token= to the browser's VNCURL.
func (c *Client) VNCURL() (string, error) {
	if !c.serverless {
		return "", errors.New("browsermesh: VNCURL is serverless-only; use ViewerToken + the browser's VNCURL")
	}
	return c.baseURL + "/watch", nil
}

func (c *Client) resolveCDP(ctx context.Context) (string, error) {
	var v struct {
		WebSocketDebuggerURL string `json:"webSocketDebuggerUrl"`
	}
	if err := c.do(ctx, "GET", "/json/version", nil, &v); err != nil {
		return "", err
	}
	if v.WebSocketDebuggerURL == "" {
		return "", errors.New("browsermesh: browser has no CDP endpoint yet")
	}
	return v.WebSocketDebuggerURL, nil
}
