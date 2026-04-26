"""
Unstructured ingestion pipeline: extracts entities and relationships from
raw text using Gemini, then loads them into Neo4j.
Run BEFORE embed_nodes.py.

Pipeline:
  raw text articles
      → Gemini structured extraction (entities + relationships)
      → Neo4j graph (MERGE nodes and edges)

Usage: python seed_db_unstructured.py
"""
import re
from typing import List
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from config import NEO4J_DRIVER

# ---------------------------------------------------------------------------
# Raw unstructured source documents
# ---------------------------------------------------------------------------
RAW_ARTICLES = [
    """
    Microsoft has completed its acquisition of Inflection AI, the startup behind
    the Pi personal assistant. The deal marks Microsoft's continued push to dominate
    the AI assistant market. Satya Nadella, CEO of Microsoft, said the acquisition
    strengthens their consumer AI capabilities. Mustafa Suleyman, who co-founded
    Inflection AI, joined Microsoft as head of its consumer AI division.
    """,
    """
    OpenAI, the company behind ChatGPT, faces growing competition in the AI assistant
    space following Microsoft's Inflection AI acquisition. Sam Altman, CEO of OpenAI,
    stated that GPT-4 remains the most capable model available to consumers. OpenAI
    directly competes with Inflection AI in the personal AI assistant market.
    Microsoft has also invested billions of dollars into OpenAI.
    """,
    """
    Anthropic, the AI safety startup co-founded by Dario Amodei, is a key rival to
    Inflection AI in the conversational AI market. Dario Amodei leads Anthropic as
    its CEO, guiding the company's mission to build safe and steerable AI systems.
    Anthropic's Claude assistant competes directly with Inflection's Pi and
    OpenAI's ChatGPT.
    """,
    """
    Google DeepMind, Alphabet's consolidated AI research division, is led by
    Demis Hassabis who serves as its CEO. DeepMind's Gemini model positions the
    company as a direct competitor to Inflection AI, OpenAI, and Anthropic in the
    large language model market. Alphabet views the AI assistant race as a top
    strategic priority.
    """,
]

# ---------------------------------------------------------------------------
# Pydantic schema — defines the JSON shape Gemini must return
# ---------------------------------------------------------------------------
class Entity(BaseModel):
    id: str            # canonical full name, e.g. "Sam Altman"
    type: str          # "Person" or "Company"
    original_text: str # one-sentence description drawn from the article

class Relationship(BaseModel):
    source: str   # entity id
    relation: str # SCREAMING_SNAKE_CASE, e.g. LEADS, ACQUIRED, COMPETES_WITH
    target: str   # entity id

class ExtractionResult(BaseModel):
    entities: List[Entity]
    relationships: List[Relationship]

# ---------------------------------------------------------------------------
# LLM extractor with structured output
# ---------------------------------------------------------------------------
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.0)
extractor = llm.with_structured_output(ExtractionResult)

SYSTEM_PROMPT = """You are a knowledge graph extractor.

Given a news article, extract:
1. Named entities — companies and people only.
   - id: the canonical full name (e.g. "Sam Altman", "OpenAI")
   - type: exactly "Person" or "Company"
   - original_text: one sentence describing the entity, drawn from the article

2. Relationships between entities.
   - source / target: entity ids from your extracted list
   - relation: SCREAMING_SNAKE_CASE verb (e.g. LEADS, ACQUIRED, COMPETES_WITH,
     FOUNDED, INVESTED_IN)

Rules:
- Only extract facts explicitly stated in the article.
- Keep entity ids consistent (same name = same id across all calls).
- Do not invent entities or relationships."""

# ---------------------------------------------------------------------------
# Sanitize LLM-generated relationship type before interpolating into Cypher
# ---------------------------------------------------------------------------
def _safe_rel_type(rel: str) -> str:
    """Keep only alphanumeric and underscore, uppercase."""
    return re.sub(r"[^A-Z0-9_]", "_", rel.upper())

# ---------------------------------------------------------------------------
# Extraction loop
# ---------------------------------------------------------------------------
all_entities: dict[str, Entity] = {}
all_relationships: list[Relationship] = []

print("Extracting entities and relationships from raw articles...\n")
for i, article in enumerate(RAW_ARTICLES, 1):
    print(f"  [Article {i}/{len(RAW_ARTICLES)}] Calling Gemini...")
    result: ExtractionResult = extractor.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=article.strip()),
    ])
    for entity in result.entities:
        all_entities[entity.id] = entity  # last-write wins on duplicates
    all_relationships.extend(result.relationships)

print(f"\nExtracted {len(all_entities)} unique entities across {len(RAW_ARTICLES)} articles.")
print(f"Extracted {len(all_relationships)} relationships (before dedup).\n")

# ---------------------------------------------------------------------------
# Write to Neo4j
# ---------------------------------------------------------------------------
MERGE_NODE = """
MERGE (n:Entity {id: $id})
SET n.name          = $id,
    n.type          = $type,
    n.original_text = $original_text
"""

written_edges = 0
skipped_edges = 0

print("Writing to Neo4j...")
with NEO4J_DRIVER.session() as session:
    for entity in all_entities.values():
        session.run(MERGE_NODE, id=entity.id, type=entity.type, original_text=entity.original_text)
    print(f"  Merged {len(all_entities)} nodes.")

    seen_edges: set[tuple] = set()
    for rel in all_relationships:
        if rel.source not in all_entities or rel.target not in all_entities:
            skipped_edges += 1
            continue
        rel_type = _safe_rel_type(rel.relation)
        edge_key = (rel.source, rel_type, rel.target)
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)
        session.run(
            f"MATCH (a:Entity {{id: $src}}), (b:Entity {{id: $dst}}) MERGE (a)-[:{rel_type}]->(b)",
            src=rel.source, dst=rel.target,
        )
        written_edges += 1

    print(f"  Merged {written_edges} relationships ({skipped_edges} skipped — unknown entity).")

print("\nDone. Run embed_nodes.py next to generate vector embeddings.")
NEO4J_DRIVER.close()
