class EmailMcpError(Exception):
    """Base error whose message is safe to return through MCP."""


class ConfigurationError(EmailMcpError):
    pass


class UnsupportedBackendError(EmailMcpError):
    """The requested local backend cannot run on this machine."""


class BackendError(EmailMcpError):
    pass


class PolicyError(EmailMcpError):
    pass


class QueryError(EmailMcpError):
    pass
