"""Ensure clean repository structure for your projects."""

import sys
from typing import cast
from typing import Literal
import time
from pathlib import Path

import click

from .repo_structure_lib import ConfigurationParseError, Flags, ScanIssue
from .repo_structure_full_scan import (
    FullScanProcessor,
)
from .repo_structure_diff_scan import DiffScanProcessor
from .repo_structure_config import Configuration
from .repo_structure_report import generate_report, format_report

try:
    from ._version import version as VERSION
except ModuleNotFoundError:  # pragma: no cover
    VERSION = "version unknown"


@click.group()
@click.option(
    "--follow-symlinks",
    "-L",
    is_flag=True,
    default=False,
    help="Follow symlinks when scanning the repository.",
)
@click.option(
    "--include-hidden",
    "-H",
    is_flag=True,
    default=True,
    help="Include hidden files and directories, when scanning the repository.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Enable verbose messages for debugging and tracing.",
)
@click.version_option(
    version=f"v{VERSION}",
    prog_name="Repo-Structure",
    message="%(prog)s %(version)s",
)
@click.pass_context
def repo_structure(
    ctx: click.Context,
    follow_symlinks: bool,
    include_hidden: bool,
    verbose: bool,
) -> None:
    """Ensure clean repository structure for your projects."""
    flags = Flags()
    flags.follow_symlinks = follow_symlinks
    flags.include_hidden = include_hidden
    flags.verbose = verbose
    ctx.obj = flags


def _load_configuration(config_path: str, verbose: bool) -> Configuration:
    """Load and validate configuration from file."""
    try:
        return Configuration(config_path, False, None, verbose)
    except ConfigurationParseError as err:
        click.echo(err, err=True)
        sys.exit(1)


def _validate_directory_mapping(directory: str, config: Configuration) -> None:
    """Validate that directory mapping exists in configuration."""
    if directory not in config.directory_map:
        available_dirs = list(config.directory_map.keys())
        click.echo(
            click.style(
                f"Error: Directory mapping '{directory}' not found in configuration.",
                fg="red",
            )
            + f"\nAvailable directory mappings: {', '.join(available_dirs)}",
            err=True,
        )
        sys.exit(1)


def _perform_scan(
    repo_root: str, config: Configuration, flags: Flags, directory: str | None
) -> tuple[list[ScanIssue], list[ScanIssue]]:
    """Perform the actual scan operation."""
    if directory:
        directory = f'/{directory.strip("/")}/'
        _validate_directory_mapping(directory, config)
        processor = FullScanProcessor(repo_root, config, flags)
        errors = processor.scan_directory(directory)
        return errors, []

    processor = FullScanProcessor(repo_root, config, flags)
    return processor.scan()


def _print_scan_results(errors: list[ScanIssue], warnings: list[ScanIssue]) -> bool:
    """Print scan results and return success status."""
    successful = True

    # Print warnings first
    if warnings:
        click.echo(click.style("Warnings:", fg="yellow"))
        for w in warnings:
            loc = f" [{w.path}]" if getattr(w, "path", None) else ""
            click.echo(click.style(f" - ({w.code}) {w.message}{loc}", fg="yellow"))

    # Then errors
    if errors:
        click.echo(click.style("Errors:", fg="red"))
        for e in errors:
            loc = f" [{e.path}]" if getattr(e, "path", None) else ""
            click.echo(click.style(f" - ({e.code}) {e.message}{loc}", fg="red"))
        successful = False

    return successful


@repo_structure.command()
@click.option(
    "--repo-root",
    "-r",
    type=click.Path(exists=True, file_okay=False),
    help="The path to the repository root.",
    default=".",
    show_default=True,
)
@click.option(
    "--config-path",
    "-c",
    type=click.Path(exists=True),
    help="The path to the configuration file.",
    default="repo_structure.yaml",
    show_default=True,
)
@click.option(
    "--directory",
    "-d",
    help="Limit scan to a specific directory (e.g. '/', 'src/', 'tests/')",
    default=None,
)
@click.pass_context
def full_scan(
    ctx: click.Context, repo_root: str, config_path: str, directory: str | None
) -> None:
    """Run a full scan on all files in the repository.

    This command is a sub command of repo_structure.
    Options:
        repo_root: The path to the repository root.
        config_path: The path to the configuration file.
        directory: Optional directory mapping to scan specifically.

    The full scan respects gitignore files and will run over all files it finds
    in the repository, no matter if they were added to git or not.

    Run this command to ensure that not only all files are allowed, but also
    that all files that are required are there.

    Use --directory to scan only a specific directory mapping for faster,
    targeted analysis.
    """
    if directory:
        click.echo(f"Running full scan on directory mapping: {directory}")
    else:
        click.echo("Running full scan")

    flags = ctx.obj
    start_time = time.time()

    config = _load_configuration(config_path, flags.verbose)
    errors, warnings = _perform_scan(repo_root, config, flags, directory)
    successful = _print_scan_results(errors, warnings)

    duration = time.time() - start_time
    if flags.verbose:
        scan_type = f"Directory scan ({directory})" if directory else "Full scan"
        click.echo(f"{scan_type} took {duration:.2f} seconds")

    click.echo(
        "Checks have"
        + (
            click.style(" succeeded", fg="green")
            if successful
            else click.style(" FAILED", fg="red")
        )
    )

    if not successful:
        sys.exit(1)


