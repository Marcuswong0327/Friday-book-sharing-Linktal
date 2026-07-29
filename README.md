# Atomic Habits Coach

AI-powered habit planner for Friday book sharing on *Atomic Habits* by James Clear.

Scan a QR → answer 3 quick questions → get a 4-law action plan → download a one-page PDF.

## Stack

- Streamlit UI (Linktal-inspired purple dashboard)
- OpenAI `gpt-4o-mini`
- `fpdf2` PDF export
- Deploy on Google Cloud Run

## Local setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # then set OPENAI_API_KEY
streamlit run app.py
```

Open http://localhost:8501

Optional Streamlit secrets: create `.streamlit/secrets.toml` with:

```toml
OPENAI_API_KEY = "sk-..."
OPENAI_API_KEY_FALLBACK = "sk-..."  # used if primary fails
```

Keys starting with `sk-or-` automatically use OpenRouter (`openai/gpt-4o-mini`). If the primary key errors (quota, auth, etc.), the app retries with `OPENAI_API_KEY_FALLBACK`.

## Cloud Run deploy

Prerequisites: `gcloud` CLI, project with Cloud Run + Artifact Registry (or Container Registry) enabled.

```bash
# Set your project
gcloud config set project YOUR_PROJECT_ID

# Build and deploy (example with Cloud Build + Cloud Run)
gcloud run deploy atomic-habits-coach \
  --source . \
  --region asia-southeast1 \
  --allow-unauthenticated \
  --set-env-vars OPENAI_API_KEY=sk-your-key-here \
  --max-instances 2 \
  --min-instances 0 \
  --memory 512Mi
```

Prefer secrets over plain env vars:

```bash
echo -n "sk-your-key" | gcloud secrets create openai-api-key --data-file=-

gcloud run deploy atomic-habits-coach \
  --source . \
  --region asia-southeast1 \
  --allow-unauthenticated \
  --set-secrets OPENAI_API_KEY=openai-api-key:latest \
  --max-instances 2 \
  --memory 512Mi
```

After deploy, copy the HTTPS service URL into your presentation QR code.

### Manual Docker

```bash
docker build -t atomic-habits-coach .
docker run -p 8080:8080 -e OPENAI_API_KEY=sk-... atomic-habits-coach
```

## App flow

1. **Goal** — habit to build or break  
2. **Anchor** — daily routine for habit stacking  
3. **Obstacle** — what usually stops them  

AI returns Cue / Craving / Response / Reward tips, a 2-minute version, habit stack, and one environment tip. PDF adds a static cheat sheet (habit loop, plateau, Clear quote).

## Notes

- No login — shared QR link for ~20 internal attendees  
- Book concepts live in the system prompt only (no full-book upload)  
- Linktal logo is optional and not required
