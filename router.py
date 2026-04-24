from langchain_core.messages import HumanMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from tools import query_financials, search_documents, traverse_knowledge_graph

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.0)
trinity_tools = [query_financials, search_documents, traverse_knowledge_graph]
llm_with_tools = llm.bind_tools(trinity_tools)

_tool_map = {
    "query_financials": query_financials,
    "search_documents": search_documents,
    "traverse_knowledge_graph": traverse_knowledge_graph,
}


MAX_TOOL_ROUNDS = 5


def alphafund_trinity_router(user_prompt: str) -> str:
    """Master cognitive loop that routes queries to the correct engine."""
    messages = [HumanMessage(content=user_prompt)]

    print(f"\n[Router] Analyzing User Intent: '{user_prompt}'")

    for _ in range(MAX_TOOL_ROUNDS):
        ai_msg = llm_with_tools.invoke(messages)
        messages.append(ai_msg)

        if not ai_msg.tool_calls:
            return _extract_text(ai_msg.content)

        for tool_call in ai_msg.tool_calls:
            print(f"[Router] Decision: Firing '{tool_call['name']}' Engine.")
            selected_tool = _tool_map[tool_call["name"]]
            tool_output = selected_tool.invoke(tool_call["args"])
            messages.append(ToolMessage(tool_call_id=tool_call["id"], content=tool_output))

        print("[Router] Data acquired. Synthesizing final response...")

    return "Router reached maximum tool-call rounds without a final text response."


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = [
            block["text"] for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        if text_parts:
            return "\n".join(text_parts)
        # Gemini 2.5 thinking mode sometimes returns only a thinking block
        thinking_parts = [
            block.get("thinking", "") for block in content
            if isinstance(block, dict) and block.get("type") == "thinking"
        ]
        return "\n".join(thinking_parts)
    return str(content)