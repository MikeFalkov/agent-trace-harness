import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from openai import OpenAI, OpenAIError


MODEL = os.getenv("MODEL", "gpt-4.1-mini")

SYSTEM_PROMPT = (
    "You are a concise, helpful assistant. "
    "Use tools when they are useful. "
    "When the user asks for current date or time, call get_current_time. "
    "When the user asks to inspect, list, read, or write local files, use the file tools. "
    "Only work with files inside the configured workspace. "
    "Do not guess current time. "
    "Do not invent file contents."
)

TRACE_DIR = Path(os.getenv("TRACE_DIR", "traces"))
TRACE_DIR.mkdir(exist_ok=True)

TRACE_FILE = TRACE_DIR / f"agent_trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"

WORKSPACE_DIR = Path(os.getenv("AGENT_WORKSPACE", "workspace")).resolve()
WORKSPACE_DIR.mkdir(exist_ok=True)

MAX_READ_CHARS = int(os.getenv("MAX_READ_CHARS", "12000"))

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise RuntimeError("Set OPENAI_API_KEY.")

client = OpenAI(api_key=api_key)


def to_plain(obj: Any) -> Any:
    """Convert SDK objects into JSON-serializable Python objects."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json", exclude_none=True)
    if isinstance(obj, dict):
        return {k: to_plain(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_plain(v) for v in obj]
    if isinstance(obj, tuple):
        return [to_plain(v) for v in obj]
    return obj


def log_jsonl(kind: str, payload: Any) -> None:
    record = {
        "ts": datetime.now().isoformat(),
        "kind": kind,
        "payload": to_plain(payload),
    }
    with TRACE_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def full_text(value: Any) -> str:
    """Serialize a value for logs without truncating it.

    This preserves the complete content of user prompts, assistant messages,
    function call arguments, and function outputs in the trace file.
    """
    if isinstance(value, str):
        return value
    return json.dumps(to_plain(value), ensure_ascii=False)


def json_size(obj: Any) -> int:
    return len(json.dumps(to_plain(obj), ensure_ascii=False))


def summarize_context_item(item: dict, index: int) -> dict:
    item_type = item.get("type")
    role = item.get("role")

    summary = {
        "index": index,
        "type": item_type,
        "role": role,
        "json_bytes": json_size(item),
    }

    if role == "user":
        summary["kind"] = "user_message"
        summary["content"] = full_text(item.get("content", ""))

    elif role == "assistant":
        summary["kind"] = "assistant_message"
        summary["content"] = full_text(item.get("content", ""))

    elif item_type == "function_call":
        summary["kind"] = "function_call"
        summary["name"] = item.get("name")
        summary["call_id"] = item.get("call_id")
        summary["arguments"] = full_text(item.get("arguments", ""))

    elif item_type == "function_call_output":
        summary["kind"] = "function_call_output"
        summary["call_id"] = item.get("call_id")
        summary["output"] = full_text(item.get("output", ""))

    elif item_type == "message":
        summary["kind"] = "model_message"
        content = item.get("content", [])
        summary["content_items"] = len(content)
        summary["content"] = full_text(content)

    else:
        summary["kind"] = item_type or "unknown"
        summary["value"] = full_text(item)

    return summary


def summarize_context(input_items: list[dict]) -> dict:
    items = [summarize_context_item(item, i) for i, item in enumerate(input_items)]

    return {
        "item_count": len(input_items),
        "input_items_json_bytes": json_size(input_items),
        "items": items,
        "counts_by_kind": {
            kind: sum(1 for item in items if item["kind"] == kind)
            for kind in sorted({item["kind"] for item in items})
        },
    }


def log_context_snapshot(kind: str, input_items: list[dict], extra: dict | None = None) -> None:
    payload = summarize_context(input_items)
    if extra:
        payload.update(extra)
    log_jsonl(kind, payload)


def safe_workspace_path(relative_path: str) -> Path:
    requested = Path(relative_path)

    if requested.is_absolute():
        raise ValueError("Absolute paths are not allowed.")

    path = (WORKSPACE_DIR / requested).resolve()

    try:
        path.relative_to(WORKSPACE_DIR)
    except ValueError:
        raise ValueError("Path escapes workspace.")

    return path


def get_current_time(timezone: str) -> dict:
    try:
        tz = ZoneInfo(timezone)
    except Exception as e:
        return {
            "ok": False,
            "error": f"Invalid IANA timezone: {timezone}",
            "detail": str(e),
        }

    now = datetime.now(tz)

    return {
        "ok": True,
        "timezone": timezone,
        "iso": now.isoformat(),
        "readable": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
    }


def list_files(directory: str) -> dict:
    try:
        base = safe_workspace_path(directory)

        if not base.exists():
            return {
                "ok": False,
                "directory": directory,
                "error": "Directory does not exist.",
            }

        if not base.is_dir():
            return {
                "ok": False,
                "directory": directory,
                "error": "Path is not a directory.",
            }

        entries = []

        for path in sorted(base.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            stat = path.stat()

            entries.append(
                {
                    "name": path.name,
                    "relative_path": str(path.relative_to(WORKSPACE_DIR)),
                    "type": "directory" if path.is_dir() else "file",
                    "size_bytes": stat.st_size if path.is_file() else None,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )

        return {
            "ok": True,
            "workspace": str(WORKSPACE_DIR),
            "directory": directory,
            "entries": entries,
        }

    except Exception as e:
        return {
            "ok": False,
            "directory": directory,
            "error": str(e),
        }


def read_text_file(path: str, max_chars: int) -> dict:
    try:
        file_path = safe_workspace_path(path)

        if not file_path.exists():
            return {
                "ok": False,
                "path": path,
                "error": "File does not exist.",
            }

        if not file_path.is_file():
            return {
                "ok": False,
                "path": path,
                "error": "Path is not a file.",
            }

        safe_max_chars = max(1, min(int(max_chars), MAX_READ_CHARS))
        text = file_path.read_text(encoding="utf-8", errors="replace")

        return {
            "ok": True,
            "path": path,
            "size_bytes": file_path.stat().st_size,
            "max_chars": safe_max_chars,
            "truncated": len(text) > safe_max_chars,
            "content": text[:safe_max_chars],
        }

    except Exception as e:
        return {
            "ok": False,
            "path": path,
            "error": str(e),
        }


def write_text_file(path: str, content: str, overwrite: bool) -> dict:
    try:
        file_path = safe_workspace_path(path)

        if file_path.exists() and not overwrite:
            return {
                "ok": False,
                "path": path,
                "error": "File exists and overwrite is false.",
            }

        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

        return {
            "ok": True,
            "path": path,
            "size_bytes": file_path.stat().st_size,
        }

    except Exception as e:
        return {
            "ok": False,
            "path": path,
            "error": str(e),
        }


TOOL_SCHEMAS = [
    {
        "type": "function",
        "name": "get_current_time",
        "description": "Get the current date and time for an IANA timezone.",
        "parameters": {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "IANA timezone, for example America/New_York, Europe/London, Asia/Tokyo, or UTC.",
                }
            },
            "required": ["timezone"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "list_files",
        "description": "List files and directories inside the agent workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Relative directory path inside the workspace. Use '.' for the workspace root.",
                }
            },
            "required": ["directory"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "read_text_file",
        "description": "Read a UTF-8 text file from the agent workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative file path inside the workspace.",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum number of characters to return.",
                },
            },
            "required": ["path", "max_chars"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "write_text_file",
        "description": "Write a UTF-8 text file inside the agent workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative file path inside the workspace.",
                },
                "content": {
                    "type": "string",
                    "description": "Text content to write.",
                },
                "overwrite": {
                    "type": "boolean",
                    "description": "Whether to overwrite an existing file.",
                },
            },
            "required": ["path", "content", "overwrite"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]

TOOL_HANDLERS = {
    "get_current_time": get_current_time,
    "list_files": list_files,
    "read_text_file": read_text_file,
    "write_text_file": write_text_file,
}


def call_tool(name: str, args: dict) -> dict:
    fn = TOOL_HANDLERS.get(name)

    if not fn:
        return {
            "ok": False,
            "error": f"Unknown tool: {name}",
        }

    try:
        result = fn(**args)
        return {
            "ok": True,
            "tool": name,
            "args": args,
            "result": result,
        }

    except Exception as e:
        return {
            "ok": False,
            "tool": name,
            "args": args,
            "error": str(e),
        }


def stream_response(input_items: list[dict], turn_index: int, round_index: int) -> dict:
    request = {
        "model": MODEL,
        "instructions": SYSTEM_PROMPT,
        "input": input_items,
        "tools": TOOL_SCHEMAS,
        "tool_choice": "auto",
        "parallel_tool_calls": False,
        "store": False,
        "stream": True,
    }

    log_context_snapshot(
        "context_before_request",
        input_items,
        {
            "turn_index": turn_index,
            "round_index": round_index,
            "instructions_chars": len(SYSTEM_PROMPT),
            "tools_count": len(TOOL_SCHEMAS),
            "tools_json_bytes": json_size(TOOL_SCHEMAS),
            "request_json_bytes": json_size(request),
        },
    )

    final_response = None
    printed_prefix = False

    stream = client.responses.create(**request)

    for event in stream:
        event_obj = to_plain(event)
        event_type = event_obj.get("type")

        if event_type == "response.output_text.delta":
            delta = event_obj.get("delta") or ""

            if delta:
                if not printed_prefix:
                    print("AI: ", end="", flush=True)
                    printed_prefix = True

                print(delta, end="", flush=True)

        elif event_type == "response.completed":
            final_response = event_obj.get("response")

        elif event_type in {"response.failed", "response.error", "error"}:
            log_jsonl("model_error", event_obj)
            print()
            print("OpenAI API error event:")
            print(json.dumps(event_obj, indent=2, ensure_ascii=False))
            raise RuntimeError("Response stream failed.")

    if printed_prefix:
        print("\n")

    if final_response is None:
        raise RuntimeError("Stream ended without response.completed.")

    log_jsonl(
        "model_usage",
        {
            "turn_index": turn_index,
            "round_index": round_index,
            "response_id": final_response.get("id"),
            "usage": final_response.get("usage"),
            "output_item_count": len(final_response.get("output", [])),
            "output_json_bytes": json_size(final_response.get("output", [])),
        },
    )

    return final_response


def extract_function_calls(response: dict) -> list[dict]:
    output_items = response.get("output", [])

    return [
        item
        for item in output_items
        if item.get("type") == "function_call"
    ]


def run_agent_turn(input_items: list[dict], turn_index: int, max_tool_rounds: int = 4) -> None:
    for round_index in range(max_tool_rounds):
        before_count = len(input_items)

        response = stream_response(input_items, turn_index, round_index)

        output_items = response.get("output", [])
        input_items.extend(output_items)

        for offset, item in enumerate(output_items):
            absolute_index = before_count + offset
            log_jsonl(
                "context_append",
                {
                    "turn_index": turn_index,
                    "round_index": round_index,
                    "source": "model_output",
                    "item": summarize_context_item(item, absolute_index),
                    "context_item_count_after": absolute_index + 1,
                },
            )

        function_calls = extract_function_calls(response)

        if not function_calls:
            log_context_snapshot(
                "turn_end",
                input_items,
                {
                    "turn_index": turn_index,
                    "round_index": round_index,
                },
            )
            return

        for call in function_calls:
            name = call["name"]
            call_id = call["call_id"]
            raw_args = call.get("arguments") or "{}"

            try:
                args = json.loads(raw_args)

            except json.JSONDecodeError as e:
                args = {}
                tool_result = {
                    "ok": False,
                    "error": "Tool arguments were not valid JSON.",
                    "raw_arguments": raw_args,
                    "detail": str(e),
                }

            else:
                tool_result = call_tool(name, args)

            tool_output = {
                "type": "function_call_output",
                "call_id": call_id,
                "output": json.dumps(tool_result, ensure_ascii=False),
            }

            log_jsonl(
                "tool_result",
                {
                    "turn_index": turn_index,
                    "round_index": round_index,
                    "tool": name,
                    "call_id": call_id,
                    "args": args,
                    "ok": tool_result.get("ok"),
                    "result_json_bytes": json_size(tool_result),
                    "result": to_plain(tool_result),
                },
            )

            input_items.append(tool_output)

            log_jsonl(
                "context_append",
                {
                    "turn_index": turn_index,
                    "round_index": round_index,
                    "source": "tool_output",
                    "item": summarize_context_item(tool_output, len(input_items) - 1),
                    "context_item_count_after": len(input_items),
                },
            )

            print(f"[tool_call] {name} {json.dumps(args, ensure_ascii=False)}")
            print(f"[tool_output] {tool_output['output']}\n")

    print("[stopped] Max tool rounds reached.")


def main() -> None:
    input_items: list[dict] = []
    turn_index = 0

    print("Chat started. Type 'exit' or 'quit' to stop.")
    print(f"Workspace: {WORKSPACE_DIR}")
    print(f"Trace file: {TRACE_FILE}\n")

    while True:
        user_text = input("You: ").strip()

        if user_text.lower() in {"exit", "quit"}:
            break

        if not user_text:
            continue

        checkpoint = len(input_items)

        user_item = {"role": "user", "content": user_text}
        input_items.append(user_item)

        log_jsonl(
            "turn_start",
            {
                "turn_index": turn_index,
                "user_message_chars": len(user_text),
                "user_message": full_text(user_text),
                "context_item_count_before_user": checkpoint,
                "context_item_count_after_user": len(input_items),
            },
        )

        log_jsonl(
            "context_append",
            {
                "turn_index": turn_index,
                "round_index": None,
                "source": "user_input",
                "item": summarize_context_item(user_item, len(input_items) - 1),
                "context_item_count_after": len(input_items),
            },
        )

        try:
            run_agent_turn(input_items, turn_index)
            turn_index += 1

        except OpenAIError as e:
            input_items[checkpoint:] = []
            log_jsonl(
                "turn_rollback",
                {
                    "turn_index": turn_index,
                    "error": str(e),
                    "context_item_count_after_rollback": len(input_items),
                },
            )
            print(f"OpenAI API error: {e}\n")

        except Exception as e:
            input_items[checkpoint:] = []
            log_jsonl(
                "turn_rollback",
                {
                    "turn_index": turn_index,
                    "error": str(e),
                    "context_item_count_after_rollback": len(input_items),
                },
            )
            print(f"Agent error: {e}\n")


if __name__ == "__main__":
    main()