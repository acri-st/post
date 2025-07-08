"""exceptions.py"""  # noqa: INP001

from msfwk.schema.exceptions import SchemaError


class PostCreationError(Exception):
    """Raised when something wrong happens during the creation of the post"""


class PostCreationDatabaseError(Exception):
    """Raised when enable to insert in database during the creation of the post"""


class RepositoryRegisterError(SchemaError):
    """Raised when something wrong happens during the register of a repository"""


class PostRetrievalError(Exception):
    """Raised when something wrong happens during the retrieval of the post"""


class PostJoinError(Exception):
    """Raised when something wrong happens during the retrieval of the post"""


class PostPermissionError(Exception):
    """Raised when something wrong happens during the retrieval of the post"""


class PostDeletionError(Exception):
    """Raised when something wrong happens during the deletion of the post"""


class RepositoryDeletionError(Exception):
    """Exception raised when repository deletion fails"""


class RepositoryCreationError(Exception):
    """Exception raised when repository creation fails"""


class DiscussionCommunicationError(Exception):
    """Exception raised when discourse creation fails"""


class TopicCreationError(Exception):
    """Exception raised when topic creation fails"""

class UnauthorizedError(Exception):
    """Exception raised when user is not authorized"""

class UserNotLoggedInError(Exception):
    """Exception raised when user is not logged in"""

class FailedToGetCurrentUserRolesError(Exception):
    """Exception raised when failed to get current user roles"""

class PostCountError(Exception):
    """Exception raised when failed to get post count"""