@repo_structure.command()
@click.option(
    "--config-path",
    "-c",
    type=click.Path(exists=True),
    help="The path to the configuration file.",
    default="repo_structure.yaml",
    show_default=True,
)
@click.argument(
    "paths",
    nargs=-1,
    type=click.Path(),
    required=False,
)
@click.pass_context
def diff_scan(ctx: click.Context, config_path: str, paths: list[str]) -> None:
    """Run a check on a differential set of files.

    Options:
        config_path: The path to the configuration file.
    Arguments:
        paths: All files to check if allowed.

    Run this command when you want to make a fast check if all files from
    a change set are allowed in the repository.

    Note that this will not check if all files that are required are there.
    For that, please run the full-scan sub command instead.
    """
    click.echo("Running diff scan")
    flags = ctx.obj

    config = _load_configuration(config_path, flags.verbose)
    processor = DiffScanProcessor(config, flags)

    # Validate paths first
    valid_paths = []
    successful = True
    for path in paths:
        if Path(path).is_absolute():
            err_msg = (
                f"'{path}' must not be absolute, but relative to the repository root"
            )
            click.echo("Error: " + click.style(err_msg, fg="red"), err=True)
            successful = False
        else:
            valid_paths.append(path)

    # Check all valid paths efficiently
    issues = processor.check_paths(valid_paths)
    if issues:
        for issue in issues:
            loc = f" [{issue.path}]" if getattr(issue, "path", None) else ""
            click.echo(
                "Error: "
                + click.style(f"({issue.code}) {issue.message}{loc}", fg="red"),
                err=True,
            )
        successful = False

    click.echo(
        "Checks have"
        + (
            click.style(" succeeded", fg="green")
            if successful
            else click.style(" FAILED", fg="red")
        )
    )

    if not successful:
        sys.exit(1)


@repo_structure.command()
@click.option(
    "--repo-root",
    "-r",
    type=click.Path(exists=True, file_okay=False),
    help="The path to the repository root.",
    default=".",
    show_default=True,
)
@click.option(
    "--config-path",
    "-c",
    type=click.Path(exists=True),
    help="The path to the configuration file.",
    default="repo_structure.yaml",
    show_default=True,
)
@click.option(
    "--output_format",
    "-f",
    type=click.Choice(["text", "json", "markdown"]),
    help="Output format for the report.",
    default="text",
    show_default=True,
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file path. If not specified, prints to stdout.",
    default=None,
)
@click.pass_context
def report(
    ctx: click.Context,
    repo_root: str,
    config_path: str,
    output_format: str,
    output: str | None,
) -> None:
    """Generate a report of the configuration structure.

    This command analyzes the configuration file and generates a comprehensive
    report showing:
    - Repository information (name, branch, commit hash and date)
    - Directory mappings and their descriptions
    - Structure rules and their descriptions
    - Which rules are applied to which directories
    - Summary statistics

    The report can be generated in text, JSON, or Markdown format.
    """
    flags = ctx.obj

    config = _load_configuration(config_path, flags.verbose)
    report_data = generate_report(config, repo_root)

    formatted_report = format_report(
        report_data, cast(Literal["text", "json", "markdown"], output_format)
    )

    if output:
        try:
            with open(output, "w", encoding="utf-8") as f:
                f.write(formatted_report)
            click.echo(f"Report written to {output}")
        except IOError as e:
            click.echo(f"Error writing to file: {e}", err=True)
            sys.exit(1)
    else:
        click.echo(formatted_report)


# The following main check is very hard to get into unit
# testing and as long as it contains so little code, we'll skip it.
if __name__ == "__main__":  # pragma: no cover
    repo_structure()  # pylint: disable=no-value-for-parameter
