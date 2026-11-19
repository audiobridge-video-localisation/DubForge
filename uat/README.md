# UAT walkthrough recorder

Records the UAT flows against a running DubForge: a screenshot per step (the element to use
ringed in red, with a numbered caption), a picture of the result, a video per flow, and a
visual guide (`output/index.html`) that testers follow and mark Pass / Fail / Blocked.

The steps, expected results and cautions live in `flows.mjs`. Change them there and re-record.

## Run it

Use a throwaway stack with mock providers; the flows create, export and delete a project.

```sh
# 1. start an isolated stack on :8090 (separate images and data from the normal stack)
cat > /tmp/uat.env <<'EOF'
STT_PROVIDER=mock
TRANSLATION_PROVIDER=mock
TTS_PROVIDER=mock
WEB_PORT=8090
API_PORT=8011
EOF
cat > /tmp/compose.uat.yml <<'EOF'
services:
  migrate: { image: dubforge-uat-api:local }
  api: { image: dubforge-uat-api:local }
  pipeline: { image: dubforge-uat-pipeline:local }
  web: { image: dubforge-uat-web:local }
EOF
docker compose -p dubforge-uat --env-file /tmp/uat.env \
  -f docker-compose.yml -f /tmp/compose.uat.yml up -d --build

# 2. record and build the guide
cd uat
npm install && npx playwright install chromium   # first time only
UAT_BASE_URL=http://localhost:8090 npm run record
node build-guide.mjs                             # writes output/index.html

# 3. stop the stack when done (-v also drops its data)
docker compose -p dubforge-uat down -v
```

The separate image names matter: the default compose file tags images `dubforge-*:local`, and
building those would replace the images a normal local stack runs on.

`UAT_HOLD_MS` sets how long each highlight stays on screen in the videos (default 1400).
