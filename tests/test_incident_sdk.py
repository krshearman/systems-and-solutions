import asyncio
from importlib.util import find_spec
import inspect
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from automation.incident_postmortem.logs import IncidentError, read_evidence
from automation.incident_postmortem.sdk import analyze_with_copilot


SAMPLE = Path(__file__).resolve().parents[1] / "examples/incident_response/service-incident.txt"
VALID = json.dumps({
    "executive_summary": [{"statement": "A synthetic probe reported HTTP 503.", "evidence": ["L3"]}],
    "impact": [], "suspected_causes": [],
    "follow_up_actions": ["Investigate the recorded probe failure."],
    "open_questions": ["What was the verified customer impact?"],
})


class FakeAssistantData:
    def __init__(self, content):
        self.content = content


class FakeRpcError(Exception):
    pass


class FakePermissionDenial:
    kind = "user-not-available"


class IncidentSdkTests(unittest.TestCase):
    def setUp(self):
        self.evidence = read_evidence(SAMPLE, "text")
        self.client = AsyncMock()
        self.client.__aenter__.return_value = self.client
        self.session = AsyncMock()
        self.session.__aenter__.return_value = self.session
        self.client.create_session.return_value = self.session
        self.session.send_and_wait.return_value = SimpleNamespace(
            data=FakeAssistantData(VALID)
        )
        self.factory = Mock(return_value=self.client)
        modules = {
            name: ModuleType(name) for name in (
                "copilot", "copilot._jsonrpc", "copilot.generated.rpc",
                "copilot.session_events",
            )
        }
        modules["copilot"].CopilotClient = self.factory
        modules["copilot._jsonrpc"].JsonRpcError = FakeRpcError
        modules["copilot.generated.rpc"].PermissionDecisionUserNotAvailable = FakePermissionDenial
        modules["copilot.session_events"].AssistantMessageData = FakeAssistantData
        self.modules = modules

    def run_adapter(self, timeout=10):
        with patch.dict(sys.modules, self.modules):
            return asyncio.run(analyze_with_copilot(self.evidence, "example-model", timeout))

    def test_session_has_no_tools_plugins_extensions_or_repository_context(self):
        result = self.run_adapter()
        self.assertEqual(result.executive_summary[0].evidence, ("L3",))
        client_options = self.factory.call_args.kwargs
        self.assertEqual(client_options["mode"], "empty")
        self.assertEqual(client_options["builtin_plugin_directories"], [])
        self.assertEqual(client_options["base_directory"], client_options["working_directory"])
        self.assertFalse(Path(client_options["base_directory"]).exists())
        options = self.client.create_session.call_args.kwargs
        self.assertEqual(options["available_tools"], [])
        self.assertEqual(options["tools"], [])
        self.assertEqual(options["mcp_servers"], {})
        self.assertFalse(options["enable_config_discovery"])
        self.assertFalse(options["request_extensions"])
        self.assertEqual(options["system_message"]["mode"], "replace")
        self.assertEqual(options["on_permission_request"](object(), object()).kind, "user-not-available")
        self.assertIn("response_schema", self.session.send_and_wait.call_args.kwargs)
        self.session.__aexit__.assert_awaited_once()
        self.client.__aexit__.assert_awaited_once()

    def test_timeout_and_sdk_errors_are_explicit(self):
        for failure in (TimeoutError(), RuntimeError("auth failed"), FakeRpcError("RPC failed")):
            with self.subTest(failure=type(failure).__name__):
                self.session.send_and_wait.side_effect = failure
                with self.assertRaises(IncidentError):
                    self.run_adapter()

    def test_outer_timeout_cancels_a_stalled_request_and_cleans_up(self):
        async def stalled(*args, **kwargs):
            await asyncio.sleep(10)

        self.session.send_and_wait.side_effect = stalled
        with self.assertRaisesRegex(IncidentError, "timed out"):
            self.run_adapter(timeout=0.01)
        self.session.__aexit__.assert_awaited_once()
        self.client.__aexit__.assert_awaited_once()

    def test_missing_sdk_dependencies_have_an_actionable_error(self):
        with patch.dict(sys.modules, {"copilot": None}):
            with self.assertRaisesRegex(IncidentError, "Install requirements-copilot.txt"):
                asyncio.run(analyze_with_copilot(self.evidence, "example-model", 10))

    def test_missing_final_message_is_rejected(self):
        self.session.send_and_wait.return_value = None
        with self.assertRaisesRegex(IncidentError, "no final analysis"):
            self.run_adapter()

    def test_wrong_event_type_is_rejected(self):
        self.session.send_and_wait.return_value = SimpleNamespace(data=object())
        with self.assertRaisesRegex(IncidentError, "no final analysis"):
            self.run_adapter()

    def test_missing_content_is_rejected(self):
        self.session.send_and_wait.return_value = SimpleNamespace(data=FakeAssistantData(None))
        with self.assertRaisesRegex(IncidentError, "no analysis text"):
            self.run_adapter()

    def test_invalid_model_json_is_not_accepted(self):
        self.session.send_and_wait.return_value = SimpleNamespace(data=FakeAssistantData("not JSON"))
        with self.assertRaisesRegex(IncidentError, "invalid JSON"):
            self.run_adapter()

    @unittest.skipUnless(find_spec("copilot"), "Optional pinned SDK is not installed")
    def test_adapter_arguments_bind_to_the_installed_sdk(self):
        from copilot import CopilotClient
        from copilot.session import CopilotSession

        self.run_adapter()
        inspect.signature(CopilotClient).bind(**self.factory.call_args.kwargs)
        inspect.signature(CopilotClient.create_session).bind(
            object(), **self.client.create_session.call_args.kwargs
        )
        args = self.session.send_and_wait.call_args
        inspect.signature(CopilotSession.send_and_wait).bind(
            object(), *args.args, **args.kwargs
        )


if __name__ == "__main__":
    unittest.main()
