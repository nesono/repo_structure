# pylint: disable=import-error
# pylint: disable=broad-exception-caught
# pylint: disable=no-value-for-parameter

"""Ensure clean repository structure for your projects."""
import sys
import time

import click

from .repo_structure_enforcement import fail_if_invalid_repo_structure, Flags
from .repo_structure_config import Configuration


@click.command()
@click.option("--repo-root", "-r", required=True, type=click.Path(exists=True))
@click.option("--config-path", "-c", required=True, type=click.Path(exists=True))
@click.option("--follow-symlinks", "-L", is_flag=True, default=False)
@click.option("--include-hidden", "-H", is_flag=True, default=True)
@click.option("--verbose", "-v", is_flag=True, default=False)
def main(
    repo_root: str,
    config_path: str,
    follow_symlinks: bool,
    include_hidden: bool,
    verbose: bool,
) -> None:
    """Ensure clean repository structure for your projects."""
    click.echo("Repo-Structure started, parsing parsing config and repo")
    flags = Flags()
    flags.follow_symlinks = follow_symlinks
    flags.include_hidden = include_hidden
    flags.verbose = verbose

    # record time how long the scanning takes
    start_time = time.time()
    successful = True
    try:
        fail_if_invalid_repo_structure(
            repo_root,
            Configuration(config_path, False, None, flags.verbose),
            flags,
        )
        click.echo("Your Repo-structure is compliant")
    except Exception as err:
        click.echo(err, err=True)
        successful = False
    duration = time.time() - start_time
    if verbose:
        click.echo(f"Repo-Structure scan finished in {duration:.{3}f} seconds")
    if not successful:
        sys.exit(1)


# The following main check is very hard to get into unit
# testing and as long as it contains so little code, we'll skip it.
if __name__ == "__main__":  # pragma: no cover
    main()
