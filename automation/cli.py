"""Shared bounded request timeout for the Python command-line tools."""

import argparse
import math


def request_timeout(value: str) -> float:
    try:
        result = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Timeout must be a number") from error
    if not math.isfinite(result) or not 0 < result <= 600:
        raise argparse.ArgumentTypeError("Timeout must be greater than 0 and at most 600 seconds")
    return result
