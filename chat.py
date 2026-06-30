import os
from openai import OpenAI, OpenAIError
from icecream import ic


MODEL = os.getenv("MODEL", "gpt-5.4-mini")
SYSTEM_PROMPT = "You are a concise, helpful assistant."

messages = []

api_key = os.getenv("API_KEY")
base_url = os.getenv("BASE_URL")

client = OpenAI(api_key=api_key, base_url=base_url)

print("Chat started. Type 'exit' or 'quit' to stop.\n")


def event_field(event, name):
    if isinstance(event, dict):
        return event.get(name)
    return getattr(event, name, None)


while True:
    user_text = input("You: ").strip()

    if user_text.lower() in {"exit", "quit"}:
        break

    if not user_text:
        continue

    messages.append({"role": "user", "content": user_text})
    ic(messages)

    try:
        stream = client.responses.create(
            model=MODEL,
            instructions=SYSTEM_PROMPT,
            input=messages,
            store=False,
            stream=True,
        )
        ic(stream)

        print("AI: ", end="", flush=True)
        text_parts = []

        for event in stream:
            event_type = event_field(event, "type")
            if event_type == "response.output_text.delta":
                delta = str(event_field(event, "delta") or "")
                text_parts.append(delta)
                print(delta, end="", flush=True)
            elif event_type in {"error", "response.failed"}:
                print()
                print(f"OpenAI API error: {event}\n")
                messages.pop()
                break
        else:
            assistant_text = "".join(text_parts)
            messages.append({"role": "assistant", "content": assistant_text})
            print("\n")

    except OpenAIError as e:
        messages.pop()
        print(f"OpenAI API error: {e}\n")
