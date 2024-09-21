# pylint: disable=import-error
# pylint: disable=broad-exception-caught
# pylint: disable=no-value-for-parameter

"""Ensure clean repository structure for your projects."""

import click

from repo_structure_config import Configuration
from repo_structure_enforcement import fail_if_invalid_repo_structure, Flags


@click.command()
@click.option("--repo-root", "-r", required=True, type=click.Path(exists=True))
@click.option("--config-path", "-c", required=True, type=click.Path(exists=True))
@click.option("--follow-links", "-L", is_flag=True, default=False)
@click.option("--include-hidden", "-H", is_flag=True, default=False)
@click.option("--verbose", "-v", is_flag=True, default=False)
def main(
    repo_root: str,
    config_path: str,
    follow_links: bool,
    include_hidden: bool,
    verbose: bool,
) -> None:
    """Ensure clean repository structure for your projects."""
    click.echo("Repo-Structure started, parsing parsing config and repo")
    flags = Flags()
    flags.follow_links = follow_links
    flags.include_hidden = include_hidden
    flags.verbose = verbose

    try:
        fail_if_invalid_repo_structure(repo_root, Configuration(config_path), flags)
        click.echo("Your Repo-structure is compliant")
    except Exception as err:
        click.echo(err, err=True)


if __name__ == "__main__":
    main()
