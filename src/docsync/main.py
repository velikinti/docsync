"""CLI entry point for docsync."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List, Optional

import click
import structlog
from dotenv import load_dotenv

log = structlog.get_logger()

from docsync.config import load_config
from docsync.confluence_client import ConfluenceClient
from docsync.github_client import GitHubClient
from docsync.space_router import SpaceRouter
import json as _json

from docsync.sync import SyncEngine, SyncReport, SyncStatus

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)


@click.group()
@click.option("--env-file", default=".env", show_default=True, help="Path to .env file")
@click.pass_context
def cli(ctx: click.Context, env_file: str) -> None:
    """docsync — sync GitHub markdown docs to Confluence."""
    env_path = Path(env_file)
    if env_path.exists():
        load_dotenv(env_path, override=False)


@cli.command()
@click.option("--config", default=".docsync.yml", show_default=True, help="Path to .docsync.yml")
@click.option("--dry-run", is_flag=True, default=False, help="Preview without writing to Confluence")
@click.option("--owner", envvar="GITHUB_REPOSITORY_OWNER", required=True, help="GitHub owner/org")
@click.option("--repo", envvar="GITHUB_REPOSITORY_NAME", required=True, help="GitHub repo name")
@click.option("--sha", envvar="GITHUB_SHA", required=True, help="Commit SHA to sync")
@click.option(
    "--spaces",
    default=None,
    help="Comma-separated Confluence space keys to restrict sync (overrides config)",
)
@click.option(
    "--continue-on-error",
    is_flag=True,
    default=False,
    help="Skip failing spaces instead of aborting the run",
)
@click.option(
    "--output-format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
    help="Summary output format after sync: table (default) or json",
)
def sync(
    config: str,
    dry_run: bool,
    owner: str,
    repo: str,
    sha: str,
    spaces: Optional[str],
    continue_on_error: bool,
    output_format: str,
) -> None:
    """Sync changed markdown files from a GitHub commit to Confluence."""
    # Validate --spaces before loading config (RISK-09)
    active_spaces: Optional[List[str]] = None
    if spaces is not None:
        parsed = [s.strip() for s in spaces.split(",") if s.strip()]
        if not parsed:
            raise click.BadParameter("--spaces must contain at least one non-empty space key")
        active_spaces = parsed

    try:
        cfg = load_config(config)
    except (FileNotFoundError, ValueError) as exc:
        click.echo(f"[docsync] Config error: {exc}", err=True)
        sys.exit(1)

    if dry_run:
        cfg = cfg.model_copy(update={"dry_run": True})

    github = GitHubClient(
        token=os.environ.get("GITHUB_TOKEN"),
        batch_size=cfg.batch_size,
    )
    confluence = ConfluenceClient(
        base_url=cfg.confluence_base_url,
        user=cfg.confluence_user,
        token=cfg.confluence_token,
    )

    router = SpaceRouter(cfg.space_mappings)
    resolved = cfg.resolve_active_spaces(cli_override=active_spaces)
    engine = SyncEngine(config=cfg, github=github, confluence=confluence, space_router=router)

    click.echo(f"[docsync] Syncing commit {sha[:8]} ({owner}/{repo})")
    if dry_run:
        click.echo("[docsync] DRY RUN — no writes to Confluence")
    if spaces:
        click.echo(f"[docsync] Space filter: {', '.join(resolved)}")

    try:
        report = engine.run(
            owner=owner,
            repo=repo,
            commit_sha=sha,
            active_spaces=resolved,
            continue_on_error=continue_on_error,
        )
    except RuntimeError as exc:
        click.echo(f"[docsync] Pre-flight error: {exc}", err=True)
        sys.exit(1)

    report.log_jsonlines()
    report.write_github_step_summary()

    _print_summary(report, dry_run, output_format)

    if report.error_count > 0:
        sys.exit(1)


def _print_summary(report: SyncReport, dry_run: bool, output_format: str) -> None:
    """Print the sync summary in the requested format."""
    if output_format == "json":
        print(_json.dumps(report.summary_dict()), flush=True)
        return
    label = "DRY RUN SUMMARY" if dry_run else "SUMMARY"
    log.info(
        label,
        created=report.created_count,
        updated=report.updated_count,
        archived=report.archived_count,
        skipped=report.skipped_count,
        errors=report.error_count,
        elapsed_seconds=round(report.elapsed_seconds, 2),
    )
    click.echo(f"\n[docsync] {'DRY RUN ' if dry_run else ''}SUMMARY")
    click.echo(f"  Created:  {report.created_count}")
    click.echo(f"  Updated:  {report.updated_count}")
    click.echo(f"  Archived: {report.archived_count}")
    click.echo(f"  Skipped:  {report.skipped_count}")
    click.echo(f"  Errors:   {report.error_count}")
    click.echo(f"  Elapsed:  {report.elapsed_seconds:.2f}s")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
