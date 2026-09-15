package browsermesh

// Browser is a single browser and its current, operator-reported status.
type Browser struct {
	ID        string `json:"browser_id"`
	Name      string `json:"name"`
	Status    string `json:"status"` // Pending | Running | Failed | Expired
	PodIP     string `json:"pod_ip"`
	CDPURL    string `json:"cdp_url"` // path, e.g. /browsers/<id>/cdp
	VNCURL    string `json:"vnc_url"` // path, e.g. /browsers/<id>/vnc
	ExpiresAt string `json:"expires_at"`
}

// BrowserMeshOptions configures a new browser.
type BrowserMeshOptions struct {
	Type           string // engine/provider, e.g. "cloak"
	TimeoutSeconds int    // auto-destroy after N seconds; 0 = server default (20 min)
}

// BrowserList is the response of List.
type BrowserList struct {
	Browsers []Browser `json:"browsers"`
}
