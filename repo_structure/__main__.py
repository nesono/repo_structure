# pylint: disable=import-error
# pylint: disable=broad-exception-caught
# pylint: disable=no-value-for-parameter

"""Ensure clean repository structure for your projects."""
import sys
import time
from pathlib import Path

import click

from .repo_structure_lib import Flags
from .repo_structure_full_scan import (
    assert_full_repository_structure,
    scan_full_repository,
)
from .repo_structure_diff_scan import assert_path
from .repo_structure_config import Configuration

try:
    from ._version import version as VERSION
except ModuleNotFoundError:  # pragma: no cover
    VERSION = "ersion unknown"


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
    click.echo("Repo-Structure started")
    flags = Flags()
    flags.follow_symlinks = follow_symlinks
    flags.include_hidden = include_hidden
    flags.verbose = verbose
    ctx.obj = flags


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
@click.pass_context
def full_scan(ctx: click.Context, repo_root: str, config_path: str) -> None:
    """Run a full scan on all files in the repository.

    This command is a sub command of repo_structure.
    Options:
        repo_root: The path to the repository root.
        config_path: The path to the configuration file.

    The full scan respects gitignore files and will run over all files it finds
    in the repository, no matter if they were added to git or not.

    Run this command to ensure that not only all files are allowed, but also
    that all files that are required are there.
    """
    click.echo("Running full scan")

    successful = True
    flags = ctx.obj

    start_time = time.time()

    try:
        config = Configuration(config_path, False, None, flags.verbose)
    except Exception as err:
        click.echo(err, err=True)
        successful = False
        sys.exit(1)

    try:
        assert_full_repository_structure(
            repo_root,
            config,
            flags,
        )
    except Exception as err:
        click.echo("Error: " + click.style(err, fg="red"), err=True)
        successful = False

    duration = time.time() - start_time
    if flags.verbose:
        click.echo(f"Full scan took {duration:.2f} seconds")

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
    successful = True

    try:
        config = Configuration(config_path, False, None, flags.verbose)
    except Exception as err:
        click.echo(err, err=True)
        successful = False
        sys.exit(1)

    for path in paths:
        if Path(path).is_absolute():
            err_msg = (
                f"'{path}' must not be absolute, but relative to the repository root"
            )
            click.echo("Error: " + click.style(err_msg, fg="red"), err=True)
            successful = False
            continue
        try:
            assert_path(
                config,
                path,
                flags,
            )
        except Exception as err:
            click.echo("Error: " + click.style(err, fg="red"), err=True)
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
@click.pass_context
def full_scan_warning(ctx: click.Context, repo_root: str, config_path: str) -> None:
    """Run a full scan and print warnings and errors without throwing.

    This behaves like full_scan, but uses scan_full_repository to aggregate
    issues (errors and warnings) and prints them for downstream consumption.
    """
    click.echo("Running full scan (non-throwing)")

    flags = ctx.obj
    start_time = time.time()

    try:
        config = Configuration(config_path, False, None, flags.verbose)
    except Exception as err:
        click.echo(err, err=True)
        sys.exit(1)

    # Call the non-throwing scan and print results
    errors, warnings = scan_full_repository(repo_root, config, flags)

    # Print warnings first
    if warnings:
        click.echo(click.style("Warnings:", fg="yellow"))
        for w in warnings:
            loc = f" [{w.path}]" if getattr(w, "path", None) else ""
            click.echo(click.style(f" - ({w.code}) {w.message}{loc}", fg="yellow"))

    # Then errors
    successful = True
    if errors:
        click.echo(click.style("Errors:", fg="red"))
        for e in errors:
            loc = f" [{e.path}]" if getattr(e, "path", None) else ""
            click.echo(click.style(f" - ({e.code}) {e.message}{loc}", fg="red"))
        successful = False

    duration = time.time() - start_time
    if flags.verbose:
        click.echo(f"Full scan (non-throwing) took {duration:.2f} seconds")

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


# The following main check is very hard to get into unit
# testing and as long as it contains so little code, we'll skip it.
if __name__ == "__main__":  # pragma: no cover
    repo_structure()
