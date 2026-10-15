"""Shared tool-free SDK transport; domain adapters validate the returned JSON."""

import asyncio
from tempfile import TemporaryDirectory


class SdkError(ValueError):
    """SDK setup, transport, or final-response failure."""


async def request_analysis(
    prompt: str,
    system_prompt: str,
    schema: dict[str, object],
    model: str,
    timeout: float,
    token: str | None = None,
) -> str:
    try:
        from copilot import CopilotClient
        from copilot._jsonrpc import JsonRpcError
        from copilot.generated.rpc import PermissionDecisionUserNotAvailable
        from copilot.session_events import AssistantMessageData
    except ImportError as error:
        raise SdkError(
            "Copilot SDK dependencies are unavailable. Install requirements-copilot.txt "
            "in the Python environment running this command."
        ) from error

    def deny_permission(*_args: object) -> PermissionDecisionUserNotAvailable:
        return PermissionDecisionUserNotAvailable()

    try:
        with TemporaryDirectory(prefix="portfolio-copilot-") as directory:
            async with asyncio.timeout(timeout):
                async with CopilotClient(
                    mode="empty",
                    base_directory=directory,
                    working_directory=directory,
                    builtin_plugin_directories=[],
                    use_logged_in_user=token is None,
                    github_token=token,
                    log_level="error",
                ) as client:
                    async with await client.create_session(
                        model=model,
                        available_tools=[],
                        tools=[],
                        on_permission_request=deny_permission,
                        system_message={"mode": "replace", "content": system_prompt},
                        mcp_servers={},
                        config_directory=directory,
                        enable_config_discovery=False,
                        request_extensions=False,
                    ) as session:
                        response = await session.send_and_wait(
                            prompt, response_schema=schema, timeout=timeout
                        )
    except TimeoutError as error:
        raise SdkError("Copilot SDK timed out; no report was generated") from error
    except (JsonRpcError, RuntimeError, OSError, ValueError) as error:
        raise SdkError(
            f"Copilot SDK failed ({type(error).__name__}). Check authentication, "
            "model access, network, and runtime setup. No offline fallback was used."
        ) from error
    if response is None or not isinstance(response.data, AssistantMessageData):
        raise SdkError("Copilot SDK returned no final analysis")
    if not isinstance(response.data.content, str):
        raise SdkError("Copilot SDK returned no analysis text")
    return response.data.content
