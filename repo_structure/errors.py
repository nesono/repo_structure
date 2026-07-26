"""Exceptions raised by repo_structure."""


class ConfigurationParseError(Exception):
    """Raised when the configuration file is invalid."""


class StructureRuleError(Exception):
    """Raised when the structure rules are invalid."""


class TemplateError(Exception):
    """Raised when a template is invalid."""
