# pylint: disable=import-error
# pylint: disable=broad-exception-caught
# pylint: disable=no-value-for-parameter

"""Ensure clean repository structure for your projects."""
import sys
import time

import click

from .repo_structure_lib import Flags
from .repo_structure_full_scan import assert_full_repository_structure
from .repo_structure_diff_scan import assert_path
from .repo_structure_config import Configuration
from ._version import version


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
    version=f"v{version}",
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
    type=click.Path(exists=True),
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
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
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


# The following main check is very hard to get into unit
# testing and as long as it contains so little code, we'll skip it.
if __name__ == "__main__":  # pragma: no cover
    repo_structure()
