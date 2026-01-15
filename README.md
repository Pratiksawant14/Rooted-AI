# ROOTED AI

A context-aware AI chatbot with tree-structured memory.

## Tech Stack
- **Backend**: Python + FastAPI
- **Frontend**: React + Vite + Vanilla CSS
- **Database**: Supabase (PostgreSQL)
- **Vector Search**: ChromaDB
- **LLM**: OpenAI (GPT-4o)

## Setup Instructions

### 1. Backend
Navigate to the `backend` folder:
```bash
cd backend
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

**Configuration**:
Open `backend/.env` and add your `OPENAI_API_KEY`.
Supabase credentials are pre-filled.

**Run**:
Double-click `start_backend.bat` or run:
```powershell
.\start_backend.bat
```
Server runs at `http://localhost:8000`.


### 2. Frontend
Navigate to the `frontend` folder:
```bash
cd frontend
npm install
npm run dev
```
Open browser at `http://localhost:5173`.

## Architecture Highlights
- **Tree Memory**: Memories are classified as STEM (Identity), BRANCH (Habit), or LEAF (Event).
- **RAG**: Retrievals are filtered by the relevant domain tree.
- **Visuals**: Frontend visualizes which memory nodes are "active" during a conversation.
