# pylint: disable=import-error
# pylint: disable=broad-exception-caught
# pylint: disable=no-value-for-parameter

"""Ensure clean repository structure for your projects."""
import sys
import time

import click

from .repo_structure_enforcement import (
    assert_full_repository_structure,
    assert_path,
    Flags,
)
from .repo_structure_config import Configuration


@click.command()
@click.option(
    "--repo-root",
    "-r",
    required=True,
    type=click.Path(exists=True),
    help="The path to the repository root.",
)
@click.option(
    "--config-path",
    "-c",
    required=True,
    type=click.Path(exists=True),
    help="The path to the configuration file.",
)
@click.option(
    "--check-all",
    "-A",
    is_flag=True,
    default=False,
    help="Check all files in the repository. Overrides --path option.",
)
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
    version="v0.1.0",
    prog_name="Repo-Structure",
    message="%(prog)s %(version)s",
)
@click.argument(
    "paths",
    nargs=-1,
    type=click.Path(exists=True),
    required=False,
)
# the argument list of the following function is prescribed through the click API
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
def repo_structure_main(
    repo_root: str,
    config_path: str,
    check_all: bool,
    follow_symlinks: bool,
    include_hidden: bool,
    verbose: bool,
    paths: list[str],
) -> None:
    """Ensure clean repository structure for your projects."""
    click.echo("Repo-Structure started, parsing parsing config and repo")
    flags = Flags()
    flags.follow_symlinks = follow_symlinks
    flags.include_hidden = include_hidden
    flags.verbose = verbose

    start_time = time.time()
    successful = True

    try:
        config = Configuration(config_path, False, None, flags.verbose)
    except Exception as err:
        click.echo(err, err=True)
        successful = False
        sys.exit(1)

    if check_all:
        if len(paths) > 0:
            click.echo(
                click.style(
                    "Warning: You have specified both --check-all and a list of paths. "
                    "The list of paths will be ignored.\n",
                    fg="yellow",
                )
            )
        try:
            assert_full_repository_structure(
                repo_root,
                config,
                flags,
            )
        except Exception as err:
            click.echo("Error: " + click.style(err, fg="red"), err=True)
            successful = False
    else:
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

    duration = time.time() - start_time
    if verbose:
        click.echo(f"Repo-Structure scan finished in {duration:.{3}f} seconds")
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
    repo_structure_main()
