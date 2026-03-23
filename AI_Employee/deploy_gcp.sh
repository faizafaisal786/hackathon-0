#!/bin/bash
# ============================================================
#  Deploy AI Employee to Google Cloud Run (FREE tier)
#  Platinum Tier — 24/7 Email Triage
# ============================================================
#
#  Prerequisites:
#    1. Install Google Cloud SDK: https://cloud.google.com/sdk/docs/install
#    2. Run: gcloud auth login
#    3. Create a GCP project (free): https://console.cloud.google.com
#    4. Set your project ID below
#
#  Free tier limits (more than enough):
#    Cloud Run Jobs : 2M task attempts/month free
#    Cloud Scheduler: 3 jobs free
#    Artifact Registry: 0.5 GB free
#
#  Usage:
#    chmod +x deploy_gcp.sh
#    ./deploy_gcp.sh
# ============================================================

set -e

# ── CONFIG — Edit these ────────────────────────────────────
PROJECT_ID="ai-employee-hackathon"      # Your GCP project ID
REGION="us-central1"                    # Free tier region
JOB_NAME="ai-employee-cloud"
IMAGE="gcr.io/$PROJECT_ID/$JOB_NAME"
SCHEDULE="*/5 * * * *"                  # Every 5 minutes

# GitHub
GIT_TOKEN="${GIT_TOKEN:-}"              # Your GitHub PAT token
GIT_REPO="https://github.com/faizafaisal786/hackathon-0.git"

# AI Backend
GROQ_API_KEY="${GROQ_API_KEY:-}"

# Gmail credentials (base64 encoded)
# To encode: base64 -w 0 credentials.json
GMAIL_CREDENTIALS_B64="${GMAIL_CREDENTIALS_B64:-}"
GMAIL_TOKEN_B64="${GMAIL_TOKEN_B64:-}"

echo "============================================================"
echo "  AI Employee — Google Cloud Run Deployment"
echo "  Project : $PROJECT_ID"
echo "  Region  : $REGION"
echo "  Job     : $JOB_NAME"
echo "  Schedule: $SCHEDULE (every 5 min)"
echo "============================================================"

# ── STEP 1: Enable required APIs ─────────────────────────
echo ""
echo "[1/6] Enabling GCP APIs..."
gcloud config set project "$PROJECT_ID"
gcloud services enable \
    run.googleapis.com \
    cloudscheduler.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com \
    --project "$PROJECT_ID"
echo "  APIs enabled OK"

# ── STEP 2: Create Artifact Registry ─────────────────────
echo ""
echo "[2/6] Creating Artifact Registry..."
gcloud artifacts repositories create ai-employee \
    --repository-format=docker \
    --location="$REGION" \
    --project "$PROJECT_ID" \
    2>/dev/null || echo "  Registry already exists"
echo "  Registry OK"

# ── STEP 3: Build and push Docker image ──────────────────
echo ""
echo "[3/6] Building Docker image..."
IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/ai-employee/$JOB_NAME"

gcloud auth configure-docker "$REGION-docker.pkg.dev" --quiet

docker build -f Dockerfile.cloudrun -t "$IMAGE:latest" .
docker push "$IMAGE:latest"
echo "  Image pushed: $IMAGE:latest"

# ── STEP 4: Create Cloud Run Job ─────────────────────────
echo ""
echo "[4/6] Creating Cloud Run Job..."
gcloud run jobs create "$JOB_NAME" \
    --image "$IMAGE:latest" \
    --region "$REGION" \
    --task-timeout 600 \
    --max-retries 1 \
    --set-env-vars "GROQ_API_KEY=$GROQ_API_KEY" \
    --set-env-vars "GIT_TOKEN=$GIT_TOKEN" \
    --set-env-vars "GIT_REPO=$GIT_REPO" \
    --set-env-vars "GMAIL_CREDENTIALS_B64=$GMAIL_CREDENTIALS_B64" \
    --set-env-vars "GMAIL_TOKEN_B64=$GMAIL_TOKEN_B64" \
    --set-env-vars "DRY_RUN=false" \
    --set-env-vars "PYTHONUNBUFFERED=1" \
    --project "$PROJECT_ID" \
    2>/dev/null || \
gcloud run jobs update "$JOB_NAME" \
    --image "$IMAGE:latest" \
    --region "$REGION" \
    --task-timeout 600 \
    --set-env-vars "GROQ_API_KEY=$GROQ_API_KEY" \
    --set-env-vars "GIT_TOKEN=$GIT_TOKEN" \
    --set-env-vars "GIT_REPO=$GIT_REPO" \
    --set-env-vars "GMAIL_CREDENTIALS_B64=$GMAIL_CREDENTIALS_B64" \
    --set-env-vars "GMAIL_TOKEN_B64=$GMAIL_TOKEN_B64" \
    --project "$PROJECT_ID"
echo "  Cloud Run Job created OK"

# ── STEP 5: Create Cloud Scheduler ───────────────────────
echo ""
echo "[5/6] Setting up Cloud Scheduler (every 5 min)..."

SA_EMAIL="$(gcloud iam service-accounts list \
    --filter="displayName:Default compute" \
    --format='value(email)' \
    --project "$PROJECT_ID")"

gcloud scheduler jobs create http "${JOB_NAME}-trigger" \
    --location "$REGION" \
    --schedule "$SCHEDULE" \
    --uri "https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT_ID/jobs/$JOB_NAME:run" \
    --oauth-service-account-email "$SA_EMAIL" \
    --project "$PROJECT_ID" \
    2>/dev/null || \
gcloud scheduler jobs update http "${JOB_NAME}-trigger" \
    --location "$REGION" \
    --schedule "$SCHEDULE" \
    --project "$PROJECT_ID"
echo "  Scheduler created OK"

# ── STEP 6: Test run ─────────────────────────────────────
echo ""
echo "[6/6] Running first test pass..."
gcloud run jobs execute "$JOB_NAME" \
    --region "$REGION" \
    --project "$PROJECT_ID" \
    --wait
echo "  Test run complete!"

echo ""
echo "============================================================"
echo "  DEPLOYMENT COMPLETE!"
echo ""
echo "  Cloud Run Job runs every 5 minutes automatically."
echo "  Monitor at: https://console.cloud.google.com/run/jobs"
echo ""
echo "  Platinum Demo Flow:"
echo "  1. Email arrives -> Cloud fetches -> drafts reply"
echo "  2. Cloud pushes to GitHub (hackathon-0)"
echo "  3. Local: git pull -> see Pending_Approval/cloud/"
echo "  4. Human approves -> Local sends via email MCP"
echo "  5. Done/ updated -> Git push back"
echo "============================================================"
