"""A tool-free, isolated SDK session; failures never become offline success."""

from ..sdk import SdkError, request_analysis
from .logs import Evidence, IncidentError
from .report import Analysis, SYSTEM_PROMPT, analysis_schema, model_prompt, validate_analysis


async def analyze_with_copilot(
    evidence: Evidence, model: str, timeout: float
) -> Analysis:
    try:
        raw = await request_analysis(
            model_prompt(evidence), SYSTEM_PROMPT, analysis_schema(evidence), model, timeout
        )
    except SdkError as error:
        raise IncidentError(str(error)) from error
    return validate_analysis(raw, evidence)
