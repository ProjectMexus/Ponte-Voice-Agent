"""Configured model/backend endpoints cannot redirect credentials to other hosts."""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from MCP.errors import AdapterError
from MCP.registry import build_registry
from MCP.rest_adapter import RestAdapter
from middleware.llm_transport import ChatCompletionError, OpenAICompatibleChatClient


class TransportRedirectTests(unittest.TestCase):
    def setUp(self):
        self.target_requests = []
        captured = self.target_requests

        class Target(BaseHTTPRequestHandler):
            def do_GET(self):
                captured.append(dict(self.headers))
                raw = json.dumps({"data": [], "choices": [{"message": {"content": '{"action":"respond","message":"Unexpected redirect"}'}}]}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *args):
                pass

        self.target = ThreadingHTTPServer(("127.0.0.1", 0), Target)
        target_url = f"http://127.0.0.1:{self.target.server_port}/unregistered-target"

        class Redirect(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", target_url)
                self.send_header("Content-Length", "0")
                self.end_headers()

            do_POST = do_GET

            def log_message(self, *args):
                pass

        self.source = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
        self.threads = []
        for server in (self.target, self.source):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.threads.append(thread)
        self.url = f"http://127.0.0.1:{self.source.server_port}"

    def tearDown(self):
        for server in (self.source, self.target):
            server.shutdown()
            server.server_close()
        for thread in self.threads:
            thread.join(2)

    def test_chat_transport_does_not_follow_redirect_or_forward_api_key(self):
        client = OpenAICompatibleChatClient(self.url, model="scripted", api_key="test-redirect-key")
        with self.assertRaises(ChatCompletionError):
            client.complete([{"role": "user", "content": "Hello"}])
        self.assertEqual(self.target_requests, [])

    def test_mcp_rest_transport_does_not_follow_redirect_or_forward_identity(self):
        adapter = RestAdapter(self.url)
        with self.assertRaises(AdapterError):
            adapter.invoke(build_registry().get("medical.list_departments"), {
                "context": {"authorization": "Bearer test-redirect-token", "accept_language": "en-US"}, "input": {},
            })
        self.assertEqual(self.target_requests, [])
