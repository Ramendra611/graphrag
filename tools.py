from langchain_core.tools import tool
from config import NEO4J_DRIVER, EMBEDDER


@tool
def query_financials(sql_query: str) -> str:
    """Use for exact math, market caps, revenue, and strict aggregations."""
    return "MOCK SQL DATA: Microsoft Market Cap is $3.1T."


@tool
def search_documents(semantic_query: str) -> str:
    """Use for finding exact quotes, generic facts, or reading unstructured reports."""
    return "MOCK FAISS DATA: 'We are focusing heavily on AI this quarter.'"


@tool
def traverse_knowledge_graph(query: str) -> str:
    """
    Use this tool ONLY when you need to answer complex, multi-hop relational questions.
    Examples: "Who is the CEO of the competitor to the startup Microsoft bought?"
    or "How are Tony and Elena connected?"
    It uses Vector Search to find the starting entity, then walks the graph edges to find the answer.
    """
    print(f"\n[Tool Execution] Triggering GraphRAG for: '{query}'")
    prompt_vector = EMBEDDER.embed_query(query)

    # Pruned Cypher Query: vector entry point + multi-hop traversal with degree pruning
    pruned_query = """
    CALL db.index.vector.queryNodes('alphafund_embeddings', 1, $vector)
    YIELD node AS entry_node

    MATCH path = (entry_node)-[*1..2]-(neighbor)
    WHERE COUNT { (neighbor)--() } < 100

    WITH path, vector.similarity.cosine(neighbor.embedding, $vector) AS relevance
    WHERE relevance > 0.55

    RETURN
        [n IN nodes(path) | n.id] AS Node_Sequence,
        [r IN relationships(path) | type(r)] AS Edge_Sequence
    ORDER BY relevance DESC LIMIT 5
    """

    with NEO4J_DRIVER.session() as session:
        results = session.run(pruned_query, vector=prompt_vector)
        raw_paths = [record.data() for record in results]

    if not raw_paths:
        return "Graph Traversal yielded no highly relevant connections."

    # Serialize graph paths into linear strings for LLM consumption
    serialized_context = []
    for path in raw_paths:
        nodes = path["Node_Sequence"]
        edges = path["Edge_Sequence"]
        path_string = nodes[0]
        for i in range(len(edges)):
            path_string += f" --[{edges[i]}]-- {nodes[i + 1]}"
        serialized_context.append(path_string)

    return "\n".join(list(set(serialized_context)))