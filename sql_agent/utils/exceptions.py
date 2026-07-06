"""Custom exception hierarchy for clear, typed error handling across layers."""


class SQLAgentError(Exception):
    """Base class for all application-specific errors."""


class NoDatabaseError(SQLAgentError):
    """Raised when an operation needs a database but none has been built yet."""


class CSVConversionError(SQLAgentError):
    """Raised when CSV -> SQLite conversion fails."""


class SchemaInspectionError(SQLAgentError):
    """Raised when the schema cannot be introspected."""


class SQLGenerationError(SQLAgentError):
    """Raised when the LLM fails to produce usable SQL after all retries."""


class SQLExecutionError(SQLAgentError):
    """Raised when a generated SQL statement fails to execute."""


class IrrelevantQuestionError(SQLAgentError):
    """Raised (and caught internally) when a question cannot be answered
    from the available database."""


class UnsafeSQLError(SQLAgentError):
    """Raised when generated SQL attempts a non-read-only operation."""
