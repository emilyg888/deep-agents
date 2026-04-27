import os
from pathlib import Path

from langchain.agents import create_agent
from langchain.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from env_utils import load_project_dotenv

load_project_dotenv(Path(__file__).with_name(".env"))

if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError(
        "OPENAI_API_KEY is not set. Add it to .env or export it in your shell."
    )


@tool
def search_news(query: str) -> str:
    """Search for news information."""
    return f"News search results for: {query}"


agent = create_agent(
    model=ChatOpenAI(model="gpt-5.4-mini", temperature=0.1, max_tokens=1000, timeout=30),
    tools=[search_news],
    system_prompt="You are a helpful assistant that searches for and summarizes news.",
)


if __name__ == "__main__":
    for chunk in agent.stream(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "Search for AI news and summarize the findings",
                }
            ]
        },
        stream_mode="values",
    ):
        latest_message = chunk["messages"][-1]
        if latest_message.content:
            if isinstance(latest_message, HumanMessage):
                print(f"User: {latest_message.content}")
            elif isinstance(latest_message, AIMessage):
                print(f"Agent: {latest_message.content}")
        elif latest_message.tool_calls:
            print(f"Calling tools: {[tc['name'] for tc in latest_message.tool_calls]}")
