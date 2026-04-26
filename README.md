# GraphRAG Trinity Router

A production-grade **Graph-Augmented Generation (GraphRAG)** system that answers complex, multi-hop questions by combining a Neo4j knowledge graph with Google Gemini. A trinity of tools — SQL (mock), vector search (mock), and graph traversal (live) — is exposed to a Gemini LLM, which autonomously routes each query to the right engine and synthesizes the final answer.

---

## How It Works

```
User Query
    │
    ▼
┌─────────────────────────────────┐
│  Trinity Router (Gemini 2.5)    │  ← decides which engine(s) to use
└────────┬────────┬───────────────┘
         │        │        │
         ▼        ▼        ▼
  Financials  Documents  Knowledge Graph
  (mock SQL)  (mock FAISS)  (Neo4j + Gemini Embeddings)
         │        │        │
         └────────┴────────┘
                  │
                  ▼
         Synthesized Answer
```

### 1. Config (`config.py`)
Loads secrets from `.env`, opens the Neo4j Bolt connection, and initialises the Gemini embedding client (`gemini-embedding-001`, 3072 dimensions). Everything downstream imports from here.

### 2. Tools (`tools.py`)
Three LangChain `@tool`-decorated functions that the LLM can invoke:

| Tool | Description |
|---|---|
| `query_financials` | Stub for an SQL engine — returns mock market-cap data |
| `search_documents` | Stub for a FAISS vector store — returns mock report excerpts |
| `traverse_knowledge_graph` | **Live.** Embeds the query, runs a two-hop pruned vector search in Neo4j, and serializes the resulting graph paths as text for the LLM |

#### GraphRAG Cypher query (inside `traverse_knowledge_graph`)
```cypher
CALL db.index.vector.queryNodes('alphafund_embeddings', 1, $vector)
YIELD node AS entry_node

MATCH path = (entry_node)-[*1..2]-(neighbor)
WHERE COUNT { (neighbor)--() } < 100          -- prune hub nodes

WITH path, vector.similarity.cosine(neighbor.embedding, $vector) AS relevance
WHERE relevance > 0.55

RETURN
    [n IN nodes(path) | n.id] AS Node_Sequence,
    [r IN relationships(path) | type(r)] AS Edge_Sequence
ORDER BY relevance DESC LIMIT 5
```
1. **Vector entry point** — finds the single most similar node to the query embedding.
2. **Multi-hop traversal** — walks up to 2 hops from that entry node.
3. **Hub pruning** — drops any neighbor connected to 100+ nodes (avoids generic hubs drowning out signal).
4. **Cosine relevance filter** — keeps only neighbors with similarity > 0.55 to the original query.
5. **Serialization** — paths are linearised as `NodeA --[EDGE]--> NodeB` strings the LLM can read.

### 3. Router (`router.py`)
Binds all three tools to `gemini-2.5-flash` and runs an **agentic loop** (up to 5 rounds):

```
while rounds < 5:
    call LLM with current message history
    if no tool_calls → return text response
    execute each called tool → append ToolMessage
    continue loop
```

The loop is necessary because Gemini 2.5 Flash (thinking mode) will sometimes chain multiple tool calls before it is ready to synthesize — e.g. first running the graph traversal, then following up with a document search. A single-pass design would return blank output on those iterations.

`_extract_text` handles Gemini 2.5's list-based content format (thinking blocks + text blocks) and falls back to the thinking block text if no explicit text block is present.

### 4. Entry Point (`main.py`)
Runs the stress-test query and prints the synthesized answer:
```
"What is the name of the executive who leads the AI company
 that competes with the startup Microsoft just bought?"
```
This query requires the LLM to: (a) identify it needs graph traversal, (b) find the Microsoft acquisition, (c) reason about competitors — a true multi-hop relational question.

---

## Project Structure

```
.
├── config.py          # Env loading, Neo4j driver, Gemini embedder
├── tools.py           # Trinity of LangChain tools
├── router.py          # Agentic routing loop
├── main.py            # Entry point / stress test
├── setup_db.py              # One-time: creates the Neo4j vector index
├── seed_db.py               # One-time: loads pre-built knowledge graph into Neo4j
├── seed_db_unstructured.py  # One-time: extracts graph from raw text via Gemini, then loads it
├── embed_nodes.py           # One-time: normalises nodes and stores Gemini embeddings
├── docker-compose.yml # Neo4j 5.x container with APOC plugin
├── requirements.txt   # Python dependencies
└── .env.example       # Environment variable template
```

---

## Setup & Running

### Prerequisites
- Docker
- Python 3.10+
- A Google API key with Gemini access

### 1. Start Neo4j
```bash
docker compose up -d
```
Wait ~15 seconds for the healthcheck to pass. The Neo4j Browser is available at `http://localhost:7474`.

### 2. Install dependencies
```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env
# Edit .env and set GOOGLE_API_KEY to your Gemini API key
```

### 4. One-time database setup
Run these scripts once in order:

```bash
python setup_db.py          # Creates the vector index (alphafund_embeddings)
```

Then seed the knowledge graph — pick one approach:

**Option A — Pre-built data** (fast, no extra API calls):
```bash
python seed_db.py
```

**Option B — Unstructured ingestion pipeline** (demonstrates the full extraction flow):
```bash
python seed_db_unstructured.py
```
This feeds raw news-style articles to Gemini, extracts entities and relationships
as structured JSON, then writes the resulting graph to Neo4j.

Finally, generate vector embeddings on all nodes:
```bash
python embed_nodes.py       # Generates and stores Gemini embeddings on all nodes
```

### 5. Run the router
```bash
python main.py
```

Expected output:
```
============================================================
 EXECUTING THE TRINITY ROUTER
============================================================

[Router] Analyzing User Intent: '...'
[Router] Decision: Firing 'traverse_knowledge_graph' Engine.
[Tool Execution] Triggering GraphRAG for: '...'
[Router] Data acquired. Synthesizing final response...

========================================
 FINAL SYNTHESIZED EXECUTIVE SUMMARY
========================================
<Gemini's synthesized answer>
```

---

## Key Design Decisions

**Why a loop instead of a single LLM call?**
Gemini 2.5 Flash with thinking mode can decide to chain tool calls across multiple turns. The agentic loop allows the model to refine its search strategy mid-flight, which produces better answers on complex queries.

**Why `gemini-embedding-001` instead of `text-embedding-004`?**
`gemini-embedding-001` produces 3072-dimensional vectors vs 768 from `text-embedding-004`, giving higher-fidelity semantic similarity at the vector entry point. The Neo4j index is configured to match (3072 dims, cosine similarity).

**Why prune hub nodes (`COUNT { (neighbor)--() } < 100`)?**
Highly connected nodes (e.g. a generic "Technology" category) appear in almost every path and add noise without relevance. Pruning them keeps the returned paths focused on specific entities.

---

## Dependencies

| Package | Purpose |
|---|---|
| `langchain-core` | Tool definitions, message types |
| `langchain-google-genai` | Gemini LLM + embedding client |
| `google-generativeai` | Underlying Google AI SDK |
| `neo4j` | Bolt driver for Neo4j |
| `python-dotenv` | `.env` file loading |
