import json
from typing import Callable, TypedDict
import urllib.parse
import urllib.request
from pathlib import Path

from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelRequest,
    ModelResponse,
    dynamic_prompt,
    wrap_model_call,
)
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from env_utils import load_project_dotenv

load_project_dotenv(Path(__file__).with_name(".env"))

class Context(TypedDict):
    user_role: str

@tool
def public_search(query: str) -> str:
    """Search for information."""
    return f"Results for: {query}"

@tool
def public_get_weather(city: str) -> str:
    """Get current weather for a given city via the Open-Meteo API."""
    geo_url = "https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode(
        {"name": city, "count": 1, "format": "json"}
    )
    with urllib.request.urlopen(geo_url, timeout=10) as resp:
        results = (json.load(resp).get("results") or [])
    if not results:
        return f"Could not find location: {city}"
    loc = results[0]
    name = ", ".join(p for p in [loc.get("name"), loc.get("admin1"), loc.get("country")] if p)

    forecast_url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(
        {
            "latitude": loc["latitude"],
            "longitude": loc["longitude"],
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
        }
    )
    with urllib.request.urlopen(forecast_url, timeout=10) as resp:
        cur = json.load(resp)["current"]
    return (
        f"Weather in {name}: {cur['temperature_2m']}°F, "
        f"humidity {cur['relative_humidity_2m']}%, "
        f"wind {cur['wind_speed_10m']} mph "
        f"(WMO code {cur['weather_code']})."
    )



basic_model = ChatOpenAI(
    model="gpt-5.4-mini",
    temperature=0.1,
    max_tokens=1000,
    timeout=30)
advanced_model = ChatOpenAI(
    model="gpt-5.4",
    temperature=0.1,
    max_tokens=1000,
    timeout=30
    # ... (other params)
)

@wrap_model_call
def dynamic_model_selection(request: ModelRequest, handler) -> ModelResponse:
    """Choose model based on conversation complexity."""
    message_count = len(request.state["messages"])

    if message_count > 10:
        # Use an advanced model for longer conversations
        model = advanced_model
    else:
        model = basic_model

    return handler(request.override(model=model))

@wrap_model_call
def state_based_tools(
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse]
) -> ModelResponse:
    """Filter tools based on conversation State."""
    state = request.state
    is_authenticated = state.get("authenticated", False)
    message_count = len(state["messages"])

    if not is_authenticated:
        # Only enable public tools before authentication
        tools = [t for t in request.tools if t.name.startswith("public_")]
        request = request.override(tools=tools)
    elif message_count < 5:
        # Limit tools early in conversation
        tools = [t for t in request.tools if t.name != "advanced_search"]
        request = request.override(tools=tools)

    return handler(request)

@dynamic_prompt
def user_role_prompt(request: ModelRequest) -> str:
    """Generate system prompt based on user role."""
    runtime_context = request.runtime.context or {}
    user_role = runtime_context.get("user_role", "user")
    base_prompt = "You are a helpful assistant."

    if user_role == "expert":
        return f"{base_prompt} Provide detailed technical responses."
    elif user_role == "everyone-else":
        return f"{base_prompt} Explain concepts simply and avoid jargon."

    return base_prompt

agent = create_agent(
    model=basic_model,  # Default model
    tools=[public_search, public_get_weather],
    system_prompt="You are a helpful weather assistant, but you can also search for information if needed. Use the tools at your disposal to provide accurate and concise answers.  Always check if the user is authenticated before using any tools, and choose the appropriate model based on the conversation length.",
    middleware=[dynamic_model_selection, state_based_tools, user_role_prompt],
    context_schema=Context
)

if __name__ == "__main__":
    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "What's the weather in San Francisco? I've been there a few times and it's always been nice. Can you also tell me about the weather in New York? I heard it's quite different from San Francisco. By the way, I'm planning a trip to both cities next month, so any tips on what to expect would be great!  Also, can you search for any upcoming weather events in those areas? I want to make sure I'm prepared for any surprises. Thanks!",
                }
            ],
            "authenticated": True,
        },
        context={"user_role": "export"},
    )

    print(result["messages"][-1].content_blocks)
