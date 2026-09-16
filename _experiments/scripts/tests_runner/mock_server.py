"""A mock OpenAI-compatible server, so the runners can be tested without a GPU.

The runner talks to it over HTTP through the real `openai` client, so the request
the runner builds and the response it reads are exercised end to end: the
reasoning options, the gateway guard, the retry policy, the fallback parser and
the history the template would see.

    with MockOpenAIServer() as server:
        server.push(tool_call("get_statistics", {}))
        server.push(text("done"))
        ...  # run the runner against server.url
"""

from __future__ import annotations

import json
import threading
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

__all__ = ["MockOpenAIServer", "text", "tool_call", "raw_content", "status", "malformed"]


def _completion(message: dict, finish_reason: str, *, model: str = "mock",
                usage: dict | None = None, extra: dict | None = None) -> dict:
    body = {
        "id": "chatcmpl-mock", "object": "chat.completion", "created": 0, "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", **message},
                     "finish_reason": finish_reason}],
        "usage": usage or {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    if extra:
        body.update(extra)
    return body


def text(content: str, *, finish_reason: str = "stop", reasoning: str | None = None,
         **extra) -> dict:
    message: dict[str, Any] = {"content": content}
    if reasoning is not None:
        message["reasoning_content"] = reasoning
    return _completion(message, finish_reason, **extra)


def tool_call(*calls, content: str = "", reasoning: str | None = None,
              finish_reason: str = "tool_calls", **extra) -> dict:
    """`tool_call(("name", {"a": 1}), ...)` or `tool_call("name", {"a": 1})`."""
    if calls and isinstance(calls[0], str):
        calls = [(calls[0], calls[1] if len(calls) > 1 else {})]
    message: dict[str, Any] = {"content": content, "tool_calls": [
        {"id": f"call_{i}", "type": "function",
         "function": {"name": name,
                      "arguments": args if isinstance(args, str)
                      else json.dumps(args, ensure_ascii=False)}}
        for i, (name, args) in enumerate(calls)]}
    if reasoning is not None:
        message["reasoning_content"] = reasoning
    return _completion(message, finish_reason, **extra)


def raw_content(content: str, *, finish_reason: str = "stop") -> dict:
    """A reply with no native tool calls, for the fallback parser."""
    return _completion({"content": content}, finish_reason)


def malformed(kind: str = "no_choices") -> dict:
    if kind == "no_choices":
        return {"id": "chatcmpl-mock", "object": "chat.completion", "created": 0,
                "model": "mock", "choices": []}
    if kind == "empty":
        return _completion({"content": ""}, "stop")
    raise ValueError(kind)


class status:
    """Return an HTTP error instead of a completion."""

    def __init__(self, code: int, message: str = "error"):
        self.code = code
        self.message = message


class _Handler(BaseHTTPRequestHandler):
    server_version = "MockOpenAI/1.0"

    def log_message(self, *args):  # keep pytest output clean
        pass

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path.endswith("/health"):
            self._send(200, {"status": "ok"})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        request = json.loads(self.rfile.read(length) or b"{}")
        state = self.server.state
        with state.lock:
            state.requests.append(request)
            response = state.next_response(request)
        if isinstance(response, status):
            self._send(response.code, {"error": {"message": response.message,
                                                 "type": "mock_error"}})
            return
        self._send(200, response)


class _State:
    def __init__(self):
        self.lock = threading.Lock()
        self.requests: list[dict] = []
        self.queue: deque = deque()
        self.default: Any = None
        self.handler: Callable[[dict], Any] | None = None

    def next_response(self, request: dict) -> Any:
        if self.handler is not None:
            return self.handler(request)
        if self.queue:
            return self.queue.popleft()
        if self.default is not None:
            return self.default
        return text("no script left")


class MockOpenAIServer:
    def __init__(self):
        self.state = _State()
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._httpd.state = self.state
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    # -- lifecycle -------------------------------------------------------
    def __enter__(self) -> "MockOpenAIServer":
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=5)

    @property
    def url(self) -> str:
        host, port = self._httpd.server_address[:2]
        return f"http://{host}:{port}/v1"

    # -- scripting -------------------------------------------------------
    def push(self, *responses) -> "MockOpenAIServer":
        self.state.queue.extend(responses)
        return self

    def always(self, response) -> "MockOpenAIServer":
        self.state.default = response
        return self

    def respond_with(self, handler: Callable[[dict], Any]) -> "MockOpenAIServer":
        self.state.handler = handler
        return self

    @property
    def requests(self) -> list[dict]:
        return list(self.state.requests)
