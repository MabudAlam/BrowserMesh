#!/usr/bin/env bash
# Live Cloud Run stats from the CLI, refreshed every 30s. Ctrl-C to stop.
#
#   ./stats.sh [SERVICE] [REGION] [PROJECT]
#
# Defaults: browsermesh-browser, us-central1, current gcloud project.
# Shows the container instance count for the latest revision (the Cloud Run
# console has no revision filter, so it sums every revision) plus a 5-minute
# request breakdown.
set -uo pipefail

SERVICE=${1:-browsermesh-browser}
REGION=${2:-us-central1}
PROJECT=${3:-$(gcloud config get-value project 2>/dev/null)}
INTERVAL=30

if [ -z "${PROJECT:-}" ] || [ "$PROJECT" = "(unset)" ]; then
  echo "stats: no GCP project (pass one or run: gcloud config set project PROJECT)" >&2
  exit 1
fi

# query <metric-type> <extra-filter> <aligner> <period>  -> JSON on stdout
query() {
  local metric=$1 extra=$2 aligner=$3 period=$4
  curl -s -G "https://monitoring.googleapis.com/v3/projects/$PROJECT/timeSeries" \
    --data-urlencode "filter=metric.type=\"$metric\" AND resource.labels.service_name=\"$SERVICE\"$extra" \
    --data-urlencode "interval.startTime=$(date -u -v-5M +%Y-%m-%dT%H:%M:%SZ)" \
    --data-urlencode "interval.endTime=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --data-urlencode "aggregation.alignmentPeriod=$period" \
    --data-urlencode "aggregation.perSeriesAligner=$aligner" \
    -H "Authorization: Bearer $(gcloud auth print-access-token 2>/dev/null)"
}

while true; do
  REV=$(gcloud run services describe "$SERVICE" --region "$REGION" --project "$PROJECT" \
    --format='value(status.latestReadyRevisionName)' 2>/dev/null || true)

  clear
  printf '\033[1mBrowserMesh Cloud Run stats\033[0m  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')"
  printf 'service=%s  region=%s  revision=%s\n\n' "$SERVICE" "$REGION" "${REV:-<none>}"

  printf 'instances (live, latest revision):\n'
  if [ -n "${REV:-}" ]; then
    query "run.googleapis.com/container/instance_count" \
      " AND resource.labels.revision_name=\"$REV\"" "ALIGN_MAX" "60s" \
    | python3 -c '
import json, sys
d = json.load(sys.stdin)
ts = d.get("timeSeries", [])
if not ts:
    print("  no data yet (samples ~every 60s)")
for s in ts:
    state = s["metric"]["labels"].get("state", "?")
    v = s["points"][0]["value"]
    print("  %-6s = %s" % (state, v.get("int64Value") or v.get("doubleValue")))
' 2>/dev/null || echo "  (unavailable)"
  fi

  printf '\nrequests (last 5m):\n'
  query "run.googleapis.com/request_count" "" "ALIGN_SUM" "300s" \
  | python3 -c '
import json, sys
d = json.load(sys.stdin)
ts = d.get("timeSeries", [])
rows = []
for s in ts:
    code = s["metric"]["labels"].get("response_code", "?")
    total = sum(int(p["value"].get("int64Value") or p["value"].get("doubleValue") or 0) for p in s["points"])
    rows.append((code, total))
for code, total in sorted(rows):
    print("  %-4s = %s" % (code, total))
if not rows:
    print("  (none)")
' 2>/dev/null || echo "  (unavailable)"

  printf '\nrefreshing every %ss — Ctrl-C to stop\n' "$INTERVAL"
  sleep "$INTERVAL"
done
