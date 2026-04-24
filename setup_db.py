"""
Run this once before main.py to create the Neo4j vector index.
Requires the Neo4j container to be running: docker compose up -d
"""
from config import NEO4J_DRIVER

# gemini-embedding-001 produces 3072-dimensional vectors
CREATE_INDEX = """
CREATE VECTOR INDEX alphafund_embeddings IF NOT EXISTS
FOR (n:Entity) ON (n.embedding)
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 3072,
    `vector.similarity_function`: 'cosine'
  }
}
"""

CHECK_INDEX = """
SHOW VECTOR INDEXES
YIELD name, state, populationPercent
WHERE name = 'alphafund_embeddings'
RETURN name, state, populationPercent
"""

with NEO4J_DRIVER.session() as session:
    session.run(CREATE_INDEX)
    print("Vector index created (or already existed).")

    result = session.run(CHECK_INDEX)
    for record in result:
        print(f"  Index : {record['name']}")
        print(f"  State : {record['state']}")
        print(f"  Populated: {record['populationPercent']:.1f}%")

NEO4J_DRIVER.close()