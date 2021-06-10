def pytest_terminal_summary(terminalreporter, exitstatus, config):
    if "not slow" not in terminalreporter.config.option.markexpr:
        if "skipped" in terminalreporter.stats:
            num_skipped_tests = len(terminalreporter.stats["skipped"])
            if num_skipped_tests > 110:
                raise Exception(f"Too many skipped tests: {num_skipped_tests}")
