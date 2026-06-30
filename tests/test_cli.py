"""Tests for CLI entry point."""

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from insight_blueprint.cli import main


def test_cli_nonexistent_project_exits_with_error() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--project", "/nonexistent/path/xyz"])
    assert result.exit_code != 0
    assert "does not exist" in result.output or "Error" in result.output


def test_cli_default_project_uses_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--project omitted: uses current working directory."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    import insight_blueprint.server as server_module

    with patch.object(server_module.mcp, "run"):
        result = runner.invoke(main, [])
    assert result.exit_code == 0
    assert (tmp_path / ".insight").exists()


# ---------------------------------------------------------------------------
# TestCliModeDispatch: --mode routes to the correct startup function
# ---------------------------------------------------------------------------


class TestCliModeDispatch:
    """Test --mode dispatch routes to the correct startup function."""

    @patch("insight_blueprint.cli._start_stdio_mode")
    @patch("insight_blueprint.cli._wire_registry")
    @patch("insight_blueprint.cli.init_project")
    def test_default_mode_is_stdio(
        self, mock_init: object, mock_wire: object, mock_stdio: object, tmp_path: Path
    ) -> None:
        """No --mode flag defaults to stdio mode."""
        runner = CliRunner()
        result = runner.invoke(main, ["--project", str(tmp_path)])
        assert result.exit_code == 0
        assert mock_stdio.called  # type: ignore[attr-defined]

    @patch("insight_blueprint.cli._start_stdio_mode")
    @patch("insight_blueprint.cli._wire_registry")
    @patch("insight_blueprint.cli.init_project")
    def test_mode_stdio_explicit(
        self, mock_init: object, mock_wire: object, mock_stdio: object, tmp_path: Path
    ) -> None:
        """--mode stdio routes to _start_stdio_mode."""
        runner = CliRunner()
        result = runner.invoke(main, ["--project", str(tmp_path), "--mode", "stdio"])
        assert result.exit_code == 0
        assert mock_stdio.called  # type: ignore[attr-defined]

    @patch("insight_blueprint.cli._start_headless_mode")
    @patch("insight_blueprint.cli._wire_registry")
    @patch("insight_blueprint.cli.init_project")
    def test_mode_headless(
        self,
        mock_init: object,
        mock_wire: object,
        mock_headless: object,
        tmp_path: Path,
    ) -> None:
        """--mode headless routes to _start_headless_mode with host and port."""
        runner = CliRunner()
        result = runner.invoke(main, ["--project", str(tmp_path), "--mode", "headless"])
        assert result.exit_code == 0
        mock_headless.assert_called_once_with("0.0.0.0", 4000)  # type: ignore[attr-defined]

    def test_mode_invalid_value(self, tmp_path: Path) -> None:
        """--mode invalid produces a Click error."""
        runner = CliRunner()
        result = runner.invoke(main, ["--project", str(tmp_path), "--mode", "invalid"])
        assert result.exit_code != 0

    @patch("insight_blueprint.cli._start_headless_mode")
    @patch("insight_blueprint.cli._wire_registry")
    @patch("insight_blueprint.cli.init_project")
    def test_headless_host_port_defaults(
        self,
        mock_init: object,
        mock_wire: object,
        mock_headless: object,
        tmp_path: Path,
    ) -> None:
        """--mode headless without --host/--port uses defaults 0.0.0.0:4000."""
        runner = CliRunner()
        result = runner.invoke(main, ["--project", str(tmp_path), "--mode", "headless"])
        assert result.exit_code == 0
        args = mock_headless.call_args[0]  # type: ignore[attr-defined]
        assert args == ("0.0.0.0", 4000)

    @patch("insight_blueprint.cli._start_stdio_mode")
    @patch("insight_blueprint.cli._wire_registry")
    @patch("insight_blueprint.cli.init_project")
    def test_host_port_ignored_in_stdio_mode(
        self, mock_init: object, mock_wire: object, mock_stdio: object, tmp_path: Path
    ) -> None:
        """--host/--port in stdio mode emits warning, still starts stdio."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--project",
                str(tmp_path),
                "--mode",
                "stdio",
                "--host",
                "1.2.3.4",
                "--port",
                "9999",
            ],
        )
        assert result.exit_code == 0
        assert "ignored in stdio mode" in (result.output + (result.stderr or ""))
        assert mock_stdio.called  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# TestStdioModeStartup
# ---------------------------------------------------------------------------


class TestStdioModeStartup:
    """Verify _start_stdio_mode runs MCP over stdio."""

    @patch("insight_blueprint.cli.mcp")
    def test_stdio_mode_calls_mcp_run(self, mock_mcp: object) -> None:
        from insight_blueprint.cli import _start_stdio_mode

        _start_stdio_mode()
        mock_mcp.run.assert_called_once_with()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# TestHeadlessModeStartup
# ---------------------------------------------------------------------------


class TestHeadlessModeStartup:
    """Verify _start_headless_mode calls mcp.run with SSE transport."""

    @patch("insight_blueprint.cli.mcp")
    def test_headless_mode_calls_mcp_run_sse(self, mock_mcp: object) -> None:
        from insight_blueprint.cli import _start_headless_mode

        _start_headless_mode("0.0.0.0", 4000)
        mock_mcp.run.assert_called_once_with(  # type: ignore[attr-defined]
            transport="sse", host="0.0.0.0", port=4000
        )

    @patch("insight_blueprint.cli.mcp")
    def test_headless_mode_prints_sse_url(
        self, mock_mcp: object, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from insight_blueprint.cli import _start_headless_mode

        _start_headless_mode("0.0.0.0", 4000)
        err = capsys.readouterr().err
        assert "http://0.0.0.0:4000/mcp/sse" in err
