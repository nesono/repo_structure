"""Exceptions raised by repo_structure."""


class RepoStructureError(Exception):
    """Base class for every error repo_structure raises deliberately.

    Callers that only want to turn a broken configuration into a message --
    the CLI, most notably -- can catch this instead of enumerating the
    subclasses and missing one when a new kind is added.
    """


class ConfigurationParseError(RepoStructureError):
    """Raised when the configuration file is invalid."""


class StructureRuleError(RepoStructureError):
    """Raised when the structure rules are invalid."""


class TemplateError(RepoStructureError):
    """Raised when a template is invalid."""
