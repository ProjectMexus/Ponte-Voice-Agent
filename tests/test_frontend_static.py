import re
import threading
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler, build_opener

from frontend.server import create_http_server


class PageElements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def by_id(self, element_id):
        return next(attrs for _, attrs in self.elements if attrs.get("id") == element_id)


class FrontendStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_http_server("127.0.0.1", 0, Path("frontend"))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.opener = build_opener(ProxyHandler({}))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_index_has_voice_text_and_persistent_service_surfaces(self):
        html = Path("frontend/index.html").read_text(encoding="utf-8")
        page = PageElements(html)
        for marker in (
            "ponte-button",
            "ponte-avatar",
            "operational-status",
            "language-toggle",
            "voice-exceptions",
            "artifact-drawer",
            "message-input",
            "message-form",
            "conversation-log",
            "service-workspace",
            "workflow-progress",
            "activity-log",
        ):
            self.assertIsNotNone(page.by_id(marker))
        self.assertTrue(any("voice-status-panel" in attrs.get("class", "").split() for _, attrs in page.elements))
        ids = [attrs["id"] for _, attrs in page.elements if "id" in attrs]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate IDs break labels and app routing")
        self.assertEqual(page.by_id("conversation-log")["role"], "log")
        self.assertEqual(page.by_id("conversation-log")["aria-relevant"], "additions")
        self.assertEqual(page.by_id("send-button")["type"], "submit")
        self.assertTrue(any(tag == "label" and attrs.get("for") == "message-input" for tag, attrs in page.elements))
        self.assertTrue(any(tag == "a" and attrs.get("href") == "#message-input" for tag, attrs in page.elements))
        self.assertTrue(all(attrs.get("type") == "button" for tag, attrs in page.elements if "data-prompt" in attrs))

    def test_display_language_is_traditional_chinese_first_and_state_only(self):
        html = Path("frontend/index.html").read_text(encoding="utf-8")
        source = Path("frontend/app.js").read_text(encoding="utf-8")
        self.assertIn('data-locale="zh-Hant"', html)
        self.assertIn('data-locale="en"', html)
        self.assertIn('let displayLocale = "zh-Hant"', source)
        for marker in (
            "DISPLAY_COPY",
            'processing: ["小澳在思考中。"',
            '"speaking-response": ["小澳正在回應。"',
            'processing: ["Ponte is thinking."',
            '"speaking-response": ["Ponte is replying."',
            'user: "你"',
            'assistant: "小澳"',
            'user: "You"',
            'assistant: "Ponte"',
            "document.documentElement.lang = locale",
        ):
            self.assertIn(marker, source)
        self.assertIn('recognition.lang = "zh-HK"', Path("frontend/speech.js").read_text(encoding="utf-8"))

    def test_operational_panel_uses_existing_health_and_voice_signals(self):
        source = Path("frontend/app.js").read_text(encoding="utf-8")
        for marker in (
            "service-status-value",
            "voice-path-value",
            "microphone-status-value",
            "backend_reachable",
            "voice_ready",
            "backendVoiceReady",
            "speech.supported",
        ):
            self.assertIn(marker, source)

    def test_required_voice_assets_are_served_without_a_cache(self):
        for path in ("app.js", "demo-console.js", "interaction-view.js", "styles.css", "voice-capture.js", "voice-exceptions.js", "mcp-client.js", "ponte2.jpg"):
            with self.opener.open(self.base_url + "/" + path) as response:
                self.assertEqual(response.headers.get("Cache-Control"), "no-store")

    def test_path_traversal_is_not_served(self):
        with self.assertRaises(HTTPError) as context:
            self.opener.open(self.base_url + "/../docs/PonteArch.md")
        self.assertEqual(context.exception.code, 404)

    def test_voice_capture_uses_supported_recording_and_vad_contract(self):
        source = Path("frontend/voice-capture.js").read_text(encoding="utf-8")
        for marker in ("MediaRecorder", "audio/webm", "audio/ogg", "silenceMs: 1350", "minDurationMs: 400", "maxDurationMs: 20_000", "vadThreshold"):
            self.assertIn(marker, source)

    def test_app_protects_the_latest_voice_turn_and_interrupts_audio(self):
        source = Path("frontend/app.js").read_text(encoding="utf-8")
        for marker in ("AbortController", "latestTurn", "AbortError", "stopPlayback", "sendVoiceTurn"):
            self.assertIn(marker, source)
        self.assertIn("showUserSpeech", source)
        self.assertIn("showPonteReply", source)
        self.assertNotIn("sound-check-button", source)
        self.assertNotIn("stopAudioButton", source)
        self.assertIn('state === "speaking-response"', source)
        self.assertIn("latestTurn += 1", source)
        self.assertIn('setState("ready")', source)

    def test_action_click_cancels_previous_audio_before_clearing_error(self):
        source = Path("frontend/app.js").read_text(encoding="utf-8")
        action_block = source.split("async function handleAction", 1)[1].split("const exceptions", 1)[0]
        self.assertIn("interruptCurrentTurn();", action_block)
        self.assertLess(action_block.index("interruptCurrentTurn();"), action_block.index("exceptions.clearError();"))
        for marker in (
            "activeSpeechTurn",
            "activeSpeechTurn === latestTurn",
            'state === "audio-error" && activeSpeechTurn === latestTurn',
        ):
            self.assertIn(marker, source)

    def test_voice_transport_is_multipart_and_preserves_json_actions(self):
        source = Path("frontend/mcp-client.js").read_text(encoding="utf-8")
        for marker in ('new FormData()', 'form.append("session_id"', 'form.append("turn_id"', 'form.append("audio"', '"/api/voice/turn"'):
            self.assertIn(marker, source)

    def test_exceptions_keep_structured_approval_and_receipt_hooks(self):
        source = Path("frontend/voice-exceptions.js").read_text(encoding="utf-8")
        for marker in ("renderApproval", "renderReceipt", "openArtifact", "response?.workspace", "response?.receipt"):
            self.assertIn(marker, source)
        self.assertIn("syncExceptionSurface", source)

    def test_avatar_exceptions_render_server_workspace_actions(self):
        source = Path("frontend/voice-exceptions.js").read_text(encoding="utf-8")
        for marker in (
            "renderWorkspace",
            "renderCanonicalWorkspace",
            "response?.recovery",
            "canonicalReceiptFields",
        ):
            self.assertIn(marker, source)
        for removed in (
            "task_state",
            "current_step",
            'kind: "search_slots"',
            'kind: "select_slot"',
            "referring_appointment_id",
            "receipt.html",
        ):
            self.assertNotIn(removed, source)

    def test_speech_fallback_remains_cantonese_capable(self):
        source = Path("frontend/speech.js").read_text(encoding="utf-8")
        for marker in ("SpeechRecognition", "webkitSpeechRecognition", "zh-HK", "speechSynthesis"):
            self.assertIn(marker, source)
        self.assertIn("speechSynthesis.resume", source)
        self.assertIn("speechSynthesis.speak(utterance)", source)

    def test_controls_have_visible_focus_and_reduced_motion_support(self):
        css = Path("frontend/styles.css").read_text(encoding="utf-8")
        focus_rule = re.search(r":focus-visible\s*\{([^}]+)\}", css).group(1)
        self.assertRegex(focus_rule, r"outline:\s*(?!none|0)[^;]+")
        reduced_motion = css.split("@media (prefers-reduced-motion: reduce)", 1)[1].split("@media", 1)[0]
        self.assertRegex(reduced_motion, r"animation(?:-duration)?:")
        self.assertRegex(reduced_motion, r"transition(?:-duration)?:")
        self.assertRegex(css, r"\[hidden\]\s*\{[^}]*display:\s*none\s*!important")

    def test_receipt_and_reset_dialogs_have_accessible_titles_and_controls(self):
        page = PageElements(Path("frontend/index.html").read_text(encoding="utf-8"))
        receipt = page.by_id("artifact-drawer")
        self.assertEqual(receipt["role"], "dialog")
        self.assertEqual(receipt["aria-modal"], "true")
        self.assertIsNotNone(page.by_id(receipt["aria-labelledby"]))
        self.assertIn("hidden", receipt)
        reset = page.by_id("reset-dialog")
        self.assertIsNotNone(page.by_id(reset["aria-labelledby"]))
        for control in ("reset-cancel", "reset-confirm", "artifact-print", "artifact-download"):
            self.assertEqual(page.by_id(control)["type"], "button")
        self.assertEqual(page.by_id("global-error")["role"], "alert")
        self.assertEqual(page.by_id("workspace-loading")["role"], "status")

    def test_small_screens_stack_panels_and_print_keeps_receipt_content(self):
        css = Path("frontend/styles.css").read_text(encoding="utf-8")
        responsive = css.split("@media (max-width: 820px)", 1)[1].split("@media", 1)[0]
        self.assertRegex(responsive, r"\.demo-layout\s*\{[^}]*grid-template-columns:\s*1fr")
        print_rules = css.split("@media print", 1)[1]
        self.assertRegex(print_rules, r"#artifact-drawer:not\(\[hidden\]\)\s*\{[^}]*display:\s*block\s*!important")
        self.assertRegex(print_rules, r"\.artifact-sheet\s*\{[^}]*overflow:\s*visible")


if __name__ == "__main__":
    unittest.main()
