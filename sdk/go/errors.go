package browsermesh

import (
	"encoding/json"
	"fmt"
	"net/http"
)

// APIError is a non-2xx response from the control plane.
type APIError struct {
	Status int    // HTTP status code
	Kind   string // machine-readable kind, e.g. "http_error"
	Detail string // human-readable message
}

func (e *APIError) Error() string {
	return fmt.Sprintf("browsermesh: %d %s: %s", e.Status, e.Kind, e.Detail)
}

// IsNotFound reports whether the error is a 404.
func (e *APIError) IsNotFound() bool { return e.Status == http.StatusNotFound }

// IsUnauthorized reports whether the error is a 401.
func (e *APIError) IsUnauthorized() bool { return e.Status == http.StatusUnauthorized }

// parseError reads the control plane's {"error","detail"} body into an APIError.
func parseError(res *http.Response) error {
	var body struct {
		Error  string `json:"error"`
		Detail string `json:"detail"`
	}
	_ = json.NewDecoder(res.Body).Decode(&body)
	return &APIError{Status: res.StatusCode, Kind: body.Error, Detail: body.Detail}
}
