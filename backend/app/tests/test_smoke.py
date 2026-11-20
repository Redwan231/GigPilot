"""Scaffold smoke test (P0-6): proves the test harness runs and the app
package imports. Real tests arrive with their tasks in Phase 1+."""

import app


def test_app_package_imports() -> None:
    assert app is not None
