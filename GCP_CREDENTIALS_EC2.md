# Setting Up GCP Credentials on EC2

## The Problem

The bot uses Gemini via Vertex AI, which requires GCP authentication. On EC2, you need to set up Application Default Credentials (ADC).

## Solution: Use a Service Account (Recommended)

### Step 1: Create a Service Account in GCP

1. Go to [GCP Console](https://console.cloud.google.com/)
2. Navigate to **IAM & Admin** → **Service Accounts**
3. Click **Create Service Account**
4. Name: `continuum-ai-bot`
5. Click **Create and Continue**
6. Grant role: **Vertex AI User** (or `roles/aiplatform.user`)
7. Click **Continue** → **Done**

### Step 2: Create and Download Key

1. Click on the service account you just created
2. Go to **Keys** tab
3. Click **Add Key** → **Create new key**
4. Choose **JSON**
5. Download the key file (e.g., `continuum-ai-key.json`)

### Step 3: Upload Key to EC2

```bash
# From your local machine, upload the key
scp -i "C:\Users\Avyukt\Downloads\continuum-kp.pem" \
    continuum-ai-key.json \
    ubuntu@ec2-3-108-63-43.ap-south-1.compute.amazonaws.com:~/continuum.ai/
```

### Step 4: Set Environment Variable on EC2

```bash
# SSH into EC2
ssh -i "C:\Users\Avyukt\Downloads\continuum-kp.pem" \
    ubuntu@ec2-3-108-63-43.ap-south-1.compute.amazonaws.com

# Set the environment variable
export GOOGLE_APPLICATION_CREDENTIALS=/home/ubuntu/continuum.ai/continuum-ai-key.json

# Or add to .env file
echo "GOOGLE_APPLICATION_CREDENTIALS=/home/ubuntu/continuum.ai/continuum-ai-key.json" >> ~/continuum.ai/.env
```

### Step 5: Restart the Bot

```bash
# Stop current bot (Ctrl+C)
# Restart
cd ~/continuum.ai
uvicorn app.slack_bot:app --host 0.0.0.0 --port 3000
```

---

## Alternative: Use gcloud CLI (If you have interactive access)

If you can SSH with X11 forwarding or have a way to do interactive login:

```bash
# Install gcloud CLI on EC2
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Authenticate
gcloud auth application-default login

# Set project
gcloud config set project continuum-ai-482615
```

But this is harder on EC2, so **service account is recommended**.

---

## Verify It Works

After setting up credentials, test:

```bash
# On EC2
python -c "from google.auth import default; creds, project = default(); print('Credentials OK!')"
```

Or test the agent directly:

```python
from app.agent.conversation import ConversationalAgent
import asyncio

agent = ConversationalAgent()
result = asyncio.run(agent.chat("test"))
print(result)
```

---

## For systemd Service

If you're using systemd, add the environment variable to the service file:

```ini
[Service]
Environment="GOOGLE_APPLICATION_CREDENTIALS=/home/ubuntu/continuum.ai/continuum-ai-key.json"
```

---

## Security Note

- **Never commit the service account key to git**
- Add `*.json` to `.gitignore` if not already there
- Restrict service account permissions to minimum needed
- Rotate keys periodically
