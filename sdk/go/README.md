# browsermesh-go

Small, dependency-free Go client for BrowserMesh. Two modes:

- **Control plane** (Kubernetes): create a browser, drive it over CDP, let the
  client clean it up.
- **Serverless** (Cloud Run): drive a single on-demand browser at a service URL.

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
	client, err := browsermesh.NewClient("http://127.0.0.1:30080", "bmsk_...")
	if err != nil {
		log.Fatal(err)
	}

	ctx := context.Background()

	// Create -> wait until Running -> run fn -> always delete.
	err = client.WithBrowser(ctx, browsermesh.CreateOptions{
		Type:           "cloak",
		TimeoutSeconds: 300, // auto-destroy safety net
	}, func(b browsermesh.Browser) error {
		cdp, err := client.CDPURL(ctx, b.ID) // ws://.../browsers/<id>/cdp?api_key=...
		if err != nil {
			return err
		}
		fmt.Println("drive this browser over CDP at", cdp)
		return nil
	})
	if err != nil {
		log.Fatal(err)
	}
}
```

### Serverless mode (Cloud Run)

A Cloud Run browser has no control plane: the service URL *is* one on-demand
browser. Use `NewServerlessClient`; the API key is optional (only if the service
requires auth). `WithBrowser` just waits until Chrome answers and calls fn.

```go
client, err := browsermesh.NewServerlessClient("https://browsermesh-browser-xxxx.run.app", "")
if err != nil {
	log.Fatal(err)
}
ctx := context.Background()

	err = client.WithBrowser(ctx, browsermesh.CreateOptions{}, func(b browsermesh.Browser) error {
		vnc, _ := client.VNCURL()          // https://.../watch  (open this to watch)
		cdp, err := client.CDPURL(ctx, "") // wss://.../devtools/browser/<id> (id ignored)
		if err != nil {
			return err
		}
		fmt.Println("watch:", vnc, "drive:", cdp)
		return nil
	})
```

`Create`, `List`, `Get`, `Delete`, and `ViewerToken` return an error in
serverless mode.

### Low-level methods

```go
b, _ := client.Create(ctx, browsermesh.CreateOptions{Type: "cloak"})
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
- Browsers auto-expire server-side (default 20 min), so a crashed client never
  leaks one; `WithBrowser` deletes explicitly as well.
