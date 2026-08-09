"""Local scripted chat-completions provider for testing the real HTTP client."""
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class ScriptedChatEndpoint:
    def __init__(self, model):
        self.model = model
        self.protocol_errors = []
        self.header_keys = []
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                status = 200
                try:
                    payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                    fixture.validate_request(payload)
                    fixture.header_keys.append(self.headers.get("Authorization"))
                    decision = model.complete(payload["messages"], **{k: v for k, v in payload.items() if k not in {"messages", "model"}})
                    if isinstance(decision, bytes):
                        raw = decision
                    elif "action" in decision:
                        if decision["action"] == "tool_call":
                            message = {"role": "assistant", "content": None, "tool_calls": [{
                                "id": f"PROVIDER-{len(model.requests)}", "type": "function", "function": {
                                    "name": decision["tool_name"].replace(".", "__"),
                                    "arguments": json.dumps(decision["arguments"]),
                                }}]}
                        else:
                            message = {"role": "assistant", "content": json.dumps(decision)}
                        raw = json.dumps({"choices": [{"finish_reason": "tool_calls" if message.get("tool_calls") else "stop", "message": message}]}).encode()
                    else:
                        raw = json.dumps(decision).encode()
                except AssertionError as error:
                    fixture.protocol_errors.append(str(error))
                    status, raw = 400, b'{"error":"fixture protocol rejection"}'
                except Exception:
                    status, raw = 503, b'{"error":"test-provider-secret"}'
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/v1/chat/completions"

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    @staticmethod
    def validate_request(payload):
        assert isinstance(payload.get("model"), str), "model is missing"
        tools = payload.get("tools", [])
        for tool in tools:
            assert re.fullmatch(r"[A-Za-z0-9_-]{1,64}", tool["function"]["name"]), "invalid provider function name"
            assert "context" not in tool["function"]["parameters"].get("properties", {}), "trusted context schema was exposed"
        awaiting = set()
        for message in payload["messages"]:
            if message["role"] == "tool":
                assert message.get("tool_call_id") in awaiting, "orphan or duplicate tool result"
                awaiting.remove(message["tool_call_id"])
            else:
                assert not awaiting, "unanswered tool call before next message"
                for call in message.get("tool_calls", []):
                    assert re.fullmatch(r"[A-Za-z0-9_-]{1,64}", call["function"]["name"]), "invalid function name in history"
                    assert call["id"] not in awaiting, "duplicate call ID"
                    assert isinstance(json.loads(call["function"]["arguments"]), dict), "tool arguments not JSON object"
                    awaiting.add(call["id"])
        assert not awaiting, "history ended with an unanswered tool call"
