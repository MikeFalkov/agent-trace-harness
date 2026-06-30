# Parsed Context Growth

Source log: `agent_trace_20260630_163308.jsonl`

This view keeps the context-relevant records only: user prompts, assistant responses, tool calls, and tool outputs. Snapshot metadata, request byte sizes, character counts, and streaming internals are omitted.

## Final Context Sequence

| Index | Kind                   | Summary                                                                                                                              |
| :---: | :--------------------: | ------------------------------------------------------------------------------------------------------------------------------------ |
|     0 | `user_message`         | User: Answer the question inside file.txt                                                                                            |
|     1 | `function_call`        | Tool call: `list_files` `{"directory": "."}`                                                                                         |
|     2 | `function_call_output` | Tool output: `list_files` ok=True, entries: file.txt, notes.txt, summary.txt                                                         |
|     3 | `function_call`        | Tool call: `read_text_file` `{"path": "file.txt", "max_chars": 1000}`                                                                |
|     4 | `function_call_output` | Tool output: `read_text_file` ok=True, `file.txt` content: `What is the capital of France?`                                          |
|     5 | `assistant_message`    | Assistant: Paris                                                                                                                     |
|     6 | `user_message`         | User: What is the number 1 best place to visit there?                                                                                |
|     7 | `assistant_message`    | Assistant: A top choice is the Eiffel Tower.                                                                                         |
|     8 | `user_message`         | User: Make note of this inside notes.txt                                                                                             |
|     9 | `function_call`        | Tool call: `write_text_file` `{"path": "notes.txt", "content": "Top place to visit in Paris: the Eiffel Tower.", "overwrite": true}` |
|    10 | `function_call_output` | Tool output: `write_text_file` ok=True, wrote `notes.txt`                                                                            |
|    11 | `assistant_message`    | Assistant: Done.                                                                                                                     |

## Turn 0

Context size: 0 items before turn, 6 items after turn.

### Items added

#### 0. User prompt

```text
Answer the question inside file.txt
```

#### 1. Tool call: `list_files`

Arguments:

```json
{
  "directory": "."
}
```

Tool result:

```json
{
  "ok": true,
  "workspace": "/home/mike/Projects/harness/workspace",
  "directory": ".",
  "entries": [
    {
      "name": "file.txt",
      "relative_path": "file.txt",
      "type": "file",
      "size_bytes": 31,
      "modified": "2026-06-02T16:04:44.053657"
    },
    {
      "name": "notes.txt",
      "relative_path": "notes.txt",
      "type": "file",
      "size_bytes": 13,
      "modified": "2026-06-30T16:07:50.371638"
    },
    {
      "name": "summary.txt",
      "relative_path": "summary.txt",
      "type": "file",
      "size_bytes": 106,
      "modified": "2026-06-02T16:08:01.486744"
    }
  ]
}
```

#### 2. Tool output appended to context

```json
{
  "ok": true,
  "tool": "list_files",
  "args": {
    "directory": "."
  },
  "result": {
    "ok": true,
    "workspace": "/home/mike/Projects/harness/workspace",
    "directory": ".",
    "entries": [
      {
        "name": "file.txt",
        "relative_path": "file.txt",
        "type": "file",
        "size_bytes": 31,
        "modified": "2026-06-02T16:04:44.053657"
      },
      {
        "name": "notes.txt",
        "relative_path": "notes.txt",
        "type": "file",
        "size_bytes": 13,
        "modified": "2026-06-30T16:07:50.371638"
      },
      {
        "name": "summary.txt",
        "relative_path": "summary.txt",
        "type": "file",
        "size_bytes": 106,
        "modified": "2026-06-02T16:08:01.486744"
      }
    ]
  }
}
```

#### 3. Tool call: `read_text_file`

Arguments:

```json
{
  "path": "file.txt",
  "max_chars": 1000
}
```

Tool result:

```json
{
  "ok": true,
  "path": "file.txt",
  "size_bytes": 31,
  "max_chars": 1000,
  "truncated": false,
  "content": "What is the capital of France?\n"
}
```

#### 4. Tool output appended to context

```json
{
  "ok": true,
  "tool": "read_text_file",
  "args": {
    "path": "file.txt",
    "max_chars": 1000
  },
  "result": {
    "ok": true,
    "path": "file.txt",
    "size_bytes": 31,
    "max_chars": 1000,
    "truncated": false,
    "content": "What is the capital of France?\n"
  }
}
```

#### 5. Assistant response

```text
Paris
```

### Context after this turn

- 0. User: Answer the question inside file.txt
- 1. Tool call `list_files` {"directory":"."}
- 2. Tool output from `list_files`
- 3. Tool call `read_text_file` {"path":"file.txt","max_chars":1000}
- 4. Tool output from `read_text_file`
- 5. Assistant: Paris

## Turn 1

Context size: 6 items before turn, 8 items after turn.

### Items added

#### 6. User prompt

```text
What is the number 1 best place to visit there?
```

#### 7. Assistant response

```text
A top choice is the Eiffel Tower.
```

### Context after this turn

- 0. User: Answer the question inside file.txt
- 1. Tool call `list_files` {"directory":"."}
- 2. Tool output from `list_files`
- 3. Tool call `read_text_file` {"path":"file.txt","max_chars":1000}
- 4. Tool output from `read_text_file`
- 5. Assistant: Paris
- 6. User: What is the number 1 best place to visit there?
- 7. Assistant: A top choice is the Eiffel Tower.

## Turn 2

Context size: 8 items before turn, 12 items after turn.

### Items added

#### 8. User prompt

```text
Make note of this inside notes.txt
```

#### 9. Tool call: `write_text_file`

Arguments:

```json
{
  "path": "notes.txt",
  "content": "Top place to visit in Paris: the Eiffel Tower.",
  "overwrite": true
}
```

Tool result:

```json
{
  "ok": true,
  "path": "notes.txt",
  "size_bytes": 46
}
```

#### 10. Tool output appended to context

```json
{
  "ok": true,
  "tool": "write_text_file",
  "args": {
    "path": "notes.txt",
    "content": "Top place to visit in Paris: the Eiffel Tower.",
    "overwrite": true
  },
  "result": {
    "ok": true,
    "path": "notes.txt",
    "size_bytes": 46
  }
}
```

#### 11. Assistant response

```text
Done.
```

### Context after this turn

- 0. User: Answer the question inside file.txt
- 1. Tool call `list_files` {"directory":"."}
- 2. Tool output from `list_files`
- 3. Tool call `read_text_file` {"path":"file.txt","max_chars":1000}
- 4. Tool output from `read_text_file`
- 5. Assistant: Paris
- 6. User: What is the number 1 best place to visit there?
- 7. Assistant: A top choice is the Eiffel Tower.
- 8. User: Make note of this inside notes.txt
- 9. Tool call `write_text_file` {"path":"notes.txt","content":"Top place to visit in Paris: the Eiffel Tower.","overwrite":true}
- 10. Tool output from `write_text_file`
- 11. Assistant: Done.
