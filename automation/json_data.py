"""Strict JSON objects shared by the SDK automations."""

import json


def decode_object(
    text: str, context: str, error_type: type[ValueError] = ValueError
) -> dict[str, object]:
    class ObjectError(ValueError):
        pass

    def unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ObjectError("duplicate JSON field")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise ObjectError("non-finite JSON values are not allowed")

    try:
        result = json.loads(
            text, object_pairs_hook=unique_pairs, parse_constant=reject_constant
        )
    except ObjectError as error:
        raise error_type(f"{context}: {error}") from error
    except (ValueError, RecursionError) as error:
        raise error_type(f"{context}: invalid JSON ({type(error).__name__})") from error
    if not isinstance(result, dict):
        raise error_type(f"{context}: expected a JSON object")
    return result
