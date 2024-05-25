# pylint: disable=import-error
# pylint: disable=broad-exception-caught
# pylint: disable=no-value-for-parameter

"""Ensure clean repository structure for your projects."""

import click

from repo_structure_config import Configuration
from repo_structure_enforcement import fail_if_invalid_repo_structure


@click.command()
@click.option("--repo-root", "-r", required=True, type=click.Path(exists=True))
@click.option("--config-path", "-c", required=True, type=click.Path(exists=True))
@click.option("--follow-links", "-L", is_flag=True, default=False)
def main(repo_root: str, config_path: str, follow_links) -> None:
    """Ensure clean repository structure for your projects."""
    try:
        fail_if_invalid_repo_structure(
            repo_root, Configuration(config_path), follow_links
        )
    except Exception as err:
        click.echo("Error found during processing", err=True)
        click.echo(err, err=True)


if __name__ == "__main__":
    main()
