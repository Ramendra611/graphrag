"""
One-time script to prepare existing Neo4j nodes for vector search:
  1. Normalizes id/original_text from name/title where missing
  2. Adds the :Entity label to every node
  3. Generates embeddings via gemini-embedding-001 and stores them
"""
from config import NEO4J_DRIVER, EMBEDDER

# Step 1: Normalize nodes that only have `name` or `title`
NORMALIZE = """
MATCH (n)
WHERE n.id IS NULL
SET n.id = coalesce(n.name, n.title),
    n.original_text = coalesce(n.name, n.title)
"""

# Step 2: Add :Entity label to every node
ADD_LABEL = "MATCH (n) SET n:Entity"

# Step 3: Fetch all nodes that need an embedding
FETCH = "MATCH (n:Entity) WHERE n.original_text IS NOT NULL RETURN n.id AS id, n.original_text AS text"

# Step 4: Store embedding back onto the node
STORE = "MATCH (n:Entity {id: $id}) SET n.embedding = $embedding"

with NEO4J_DRIVER.session() as session:
    session.run(NORMALIZE)
    print("Normalized id/original_text on legacy nodes.")

    session.run(ADD_LABEL)
    print("Added :Entity label to all nodes.")

    nodes = session.run(FETCH).data()
    print(f"Found {len(nodes)} nodes to embed.")

    for node in nodes:
        embedding = EMBEDDER.embed_query(node["text"])
        session.run(STORE, id=node["id"], embedding=embedding)
        print(f"  Embedded: {node['id']}")

    print("\nDone. All nodes are vectorized and ready for GraphRAG.")

NEO4J_DRIVER.close()