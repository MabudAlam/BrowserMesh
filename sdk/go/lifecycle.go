package browsermesh

import (
	"context"
	"fmt"
	"time"
)

// WaitReady polls the browser until it reports "Running", or the context ends.
func (c *BrowserMeshClient) WaitReady(ctx context.Context, id string) (Browser, error) {
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

// WithBrowser runs fn against a fresh browser and always cleans it up:
//
//	create -> WaitReady -> fn -> Delete
//
// It is the recommended way to use BrowserMesh for a scrape/task.
func (c *BrowserMeshClient) WithBrowser(ctx context.Context, opts BrowserMeshOptions, fn func(Browser) error) error {
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
