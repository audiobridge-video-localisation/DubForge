#!/usr/bin/env bash
# Reset and seed the demo so it can be repeated from a clean state.
#
#   scripts/demo.sh reset [--yes]   delete every project, upload, dub and export
#   scripts/demo.sh seed            upload samples/demo-speech.mp4 and wait until it is processed
#   scripts/demo.sh fresh [--yes]   reset, then seed
#
# The stack must be running (docker compose up). Downloaded models and the learned voice speed
# are kept. Set DEMO_ENV_FILE to pass an env file to docker compose, and WEB_PORT / API_PORT if
# you changed them.
set -euo pipefail

cd "$(dirname "$0")/.."
COMPOSE=(docker compose)
[ -n "${DEMO_ENV_FILE:-}" ] && COMPOSE+=(--env-file "$DEMO_ENV_FILE")
API="http://localhost:${API_PORT:-8001}"
WEB="http://localhost:${WEB_PORT:-8080}"
SAMPLE="samples/demo-speech.mp4"

reset() {
  if [ "${1:-}" != "--yes" ]; then
    echo "This deletes ALL projects, uploaded videos, dubbed audio and exports."
    read -r -p "Type 'reset' to continue: " answer
    [ "$answer" = "reset" ] || { echo "Cancelled."; exit 1; }
  fi
  # TRUNCATE ... CASCADE also empties everything that points at a project
  "${COMPOSE[@]}" exec -T postgres sh -c 'psql -q -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "TRUNCATE projects CASCADE"'
  # drop queued work for the rows that are now gone
  "${COMPOSE[@]}" exec -T redis redis-cli DEL dubforge:jobs dubforge:artifacts dubforge:exports >/dev/null
  "${COMPOSE[@]}" exec -T pipeline sh -c \
    "find /app/data -mindepth 1 -maxdepth 1 ! -name .cache ! -name .speech_rate.json -exec rm -rf {} +"
  echo "Reset: all demo data removed."
}

json() { python3 -c "import sys, json; d = json.load(sys.stdin); print($1)"; }

seed() {
  [ -f "$SAMPLE" ] || { echo "Missing $SAMPLE"; exit 1; }
  curl -fsS "$API/health" >/dev/null 2>&1 || curl -fsS "$API/projects" >/dev/null \
    || { echo "The API is not answering at $API. Is the stack running?"; exit 1; }
  local project media_json project_id job_id status
  project=$(curl -fsS -X POST "$API/projects" -H 'Content-Type: application/json' -d '{"name":"Demo"}')
  project_id=$(printf '%s' "$project" | json "d['id']")
  media_json=$(curl -fsS -X POST "$API/projects/$project_id/media" -F "file=@$SAMPLE")
  job_id=$(printf '%s' "$media_json" | json "d['job']['id']")
  echo "Uploaded $SAMPLE. Processing..."
  for _ in $(seq 1 180); do
    status=$(curl -fsS "$API/jobs/$job_id" | json "d['status']")
    case "$status" in
      completed) echo "Ready: $WEB/projects/$project_id"; return 0 ;;
      failed) echo "Processing failed. See: docker compose logs pipeline"; return 1 ;;
    esac
    sleep 3
  done
  echo "Still processing after 9 minutes (the first run downloads models). Open: $WEB/projects/$project_id"
}

case "${1:-}" in
  reset) reset "${2:-}" ;;
  seed) seed ;;
  fresh) reset "${2:-}"; seed ;;
  *) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
