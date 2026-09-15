# browsermesh-go

Small, dependency-free Go client for the [BrowserMesh](../../) control plane.
Create a browser, drive it over CDP, and let the client clean it up.

## Install

```bash
go get github.com/operolabs/browsermesh-go
```

## Usage

Both the base URL and an API key are required (create a key in the dashboard).

```go
package main

import (
	"context"
	"fmt"
	"log"

	browsermesh "github.com/operolabs/browsermesh-go"
)

func main() {
	client, err := browsermesh.NewBrowserMeshClient("http://127.0.0.1:30080", "bmsk_...")
	if err != nil {
		log.Fatal(err)
	}

	ctx := context.Background()

	// Create -> wait until Running -> run fn -> always delete.
	err = client.WithBrowser(ctx, browsermesh.BrowserMeshOptions{
		Type:           "cloak",
		TimeoutSeconds: 300, // auto-destroy safety net
	}, func(b browsermesh.Browser) error {
		cdp, err := client.CDPURL(b.ID) // ws://.../browsers/<id>/cdp?api_key=...
		if err != nil {
			return err
		}
		watch, err := client.WatchURL(ctx, b.ID) // noVNC ws URL, with a viewer token
		if err != nil {
			return err
		}
		fmt.Println("drive:", cdp)
		fmt.Println("watch:", watch)
		return nil
	})
	if err != nil {
		log.Fatal(err)
	}
}
```

### Low-level methods

```go
b, _ := client.Create(ctx, browsermesh.BrowserMeshOptions{Type: "cloak"})
list, _ := client.List(ctx)
b, _ = client.Get(ctx, b.ID)
b, _ = client.WaitReady(ctx, b.ID)
_ = client.Delete(ctx, b.ID)
token, _ := client.ViewerToken(ctx, b.ID) // for the noVNC WebSocket
```

Errors from non-2xx responses are `*browsermesh.APIError` (with `Status`,
`Kind`, `Detail`, and `IsNotFound`/`IsUnauthorized` helpers).

## Notes

- The API key is sent as `Authorization: Bearer <key>`; the CDP WebSocket URL
  also carries `?api_key=` so header-less clients can authenticate.
- `WatchURL(ctx, id)` mints a short-lived viewer token and returns the noVNC ws
  URL (the dashboard consumes this).
- Browsers auto-expire server-side (default 20 min), so a crashed client never
  leaks one; `WithBrowser` deletes explicitly as well.
