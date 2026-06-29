"""CLI entry point for insight-blueprint."""

import sys
from pathlib import Path

import click
from click.core import ParameterSource

from insight_blueprint.server import mcp
from insight_blueprint.storage.project import init_project


def _resolve_project(project: str | None) -> Path:
    """Resolve and validate the project path."""
    project_path = Path(project).resolve() if project else Path.cwd()
    if not project_path.exists():
        raise click.ClickException(
            f"Project path does not exist: {project_path}\n"
            "Please create the directory first or specify a valid path."
        )
    return project_path


def _wire_registry(project_path: Path) -> None:
    """Wire services into the centralized registry."""
    import insight_blueprint._registry as registry
    from insight_blueprint.core.catalog import CatalogService
    from insight_blueprint.core.designs import DesignService
    from insight_blueprint.core.reviews import ReviewService
    from insight_blueprint.core.rules import RulesService

    registry.design_service = DesignService(project_path)

    registry.catalog_service = CatalogService(project_path)
    registry.catalog_service.rebuild_index()

    registry.review_service = ReviewService(project_path, registry.design_service)
    db_path = project_path / ".insight" / "catalog.db"
    registry.rules_service = RulesService(
        project_path, registry.catalog_service, registry.design_service, db_path
    )


def _start_stdio_mode() -> None:
    """Start MCP server over stdio (default)."""
    mcp.run()


def _start_headless_mode(host: str, port: int) -> None:
    """Start headless mode: MCP server over HTTP/SSE."""
    print(f"MCP SSE: http://{host}:{port}/mcp/sse", file=sys.stderr)
    mcp.run(transport="sse", host=host, port=port)


@click.group(invoke_without_command=True)
@click.version_option(package_name="insight-blueprint")
@click.option(
    "--project",
    default=None,
    help="Path to the analysis project directory (default: current directory)",
)
@click.option(
    "--mode",
    type=click.Choice(["stdio", "headless"]),
    default="stdio",
    help="Startup mode: stdio (MCP over stdio, default), headless (MCP over HTTP/SSE)",
)
@click.option(
    "--host",
    type=str,
    default="0.0.0.0",
    help="Bind address for headless mode (default: 0.0.0.0)",
)
@click.option(
    "--port",
    type=int,
    default=4000,
    help="Listen port for headless mode (default: 4000)",
)
@click.pass_context
def main(
    ctx: click.Context,
    project: str | None,
    mode: str,
    host: str,
    port: int,
) -> None:
    """Start the insight-blueprint MCP server for analysis design management."""
    ctx.ensure_object(dict)
    ctx.obj["project"] = project

    # If a subcommand was invoked, skip the default server startup
    if ctx.invoked_subcommand is not None:
        return

    project_path = _resolve_project(project)
    init_project(project_path)
    _wire_registry(project_path)

    if mode == "stdio":
        # --host/--port are only meaningful in headless mode
        if (
            ctx.get_parameter_source("host") == ParameterSource.COMMANDLINE
            or ctx.get_parameter_source("port") == ParameterSource.COMMANDLINE
        ):
            click.echo("Warning: --host/--port are ignored in stdio mode", err=True)
        _start_stdio_mode()
    elif mode == "headless":
        _start_headless_mode(host, port)
