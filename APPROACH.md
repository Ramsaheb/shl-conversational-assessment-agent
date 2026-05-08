# Approach Document: SHL Assessment Recommender Agent

## 1. Architecture & Design Choices
The project is built as a **stateless FastAPI microservice**. Instead of using heavy, opinionated agent frameworks (like LangChain or LangGraph) that often suffer from non-deterministic routing loops, high latency, and difficult debugging, I implemented a **deterministic intent orchestration layer** in pure Python.

**Key Design Decisions:**
*   **Stateless by Design:** As requested, the `/chat` endpoint accepts the full conversation history with every request. State extraction happens per-request.
*   **Deterministic Intent Routing:** The agent analyzes the user's input and classifies it into one of six intents (`refusal`, `comparison`, `refinement`, `recommendation`, `greeting`, `clarification`) using deterministic rules and keyword matching. This ensures the system behaves predictably, avoids hallucinated tool calls, and strictly enforces the conversation cap without relying on the LLM's whims.
*   **Safety First (Refusals):** A dedicated refusal service runs *before* any LLM generation. It uses a combination of regex (for prompt injection like "ignore previous instructions") and contextual keyword checking to block out-of-scope topics (legal, salary, competitors) while smartly allowing SHL-relevant queries (e.g., permitting AWS when discussing cloud engineer roles).
*   **Turn-Cap Enforcement:** To guarantee the agent doesn't get trapped in an endless cycle of clarifying questions, a hard limit forces the agent to make a best-effort recommendation if the conversation approaches the 8-turn limit.

## 2. Retrieval Strategy
Retrieval relies on a **Hybrid Search Approach** backed by **ChromaDB**:
*   **Embedding Model:** `sentence-transformers/all-MiniLM-L6-v2` runs locally, offering an excellent balance of speed and semantic representation for short-to-medium text.
*   **No Hard Metadata Filtering:** I discovered that hard-filtering by assessment type (e.g., only returning "Skills & Simulations" when a user asks for "developer assessments") drastically harmed Recall@10, as it excluded perfectly valid cognitive and personality tests for that role. 
*   **Ranking with Metadata Boost:** Instead, the retrieval pulls a broad semantic set (top 30), and then a custom ranking algorithm applies keyword overlap (Jaccard similarity) and metadata bonuses based on the extracted assessment type preferences. This significantly improves recall.

## 3. Prompt Design & Grounding
*   **Post-Retrieval Generation:** The LLM (Groq: `llama-3.1-8b-instant`) is never asked to generate URLs or assessment names from its own weights. It is provided a strict set of retrieved, verified assessments and asked only to explain *why* they fit the role.
*   **Output Sanitization:** Even with strict prompts, LLMs can occasionally hallucinate URLs in the conversational reply text. A post-generation sanitization step strips any URLs from the natural language reply, ensuring the user only uses the structured, validated `recommendations` array.
*   **Strict Validation:** The structured `recommendations` are passed through a validation function that cross-references them against the scraped catalog, enforcing the 1-10 item constraint and ensuring exact URL matches.

## 4. Evaluation Approach & Iteration
*   **What Didn't Work:** Initially, my catalog only contained ~22 hand-curated items. This completely destroyed Recall@10 because the evaluation traces expect specific tests from the full catalog (like "Java 8 (New)"). I also found that matching "job description" in the refusal logic blocked legitimate requests. 
*   **Improvement Measurement:** By writing a comprehensive testing script (`scripts/run_comprehensive_qa.py`), I was able to simulate edge cases (vague queries, refinement, competitor mentions, JDs) and measure latency, schema compliance, and behavioral pass-rates locally.
*   **Catalog Expansion:** I wrote a dedicated scraper (`scripts/scrape_full_catalog.py`) to traverse the actual SHL product catalog pagination, extracting all 377 individual test solutions along with their exact single-letter test type codes (A, B, C, K, P, S). This drastically improved recall against the test traces.

## 5. AI Tools Used
I utilized **AI-assisted development tools (Gemini / Antigravity)** to accelerate the build process. Specifically:
1.  **Refactoring and Scaffolding:** Rapidly scaffolding the FastAPI endpoints and Pydantic models.
2.  **Scraper Creation:** Writing the robust BeautifulSoup pagination logic to ingest the full SHL catalog.
3.  **Code Review:** Identifying the blocking synchronous LLM calls in the async request handlers, which I then wrapped in `asyncio.to_thread` to prevent event-loop blocking under load.
