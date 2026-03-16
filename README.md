# 🌊 Fluently - Multimodal Speech Coach

Fluently is a hybrid interaction web application that transforms language learning through immersive, real-time voice conversational coaching. It transitions users from a structured onboarding and learning path dashboard into a full-screen, live coaching session powered by Google's Gemini Live API.

## 🚀 Features
*   **Structured Onboarding:** A multi-step setup wizard that tailors the live agent's focus and daily goals.
*   **Learning Path Dashboard:** A beautiful, visual roadmap (Duolingo-style) to track user progress and select upcoming conversation topics.
*   **Immersive Live Sessions:** Real-time, continuous bi-directional voice streaming connecting the user directly with the Gemini Multimodal AI.
*   **Audio Pipeline Integration:** Advanced WebSockets stream user microphone input directly into the backend for seamless, extremely low-latency feedback.

## 🛠 Architecture & Tech Stack
*   **Frontend:** React 19, Vite, TailwindCSS 4, React Router, Lucide React icons.
*   **Backend:** Python 3.11, FastAPI, Python WebSockets.
*   **AI Integrations:** Google Cloud Vertex AI, Google GenAI SDK (Gemini Live API).

---

## ⚙️ Spin-up Instructions

We have designed Fluently to be extremely easy to build, run locally, and deploy. Follow this step-by-step guide to run the codebase on your own machine. Even if you are reviewing this project for a hackathon, these instructions prove the project is completely reproducible.

### Prerequisites
*   [Node.js](https://nodejs.org/) (v18 or higher)
*   [Python](https://python.org/) (3.11 or higher)
*   A Google Cloud account with the **Gemini API** / Vertex AI enabled.

### 💻 Local Development Setup

#### 1. Clone the Repository
```bash
git clone https://github.com/rayirthsaharan/Fluently.git
cd Fluently
```

#### 2. Backend Setup (FastAPI + WebSockets)
The backend manages the secure WebSocket connections and audio bridging to Google's Gemini services.

Open your terminal and run:
```bash
# Navigate to the backend directory
cd backend

# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install all Python dependencies
pip install -r requirements.txt

# Set up your environment variables
# Note: Add your exact Gemini API key below
echo "GEMINI_API_KEY=your_gemini_api_key_here" > .env

# Run the backend FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
*Your backend is now running at `http://localhost:8000`.*

#### 3. Frontend Setup (React + Vite)
The front end handles our gorgeous interactive UI and the raw microphone byte-streams.

Open a **new** terminal window/tab from the project root:
```bash
# Navigate to the frontend directory
cd frontend

# Install all Node.js dependencies
npm install

# Start the Vite development server
npm run dev
```
*Your frontend is now available at `http://localhost:5173`. Open this in your browser!*

---

### ☁️ Cloud Deployment Setup (Docker)

Both the frontend and backend include optimized [Dockerfile](cci:7://file:///Users/rayirthsaharan/Desktop/fluently-app/backend/Dockerfile:0:0-0:0)s, making them 1-click deployable to any container registry (like **Google Cloud Run** or AWS ECS).

#### Deploying the Backend
```bash
cd backend
gcloud run deploy fluently-backend \
  --source . \
  --set-env-vars GEMINI_API_KEY="your_gemini_api_key_here" \
  --allow-unauthenticated
```

#### Deploying the Frontend
*(Note: Be sure your frontend API URLs point to the newly deployed backend instead of localhost before building).*
```bash
cd frontend
gcloud run deploy fluently-frontend \
  --source . \
  --port 8080 \
  --allow-unauthenticated
```

---

## 💡 What's Next for Fluently
We have big plans for the future of Fluently:
1.  **More language modes:** Expand coaching from primarily English/Spanish to over 20+ low-resource languages.
2.  **Persistent Transcripts:** Save conversations to a secure database to review mistakes over time.
3.  **Video Integration:** Capture facial expressions and emotion during conversation to provide public speaking metrics.

---
*Built with ❤️ for the future of interactive education.*
