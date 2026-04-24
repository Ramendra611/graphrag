from router import alphafund_trinity_router
from config import NEO4J_DRIVER

if __name__ == "__main__":
    print("=" * 60)
    print(" EXECUTING THE TRINITY ROUTER ")
    print("=" * 60)

    impossible_query = (
        "What is the name of the executive who leads the AI company "
        "that competes with the startup Microsoft just bought?"
    )

    final_answer = alphafund_trinity_router(impossible_query)

    print("\n" + "=" * 40)
    print(" FINAL SYNTHESIZED EXECUTIVE SUMMARY ")
    print("=" * 40)
    print(final_answer)

    NEO4J_DRIVER.close()