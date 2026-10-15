import unittest

from examples.refactor_guard import after, before, event_api, legacy_api, workspace


IMPLEMENTATIONS = (before, after, workspace)


class SummaryContractTests(unittest.TestCase):
    def test_counts_follow_the_documented_contract(self):
        cases = (
            ("empty input", [], {}),
            ("blank lines", ["", "\n", " \t\r\n"], {}),
            (
                "aliases and whitespace",
                [
                    "t1| warn |first\n",
                    "t2|WARNING|second\r\n",
                    "t3| err |third",
                    "t4|ERROR|fourth",
                    "t5| info |fifth",
                ],
                {"WARNING": 2, "ERROR": 2, "INFO": 1},
            ),
            (
                "unknown and empty severities",
                ["t1| notice |message", "||", "t2|   |message"],
                {"NOTICE": 1, "": 2},
            ),
            (
                "message delimiters and arbitrary timestamps",
                ["not-a-timestamp|INFO|message|with|pipes", "|warn|"],
                {"INFO": 1, "WARNING": 1},
            ),
            (
                "unicode payload",
                ["t1|INFO|caf\u00e9 \u2603", "t2|warn|message"],
                {"INFO": 1, "WARNING": 1},
            ),
        )
        for implementation in IMPLEMENTATIONS:
            for name, lines, expected in cases:
                with self.subTest(implementation=implementation.__name__, case=name):
                    original = lines.copy()
                    self.assertEqual(implementation.summarize(lines), expected)
                    self.assertEqual(lines, original)

    def test_first_seen_severity_order_is_preserved(self):
        lines = ["t|err|one", "t|info|two", "t|warn|three", "t|err|four"]
        for implementation in IMPLEMENTATIONS:
            with self.subTest(implementation=implementation.__name__):
                result = implementation.summarize(lines)
                self.assertEqual(
                    list(result.items()),
                    [("ERROR", 2), ("INFO", 1), ("WARNING", 1)],
                )

    def test_input_is_iterated_only_once(self):
        class SinglePass:
            def __init__(self):
                self.iterated = False

            def __iter__(self):
                if self.iterated:
                    raise AssertionError("Input iterated twice")
                self.iterated = True
                return iter(["t|INFO|one", "t|warn|two"])

        for implementation in IMPLEMENTATIONS:
            with self.subTest(implementation=implementation.__name__):
                self.assertEqual(
                    implementation.summarize(SinglePass()),
                    {"INFO": 1, "WARNING": 1},
                )

    def test_generators_are_consumed(self):
        for implementation in IMPLEMENTATIONS:
            with self.subTest(implementation=implementation.__name__):
                lines = (line for line in ["t|INFO|one", "t|INFO|two"])
                self.assertEqual(implementation.summarize(lines), {"INFO": 2})
                self.assertEqual(list(lines), [])

    def test_malformed_nonblank_records_raise_value_error(self):
        for implementation in IMPLEMENTATIONS:
            for malformed in ("broken", "t|INFO", " \tbroken\r\n"):
                with self.subTest(
                    implementation=implementation.__name__, record=malformed
                ):
                    with self.assertRaises(ValueError):
                        implementation.summarize(["t|INFO|first", malformed])

    def test_iteration_failure_is_not_swallowed(self):
        def interrupted():
            yield "t|INFO|first"
            raise RuntimeError("stream interrupted")

        for implementation in IMPLEMENTATIONS:
            with self.subTest(implementation=implementation.__name__):
                with self.assertRaisesRegex(RuntimeError, "^stream interrupted$"):
                    implementation.summarize(interrupted())

    def test_iteration_stops_at_the_first_malformed_record(self):
        for implementation in IMPLEMENTATIONS:
            with self.subTest(implementation=implementation.__name__):
                lines = iter(["t|INFO|first", "broken", "t|WARN|unread"])
                with self.assertRaises(ValueError):
                    implementation.summarize(lines)
                self.assertEqual(list(lines), ["t|WARN|unread"])


class InternalApiContractTests(unittest.TestCase):
    def test_parser_preserves_message_content_and_only_removes_line_endings(self):
        expected = (" raw timestamp ", " warn ", " message | with pipes  ")
        line = " raw timestamp | warn | message | with pipes  \r\n"
        self.assertEqual(event_api.parse_record(line), expected)
        self.assertEqual(legacy_api.parse_line(line), expected)

    def test_normalization_has_explicit_expected_values(self):
        for value, expected in (
            ("warn", "WARNING"),
            (" err ", "ERROR"),
            ("warning", "WARNING"),
            (" notice ", "NOTICE"),
            ("", ""),
        ):
            with self.subTest(value=value):
                self.assertEqual(event_api.normalize_severity(value), expected)
                self.assertEqual(legacy_api.normalize_level(value), expected)

    def test_legacy_and_replacement_parser_exceptions_match(self):
        for line in ("broken", "t|INFO"):
            with self.subTest(line=line):
                with self.assertRaises(ValueError) as legacy:
                    legacy_api.parse_line(line)
                with self.assertRaises(ValueError) as replacement:
                    event_api.parse_record(line)
                self.assertEqual(str(legacy.exception), str(replacement.exception))


if __name__ == "__main__":
    unittest.main()
