package browsermesh

import (
	"context"
	"net/url"
)

// Create declares a new browser. The control plane's operator provisions it
// asynchronously; use WaitReady (or WithBrowser) before driving it.
func (c *BrowserMeshClient) Create(ctx context.Context, opts BrowserMeshOptions) (Browser, error) {
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
func (c *BrowserMeshClient) List(ctx context.Context) ([]Browser, error) {
	var out BrowserList
	if err := c.do(ctx, "GET", "/browsers", nil, &out); err != nil {
		return nil, err
	}
	return out.Browsers, nil
}

// Get returns a single browser by id.
func (c *BrowserMeshClient) Get(ctx context.Context, id string) (Browser, error) {
	var b Browser
	if err := c.do(ctx, "GET", "/browsers/"+url.PathEscape(id), nil, &b); err != nil {
		return Browser{}, err
	}
	return b, nil
}

// Delete stops a browser (the Pod is garbage-collected by the operator).
func (c *BrowserMeshClient) Delete(ctx context.Context, id string) error {
	return c.do(ctx, "DELETE", "/browsers/"+url.PathEscape(id), nil, nil)
}

// ViewerToken mints a short-lived token so a browser can open the noVNC
// WebSocket (which cannot send headers). Append it as ?token= to VNCURL.
func (c *BrowserMeshClient) ViewerToken(ctx context.Context, id string) (string, error) {
	var out struct {
		Token string `json:"token"`
	}
	if err := c.do(ctx, "POST", "/browsers/"+url.PathEscape(id)+"/viewer-token", nil, &out); err != nil {
		return "", err
	}
	return out.Token, nil
}

// CDPURL returns the WebSocket URL to drive the browser over CDP. The API key
// is included as ?api_key= so clients that cannot set headers still authenticate.
func (c *BrowserMeshClient) CDPURL(id string) (string, error) {
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

// WatchURL returns the noVNC WebSocket URL to watch the browser live, with a
// fresh short-lived viewer token. The dashboard consumes this.
func (c *BrowserMeshClient) WatchURL(ctx context.Context, id string) (string, error) {
	token, err := c.ViewerToken(ctx, id)
	if err != nil {
		return "", err
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
	u.Path = "/browsers/" + id + "/vnc"
	q := u.Query()
	q.Set("token", token)
	u.RawQuery = q.Encode()
	return u.String(), nil
}
