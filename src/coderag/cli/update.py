"""CLI commands for CodeRAG update management."""

from __future__ import annotations

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from coderag.updater.checker import UpdateChecker
from coderag.updater.config import UpdateConfig
from coderag.updater.installer import UpdateInstaller, UpdateStrategy

console = Console()


@click.group()
def update():
    """Manage CodeRAG updates."""


@update.command("check")
@click.option("--force", is_flag=True, help="Bypass cache and check now")
def check_update(force: bool) -> None:
    """Check for available updates."""
    config = UpdateConfig.load()
    checker = UpdateChecker(config)

    console.print("[bold]Checking for updates...[/bold]")
    info = checker.check(force=force)

    if info is None:
        console.print("[yellow]Could not check for updates (network error or no releases)[/yellow]")
        return

    table = Table(title="CodeRAG Version Info")
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("Current Version", info.current)
    table.add_row("Latest Version", info.latest)
    table.add_row(
        "Update Available",
        "✅ Yes" if info.update_available else "✓ Up to date",
    )
    if info.release_url:
        table.add_row("Release URL", info.release_url)
    if info.published_at:
        table.add_row("Published", info.published_at)
    console.print(table)

    if info.update_available:
        console.print(f"\n[bold green]Run 'coderag update install' to update to v{info.latest}[/bold green]")


@update.command("install")
@click.option(
    "--version",
    "target_version",
    default=None,
    help="Specific version to install",
)
@click.option(
    "--strategy",
    type=click.Choice(["pypi", "git", "auto"]),
    default="auto",
    help="Update strategy",
)
def install_update(target_version: str | None, strategy: str) -> None:
    """Install the latest update."""
    strat = None
    if strategy == "pypi":
        strat = UpdateStrategy.PYPI
    elif strategy == "git":
        strat = UpdateStrategy.GIT

    installer = UpdateInstaller(strategy=strat)
    console.print(f"[bold]Updating CodeRAG via {installer.strategy.value}...[/bold]")

    result = installer.install(target_version=target_version)

    if result.success:
        console.print(
            Panel(
                f"[green]✅ {result.message}[/green]",
                title="Update Successful",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel(
                f"[red]❌ {result.message}[/red]",
                title="Update Failed",
                border_style="red",
            )
        )


@update.command("config")
@click.option(
    "--auto-check/--no-auto-check",
    default=None,
    help="Enable/disable auto-check on launch",
)
@click.option(
    "--auto-install/--no-auto-install",
    default=None,
    help="Enable/disable auto-install",
)
@click.option(
    "--channel",
    type=click.Choice(["stable", "beta", "dev"]),
    default=None,
)
@click.option(
    "--interval",
    type=int,
    default=None,
    help="Check interval in seconds",
)
def config_update(
    auto_check: bool | None,
    auto_install: bool | None,
    channel: str | None,
    interval: int | None,
) -> None:
    """View or modify update configuration."""
    config = UpdateConfig.load()

    changed = False
    if auto_check is not None:
        config.auto_check = auto_check
        changed = True
    if auto_install is not None:
        config.auto_install = auto_install
        changed = True
    if channel is not None:
        config.channel = channel
        changed = True
    if interval is not None:
        config.check_interval = interval
        changed = True

    if changed:
        config.save()
        console.print("[green]Configuration updated.[/green]")

    table = Table(title="Update Configuration")
    table.add_column("Setting", style="bold")
    table.add_column("Value")
    table.add_row(
        "Auto Check",
        "✅ Enabled" if config.auto_check else "❌ Disabled",
    )
    table.add_row(
        "Auto Install",
        "✅ Enabled" if config.auto_install else "❌ Disabled",
    )
    table.add_row("Channel", config.channel)
    table.add_row(
        "Check Interval",
        f"{config.check_interval}s ({config.check_interval // 60}min)",
    )
    table.add_row("GitHub Repo", config.github_repo)
    console.print(table)


@update.command("clear-cache")
def clear_cache() -> None:
    """Clear the update check cache."""
    checker = UpdateChecker()
    checker.clear_cache()
    console.print("[green]Update cache cleared.[/green]")
