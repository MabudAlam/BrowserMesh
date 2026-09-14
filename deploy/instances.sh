#!/usr/bin/env bash
# Live Cloud Run container instance count, filtered to the latest revision.
#
# The Cloud Run console's Metrics tab has no revision filter, so it sums every
# revision ever deployed (e.g. "15" = 5 instances x 3 revisions). This shows the
# real current number for the revision that is actually serving traffic.
#
#   ./deploy/instances.sh [SERVICE] [REGION] [PROJECT]
#
# Defaults: browsermesh-browser, us-central1, current gcloud project.
set -euo pipefail

SERVICE=${1:-browsermesh-browser}
REGION=${2:-us-central1}
PROJECT=${3:-$(gcloud config get-value project 2>/dev/null)}

REV=$(gcloud run services describe "$SERVICE" --region "$REGION" --project "$PROJECT" \
  --format='value(status.latestReadyRevisionName)')
TOKEN=$(gcloud auth print-access-token)
START=$(date -u -v-5M +%Y-%m-%dT%H:%M:%SZ)
END=$(date -u +%Y-%m-%dT%H:%M:%SZ)

echo "service=$SERVICE  region=$REGION  revision=$REV"

curl -s -G "https://monitoring.googleapis.com/v3/projects/$PROJECT/timeSeries" \
  --data-urlencode "filter=metric.type=\"run.googleapis.com/container/instance_count\" AND resource.labels.service_name=\"$SERVICE\" AND resource.labels.revision_name=\"$REV\"" \
  --data-urlencode "interval.startTime=$START" \
  --data-urlencode "interval.endTime=$END" \
  --data-urlencode "aggregation.alignmentPeriod=60s" \
  --data-urlencode "aggregation.perSeriesAligner=ALIGN_MAX" \
  -H "Authorization: Bearer $TOKEN" \
| python3 -c '
import json, sys
d = json.load(sys.stdin)
ts = d.get("timeSeries", [])
if not ts:
    print("  no data yet (the metric samples ~every 60s)")
    raise SystemExit
for s in ts:
    state = s["metric"]["labels"].get("state", "?")
    v = s["points"][0]["value"]
    print("  %-6s = %s" % (state, v.get("int64Value") or v.get("doubleValue")))
'
