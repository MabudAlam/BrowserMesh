# Deploying BrowserMesh (production, cheap)

BrowserMesh runs **headed browsers** (KasmVNC + Chrome in a container), so it
needs real Linux containers with a persistent process — not functions. Any
Kubernetes works; the Pod is the unit. The cost levers are the same everywhere:

1. **Spot / preemptible nodes** for the browser Pods (the operator self-heals if
   one is reclaimed).
2. **Scale to zero** when idle — browsers auto-expire (default 20 min), and the
   operator runs no browser Pods when none are declared.
3. **Right-size memory** (each browser is ~1–2 GiB) and **pack** browsers per node.
4. **Watch egress** — for scrapers, network egress often costs more than compute.

> Architecture is unchanged from local: `crds/` + `operator/` + `control/` +
> `infra/browser/`. Only the image registry, ingress, and node pools change.

## Guides

- **[gke.md](./gke.md)** — GKE **zonal Standard** (free-tier control plane) with a
  **spot** browser node pool that scales to zero.
- **[k3s.md](./k3s.md)** — cheapest overall: k3s on a single small x86 VPS.

## Host comparison

| Option | Rough cost | Ops | Notes |
|---|---|---|---|
| **Hetzner Cloud + k3s** | ~€5–15/mo per VM | medium | Cheapest real option; one VM runs control+operator, add VMs for browsers. |
| **Oracle Cloud Always Free (ARM)** | **$0** | medium | 4 ARM cores / 24 GB free; needs an ARM build of the browser image. |
| **GKE Standard + spot pool** | low | low | Free zonal control plane; spot VMs ~60–80% off; scales to zero. |
| **DigitalOcean DOKS** | from $12/mo/node | low | Simple managed k8s; add a spot-ish pool. |

**Recommendation:** for "cheap but managed", **GKE with a spot browser node pool
+ autoscaler**; for "cheapest overall", **Hetzner (or Oracle free) + k3s**.

## Browser Pod placement

Pin browser Pods to a specific (e.g. spot) node pool with the operator's env
vars — see `gke.md` step 4:

```yaml
env:
- name: BROWSER_NODE_SELECTOR
  value: '{"cloud.google.com/gke-nodepool":"browsers"}'
- name: BROWSER_TOLERATIONS
  value: '[{"key":"browsers","operator":"Equal","value":"true","effect":"NoSchedule"}]'
```

The cluster autoscaler adds a spot node when browsers are `Pending` and removes
it when idle → you pay only while browsers run.

## Cost checklist

- [ ] Browser Pods run on **spot/preemptible** nodes (operator self-heals kills).
- [ ] **Scale to zero**: no browser Pods when idle (auto-expiry + autoscaler to 0).
- [ ] Right-size memory; pack ~6–7 browsers per 16 GB node.
- [ ] Use **Cloudflare Tunnel** instead of a cloud LoadBalancer.
- [ ] Dashboard on **Vercel/Cloudflare Pages** (free tier).
- [ ] Set budgets/alerts; monitor **egress** (scraping traffic).
- [ ] Rotate `browsermesh-auth/session-secret`; never commit real secrets.
