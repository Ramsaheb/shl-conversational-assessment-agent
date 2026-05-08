# SHL Conversational Assessment Recommendation Agent

A production-quality, stateless conversational AI agent that helps recruiters select SHL assessments. Built with FastAPI, ChromaDB, Sentence Transformers, and Groq API.

## Architecture

```
User Messages → POST /chat
    ↓
Conversation State Extractor (deterministic parsing)
    ↓
Intent Analyzer (keyword patterns + state completeness)
    ↓
Decision Layer (Python if/else — no LLM)
    ├── Refusal     → polite refusal, recommendations=[]
    ├── Clarification → ask questions, recommendations=[]
    ├── Comparison  → grounded catalog comparison, recommendations=[]
    └── Recommendation → retrieve → rank → LLM summary → recommendations=[1-10]
    ↓
Strict Response Formatter (Pydantic + catalog validation)
    ↓
FastAPI JSON Response
```

### Key Design Decisions

- **Deterministic intent detection**: Python pattern matching decides the flow. LLM only generates natural language.
- **Hybrid retrieval**: Semantic (ChromaDB) + keyword (Jaccard) + metadata filtering.
- **Catalog grounding**: Every recommendation validated against `catalog.json` — zero hallucination.
- **Stateless**: Full conversation history sent every request. State reconstructed each time.
- **No frameworks**: Pure FastAPI + Python. No LangChain/LangGraph/CrewAI.

## Quick Start

### Prerequisites

- Python 3.11+
- Groq API key ([get one here](https://console.groq.com))

### Local Setup

```bash
# Clone the repository
git clone <repo-url>
cd shl-conversational-assessment-agent

# Create virtual environment
python -m venv venv
venv\Scripts\activate    # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your GROQ_API_KEY

# Ingest catalog into ChromaDB
python -m scripts.ingest_catalog

# Start the server
uvicorn app.main:app --reload --port 8000
```

Open **http://localhost:8000/docs** for Swagger UI.

### Docker Setup

```bash
docker build -t shl-agent .
docker run -p 8000:8000 -e GROQ_API_KEY=your_key_here shl-agent
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | (required) | Groq API key |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | Groq model name |
| `CHROMA_PERSIST_DIR` | `./chroma_db` | ChromaDB storage path |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model |
| `PORT` | `8000` | Server port |
| `LOG_LEVEL` | `INFO` | Logging level |

## API Endpoints

### GET /health

```bash
curl http://localhost:8000/health
```

Response:
```json
{"status": "ok"}
```

### POST /chat

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "I need assessments for a senior Java developer"}
    ]
  }'
```

Response:
```json
{
  "reply": "For a senior Java developer role, I recommend the following assessments...",
  "recommendations": [
    {
      "name": "SHL Coding Simulations",
      "url": "https://www.shl.com/products/assessments/skills-and-simulations/coding-simulations/",
      "test_type": "Skills & Simulations"
    },
    {
      "name": "SHL Verify G+ (General Ability)",
      "url": "https://www.shl.com/products/assessments/cognitive-assessments/",
      "test_type": "Cognitive"
    }
  ],
  "end_of_conversation": false
}
```

### Conversation Examples

**Vague query → Clarification:**
```json
{"messages": [{"role": "user", "content": "I need an assessment"}]}
// Returns: clarifying questions, recommendations=[]
```

**Comparison:**
```json
{"messages": [{"role": "user", "content": "Compare OPQ and Verify G+"}]}
// Returns: grounded comparison, recommendations=[]
```

**Refinement:**
```json
{"messages": [
  {"role": "user", "content": "Assessments for a developer"},
  {"role": "assistant", "content": "Here are coding assessments..."},
  {"role": "user", "content": "Also add personality assessments"}
]}
// Returns: updated recommendations including personality
```

## Testing

```bash
pytest tests/ -v
```

## Deployment (Render)

1. Push to GitHub
2. Create a new Web Service on [Render](https://render.com)
3. Set build command: `pip install -r requirements.txt && python -m scripts.ingest_catalog`
4. Set start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add environment variable: `GROQ_API_KEY`

## Project Structure

```
├── app/
│   ├── main.py                 # FastAPI app + health endpoint
│   ├── config.py               # Environment configuration
│   ├── routes/chat.py          # POST /chat endpoint
│   ├── models/                 # Pydantic request/response models
│   ├── services/               # Business logic services
│   │   ├── conversation_service.py  # Main orchestrator
│   │   ├── recommendation_service.py
│   │   ├── comparison_service.py
│   │   ├── refusal_service.py
│   │   └── groq_service.py
│   ├── retrieval/              # Vector DB + hybrid search
│   │   ├── chroma_client.py
│   │   ├── embedding_service.py
│   │   ├── retriever.py
│   │   └── ranking.py
│   ├── prompts/                # LLM prompt templates
│   ├── utils/                  # Helpers (logging, parsing, validation)
│   └── data/catalog.json       # SHL assessment catalog
├── scripts/                    # Ingestion + scraping utilities
├── tests/                      # Pytest test suite
├── Dockerfile
├── requirements.txt
└── .env.example
```

## License

MIT
