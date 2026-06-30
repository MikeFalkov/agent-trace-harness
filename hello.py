#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
from openai import APIConnectionError, APIStatusError, OpenAI
from dotenv import dotenv_values


CONFIG_PATH = Path(__file__).with_name("model-access.md")
ENV_PATH = Path(__file__).with_name(".env")


def load_local_config(path: Path = CONFIG_PATH) -> dict[str, str]:
    config: dict[str, str] = {}
    if not path.exists():
        return config

    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        config[key.strip()] = value.strip().strip("\"'")

    return config


def load_env_file(path: Path = ENV_PATH) -> dict[str, str]:
    if not path.exists():
        return {}

    return {key: value for key, value in dotenv_values(path).items() if key and value}


def first_config_value(
    *values: tuple[str, str | None],
) -> tuple[str | None, str | None]:
    return next(
        ((value, source) for source, value in values if value),
        (None, None),
    )


def event_field(event: object, name: str) -> object | None:
    if isinstance(event, dict):
        return event.get(name)
    return getattr(event, name, None)


def main() -> int:
    env_file = load_env_file()
    config = load_local_config()
    api_key, api_key_source = first_config_value(
        (".env api_key", env_file.get("api_key")),
        (".env OPENAI_API_KEY", env_file.get("OPENAI_API_KEY")),
        ("environment OPENAI_API_KEY", os.getenv("OPENAI_API_KEY")),
        ("environment api_key", os.getenv("api_key")),
        ("model-access.md api_key", config.get("api_key")),
    )
    base_url, base_url_source = first_config_value(
        (".env api_endpoint", env_file.get("api_endpoint")),
        (".env OPENAI_BASE_URL", env_file.get("OPENAI_BASE_URL")),
        (".env OPENAI_API_BASE", env_file.get("OPENAI_API_BASE")),
        ("environment OPENAI_BASE_URL", os.getenv("OPENAI_BASE_URL")),
        ("environment OPENAI_API_BASE", os.getenv("OPENAI_API_BASE")),
        ("environment api_endpoint", os.getenv("api_endpoint")),
        ("model-access.md api_endpoint", config.get("api_endpoint")),
    )
    model, model_source = first_config_value(
        (".env model", env_file.get("model")),
        (".env OPENAI_MODEL", env_file.get("OPENAI_MODEL")),
        ("environment OPENAI_MODEL", os.getenv("OPENAI_MODEL")),
        ("environment model", os.getenv("model")),
        ("model-access.md model", config.get("model")),
    )

    missing = [
        name
        for name, value in (
            ("OPENAI_API_KEY or api_key", api_key),
            ("OPENAI_BASE_URL or api_endpoint", base_url),
            ("OPENAI_MODEL or model", model),
        )
        if not value
    ]
    if missing:
        print("Missing configuration: " + ", ".join(missing))
        print(f"Set environment variables or add values to {ENV_PATH.name}.")
        return 2

    client = OpenAI(api_key=api_key, base_url=base_url)
    print(f"Testing model {model} at {base_url}")
    print(
        "Config sources: "
        f"api_key={api_key_source}, "
        f"base_url={base_url_source}, "
        f"model={model_source}"
    )
    print("Response: ", end="", flush=True)

    try:
        # This gateway requires the Responses API to stream and not store results.
        stream = client.responses.create(
            model=model,
            instructions="You are a knowledgeable expert in geography.",
            input=[
                {"role": "user", "content": "What is the capital of France?"},
                {"role": "assistant", "content": "The capital of France is **Paris**."},
                {"role": "user", "content": "What is the best place to see there?"},
            ],
            store=False,
            stream=True,
        )

        text_parts: list[str] = []
        final_status = "unknown"

        for event in stream:
            event_type = event_field(event, "type")
            if event_type == "response.output_text.delta":
                delta = str(event_field(event, "delta") or "")
                text_parts.append(delta)
                print(delta, end="", flush=True)
            elif event_type == "response.completed":
                response = event_field(event, "response")
                final_status = str(event_field(response, "status") or "completed")
            elif event_type in {"error", "response.failed"}:
                print()
                print(f"Endpoint returned stream error event: {event}")
                return 1

        print()
        print(f"Status: {final_status}")
        return 0 if "".join(text_parts).strip() else 1

    except APIStatusError as exc:
        print()
        print(f"HTTP {exc.status_code}: {exc.response.text}")
        return 1
    except APIConnectionError as exc:
        print()
        print(f"Connection error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
