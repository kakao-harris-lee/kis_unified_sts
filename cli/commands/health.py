"""Health-check CLI command."""

from __future__ import annotations

import sys

import click

from cli.commands.common import DEFAULT_DASHBOARD_URL

# =============================================================================
# Health Commands
# =============================================================================


@click.command("health")
@click.option(
    "--url",
    "-u",
    default=DEFAULT_DASHBOARD_URL,
    help="Dashboard API URL",
)
def health(url: str):
    """시스템 헬스 체크

    \b
    Example:
        sts health
        sts health --url http://localhost:5081
    """
    try:
        import httpx
    except ImportError:
        click.echo("Error: httpx not installed (pip install httpx)", err=True)
        sys.exit(1)

    try:
        click.echo(f"Checking health: {url}")

        # Basic health
        response = httpx.get(f"{url}/health", timeout=5.0)
        if response.status_code == 200:
            data = response.json()
            click.echo("Health Check: ✓")
            click.echo(f"  Status: {data.get('status', 'unknown')}")
            click.echo(f"  Version: {data.get('version', 'unknown')}")
        else:
            click.echo(f"Health Check: ✗ ({response.status_code})")

        # Readiness: the dashboard exposes a single /health (no separate
        # /health/ready); reuse it as the readiness signal.
        try:
            response = httpx.get(f"{url}/health", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                click.echo("Readiness: ✓")
                components = data.get("components", {})
                for name, status in components.items():
                    icon = "✓" if status else "✗"
                    click.echo(f"  {name}: {icon}")
            elif response.status_code == 404:
                click.echo("Readiness: N/A (endpoint not available)")
            else:
                click.echo(f"Readiness: ✗ ({response.status_code})")
        except httpx.HTTPError:
            click.echo("Readiness: N/A")

    except httpx.ConnectError:
        click.echo("Health Check: ✗ (Connection refused)")
        click.echo(
            "Note: Start API server with 'uvicorn services.dashboard.app:create_app --factory'"
        )
