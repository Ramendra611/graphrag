"""
One-time script: loads a pre-built AlphaFund knowledge graph into Neo4j.
Run BEFORE embed_nodes.py.

Usage: python seed_db.py
"""
from config import NEO4J_DRIVER

NODES = [
    {
        "id": "Microsoft",
        "name": "Microsoft",
        "type": "Company",
        "original_text": "Microsoft is a global technology corporation known for Windows, Azure cloud, and major AI investments.",
    },
    {
        "id": "Inflection AI",
        "name": "Inflection AI",
        "type": "Company",
        "original_text": "Inflection AI is an AI startup that built the Pi personal assistant, focused on empathetic conversational AI.",
    },
    {
        "id": "OpenAI",
        "name": "OpenAI",
        "type": "Company",
        "original_text": "OpenAI is an AI research company that created ChatGPT and GPT-4, competing in the large language model space.",
    },
    {
        "id": "Anthropic",
        "name": "Anthropic",
        "type": "Company",
        "original_text": "Anthropic is an AI safety company that builds Claude, a large language model competing with GPT-4.",
    },
    {
        "id": "Google DeepMind",
        "name": "Google DeepMind",
        "type": "Company",
        "original_text": "Google DeepMind is Alphabet's AI research division, building Gemini and competing in the foundation model space.",
    },
    {
        "id": "Sam Altman",
        "name": "Sam Altman",
        "type": "Person",
        "original_text": "Sam Altman is the CEO of OpenAI, the company behind ChatGPT and GPT-4.",
    },
    {
        "id": "Dario Amodei",
        "name": "Dario Amodei",
        "type": "Person",
        "original_text": "Dario Amodei is the CEO and co-founder of Anthropic, the AI safety company.",
    },
    {
        "id": "Satya Nadella",
        "name": "Satya Nadella",
        "type": "Person",
        "original_text": "Satya Nadella is the CEO of Microsoft, who led the company's multi-billion dollar investment in OpenAI.",
    },
    {
        "id": "Demis Hassabis",
        "name": "Demis Hassabis",
        "type": "Person",
        "original_text": "Demis Hassabis is the CEO of Google DeepMind, leading AI research at Alphabet.",
    },
    {
        "id": "Mustafa Suleyman",
        "name": "Mustafa Suleyman",
        "type": "Person",
        "original_text": "Mustafa Suleyman is the co-founder of Inflection AI who later joined Microsoft as head of consumer AI.",
    },
]

# (source_id, RELATIONSHIP_TYPE, target_id)
EDGES = [
    ("Microsoft",      "ACQUIRED",      "Inflection AI"),
    ("Microsoft",      "INVESTED_IN",   "OpenAI"),
    ("OpenAI",         "COMPETES_WITH", "Inflection AI"),
    ("Anthropic",      "COMPETES_WITH", "Inflection AI"),
    ("Google DeepMind","COMPETES_WITH", "Inflection AI"),
    ("OpenAI",         "COMPETES_WITH", "Anthropic"),
    ("OpenAI",         "COMPETES_WITH", "Google DeepMind"),
    ("Sam Altman",     "LEADS",         "OpenAI"),
    ("Dario Amodei",   "LEADS",         "Anthropic"),
    ("Satya Nadella",  "LEADS",         "Microsoft"),
    ("Demis Hassabis", "LEADS",         "Google DeepMind"),
    ("Mustafa Suleyman","FOUNDED",      "Inflection AI"),
]

MERGE_NODE = """
MERGE (n:Entity {id: $id})
SET n.name         = $name,
    n.type         = $type,
    n.original_text = $original_text
"""

with NEO4J_DRIVER.session() as session:
    for node in NODES:
        session.run(MERGE_NODE, **node)
    print(f"Seeded {len(NODES)} nodes.")

    for src, rel, dst in EDGES:
        # rel is a hardcoded constant — not user input, safe to interpolate
        session.run(
            f"MATCH (a:Entity {{id: $src}}), (b:Entity {{id: $dst}}) MERGE (a)-[:{rel}]->(b)",
            src=src, dst=dst,
        )
    print(f"Seeded {len(EDGES)} relationships.")

print("\nDatabase seeded. Run embed_nodes.py next.")
NEO4J_DRIVER.close()
