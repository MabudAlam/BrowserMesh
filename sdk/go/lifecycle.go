package browsermesh

import (
	"context"
	"fmt"
	"time"
)

// WaitReady waits until the browser is ready.
//
// Control plane: polls the Browser resource until it reports "Running".
// Serverless: polls /json/version until Chrome's CDP answers.
func (c *Client) WaitReady(ctx context.Context, id string) (Browser, error) {
	if c.serverless {
		return c.waitReadyServerless(ctx)
	}
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()
	for {
		b, err := c.Get(ctx, id)
		if err != nil {
			return Browser{}, err
		}
		switch b.Status {
		case "Running":
			return b, nil
		case "Failed", "Expired":
			return Browser{}, fmt.Errorf("browsermesh: browser %s is %s", id, b.Status)
		}
		select {
		case <-ctx.Done():
			return Browser{}, ctx.Err()
		case <-ticker.C:
		}
	}
}

func (c *Client) waitReadyServerless(ctx context.Context) (Browser, error) {
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()
	for {
		cdp, err := c.resolveCDP(ctx)
		if err == nil {
			return Browser{Status: "Running", CDPURL: cdp, VNCURL: c.baseURL + "/watch"}, nil
		}
		select {
		case <-ctx.Done():
			return Browser{}, ctx.Err()
		case <-ticker.C:
		}
	}
}

// WithBrowser runs fn against a browser.
//
// Control plane: create -> WaitReady -> fn -> Delete (always cleans up).
// Serverless: WaitReady -> fn (nothing to create or delete; Cloud Run scales
// the instance down when the connection ends).
func (c *Client) WithBrowser(ctx context.Context, opts CreateOptions, fn func(Browser) error) error {
	if c.serverless {
		b, err := c.WaitReady(ctx, "")
		if err != nil {
			return err
		}
		return fn(b)
	}
	created, err := c.Create(ctx, opts)
	if err != nil {
		return err
	}
	defer func() {
		// Best-effort cleanup; the browser also auto-expires server-side.
		_ = c.Delete(context.WithoutCancel(ctx), created.ID)
	}()

	b, err := c.WaitReady(ctx, created.ID)
	if err != nil {
		return err
	}
	return fn(b)
}
