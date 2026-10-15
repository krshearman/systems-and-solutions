"""A tool-free, isolated SDK session; failures never become offline success."""

import asyncio
from tempfile import TemporaryDirectory

from .logs import Evidence, IncidentError
from .report import Analysis, SYSTEM_PROMPT, analysis_schema, model_prompt, validate_analysis


async def analyze_with_copilot(
    evidence: Evidence, model: str, timeout: float
) -> Analysis:
    prompt = model_prompt(evidence)
    try:
        from copilot import CopilotClient
        from copilot._jsonrpc import JsonRpcError
        from copilot.generated.rpc import PermissionDecisionUserNotAvailable
        from copilot.session_events import AssistantMessageData
    except ImportError as error:
        raise IncidentError(
            "Copilot SDK dependencies are unavailable. Install requirements-copilot.txt "
            "in the Python environment running this command."
        ) from error

    def deny_permission(*_args: object) -> PermissionDecisionUserNotAvailable:
        return PermissionDecisionUserNotAvailable()

    try:
        with TemporaryDirectory(prefix="incident-copilot-") as directory:
            async with asyncio.timeout(timeout):
                async with CopilotClient(
                    mode="empty",
                    base_directory=directory,
                    working_directory=directory,
                    builtin_plugin_directories=[],
                    use_logged_in_user=True,
                    log_level="error",
                ) as client:
                    async with await client.create_session(
                        model=model,
                        available_tools=[],
                        tools=[],
                        on_permission_request=deny_permission,
                        system_message={"mode": "replace", "content": SYSTEM_PROMPT},
                        mcp_servers={},
                        config_directory=directory,
                        enable_config_discovery=False,
                        request_extensions=False,
                    ) as session:
                        response = await session.send_and_wait(
                            prompt,
                            response_schema=analysis_schema(evidence),
                            timeout=timeout,
                        )
    except TimeoutError as error:
        raise IncidentError("Copilot SDK timed out; no report was generated") from error
    except (JsonRpcError, RuntimeError, OSError, ValueError) as error:
        raise IncidentError(
            f"Copilot SDK failed ({type(error).__name__}). Check authentication, "
            "model access, network, and runtime setup. No offline fallback was used."
        ) from error
    if response is None or not isinstance(response.data, AssistantMessageData):
        raise IncidentError("Copilot SDK returned no final analysis")
    if not isinstance(response.data.content, str):
        raise IncidentError("Copilot SDK returned no analysis text")
    return validate_analysis(response.data.content, evidence)
