"""Manage the API entrypoints"""

import uuid  # noqa: D100
from typing import TYPE_CHECKING, NoReturn
from uuid import UUID

from msfwk import database
from msfwk.request import HttpClient
from msfwk.utils.logging import get_logger
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from post.constants import DISCOURSE_POST_CATEGORY_UUID
from post.db_utils import (
    create_discussion,
    create_post_in_database,
    get_or_create_discourse_category,
    get_topic_info_from_discourse,
)

from .interfaces import (
    BasicPost,
    PostCreationData,
    PostDatabaseClass,
)
from .models.exceptions import (
    DiscussionCommunicationError,
    FailedToGetCurrentUserRolesError,
    PostCountError,
    PostCreationDatabaseError,
    PostCreationError,
    PostDeletionError,
    PostRetrievalError,
    RepositoryCreationError,
    TopicCreationError,
    UserNotLoggedInError,
)

logger = get_logger("application")

# HTTP Status codes
HTTP_STATUS_UNAUTHORIZED = 401
HTTP_STATUS_OK = 200

###############
#   Post
###############


async def create_post(post_creation_data: PostCreationData) -> PostDatabaseClass:
    """Creates a new post with participants"""
    try:
        async with (
            database.get_schema().get_async_session() as db_session,
            db_session.begin()
        ):
            post_id = uuid.uuid4()
            topic_id = await create_discussion(post_id, post_creation_data)
            logger.debug("topic_id: %s", topic_id)
            post = await create_post_in_database(post_creation_data, str(post_id), str(topic_id), db_session)

    except RepositoryCreationError as rce:
        message = "Failed to create repository post in storage service"
        logger.exception(message, exc_info=rce)
        raise PostCreationError(str(rce)) from rce
    except PostCreationDatabaseError as gcde:
        message = "Failed to create post because the name is not unique"
        logger.exception(message)
        raise PostCreationError(message) from gcde
    except DiscussionCommunicationError as dce:
        message = "Failed to create discussion for post"
        logger.exception(message, exc_info=dce)
        raise PostCreationError(message) from dce
    except SQLAlchemyError as sae:
        message = "Failed to create record in database"
        logger.exception(message)
        raise PostCreationError(message) from sae
    return post


async def complete_post_list_from_discourse(post_list: list[BasicPost]) -> None:
    """Complete post list with additional information from discourse.

    Args:
        post_list: List of posts to complete with discourse information
    """
    logger.debug("Fetching additional info from discourse...")
    discourse_info = await get_or_create_discourse_category(uuid.UUID(DISCOURSE_POST_CATEGORY_UUID))
    logger.debug("Crossing data from database with discourse...")
    for post in post_list:
        for topic in discourse_info.topics:
            if post.topicId == topic["id"]:
                post.reply_count = topic["posts_count"] - 1  # to account for the first post being the OP


async def complete_single_post_from_discourse(post: BasicPost) -> None:
    """Complete a single post with additional information from discourse.

    Args:
        post: Post to complete with discourse information
    """
    logger.debug("Fetching additional info from discourse...")
    topic_info = await get_topic_info_from_discourse(post.topicId)
    logger.debug("Crossing data from database with discourse...")
    post.replies = topic_info.posts
    del post.replies[0]
    post.reply_count = len(post.replies)


async def get_posts_from_database(categories: list[int] | None = None) -> list[BasicPost]:
    """Retrieves a list of posts from the database, including participant information
    if the current user is the owner of the post.

    Returns
        list[BasicPost]: A list of BasicPost objects representing posts with their participants.
    """
    db_session: AsyncSession
    try:
        # Access tables from the "collaborative" schema
        posts_table = database.get_schema("collaborative").tables["Posts"]
        categories_table = database.get_schema("collaborative").tables["Categories"]

        async with database.get_schema("collaborative").get_async_session() as db_session:
            logger.debug("Retrieving posts with participants from database")

            statement = select(
                posts_table,
                categories_table.c.name.label("category_name"),
            ).outerjoin(categories_table, categories_table.c.id == posts_table.c.categoryId)

            if categories is not None:
                statement = statement.where(posts_table.c.categoryId.in_(categories))

            posts_result = await db_session.execute(statement)
            rows = posts_result if isinstance(posts_result, list) else posts_result.all()

            return [BasicPost.from_record(row) for row in rows]

    except SQLAlchemyError as sae:
        message = "Failed to retrieve posts from database"
        logger.exception(message)
        raise PostRetrievalError(message) from sae


async def get_post(post_id: UUID) -> BasicPost:
    """Retrieves a post along with its participants using the post_id.

    Args:
        post_id (UUID): The unique ID of the post to retrieve.

    Returns:
        BasicPost: The post object with participant information.

    Raises:
        PostNotFoundError: If no post is found with the given ID.
        PostRetrievalError: If there's an error retrieving the post.
    """
    try:
        async with database.get_schema().get_async_session() as db_session:
            post_table = database.get_schema().tables["Posts"]
            category_table = database.get_schema().tables["Categories"]

            # Query the database for the post
            query = (
                select(post_table, category_table.c.name.label("category_name"))
                .join(category_table, post_table.c.categoryId == category_table.c.id)
                .filter(post_table.c.id == post_id)
            )

            result = await db_session.execute(query)
            post_data = result.fetchone()

            if not post_data:
                message = f"Post with ID {post_id} not found."
                logger.error(message)
                raise PostRetrievalError(message)

            return BasicPost.from_record(post_data)

    except SQLAlchemyError as sae:
        message = "Failed to retrieve post or participants from the database."
        logger.exception(message)
        raise PostRetrievalError(message) from sae


async def delete_post_from_db_and_discourse(post_id: UUID) -> None:
    """Delete a post and its participants from the database.

    Args:
        post_id (UUID): The unique identifier of the post to delete.

    Raises:
        PostDeletionError: If the deletion operation fails.
    """
    try:
        async with database.get_schema("collaborative").get_async_session() as db_session:
            # Access the required tables
            posts_table = database.get_schema("collaborative").tables["Posts"]
            discourses_table = database.get_schema("collaborative").tables["Discourses"]

            # Delete the post itself
            delete_post_stmt = posts_table.delete().where(posts_table.c.id == post_id)
            result = await db_session.execute(delete_post_stmt)

            # Delete discourse associated with the asset
            delete_discourse_stmt = discourses_table.delete().where(discourses_table.c.assetId == post_id)
            await db_session.execute(delete_discourse_stmt)

            # Check if the post deletion succeeded
            if result.rowcount == 0:
                msg = f"Post {post_id} not found or already deleted."
                raise PostDeletionError(msg)

            await db_session.commit()

    except SQLAlchemyError as sae:
        message = "Failed to delete post from database."
        logger.exception(message)
        raise PostDeletionError(message) from sae


async def get_current_user_roles() -> list[str]:
    """Get the current user's roles from the auth service.

    Returns:
        list[str]: List of roles assigned to the current user
    Raises:
        UserNotLoggedInError: If the user is not logged in
        FailedToGetCurrentUserRolesError: If there's an error retrieving the roles
    """
    def _handle_unauthorized() -> NoReturn:
        logger.error(unauthorized_msg)
        raise UserNotLoggedInError(unauthorized_msg)

    logger.debug("Getting current user roles")
    url = "/profile"
    error_msg = "Failed to get current user roles"
    unauthorized_msg = "User is not logged in"

    try:
        http_client = HttpClient()
        async with (
            http_client.get_service_session("auth") as session,
            session.get(url) as response,
        ):
            if response.status == HTTP_STATUS_UNAUTHORIZED:
                _handle_unauthorized()
            if response.status == HTTP_STATUS_OK:
                logger.debug("User is logged in")
                response_json = await response.json()
                return response_json["data"]["roles"]
    except Exception as e:
        logger.exception(error_msg)
        raise FailedToGetCurrentUserRolesError(error_msg) from e


async def get_user_post_count(user_id: str) -> int:
    """Get the total number of posts created by a user.

    Args:
        user_id (str): The ID of the user to count posts for.

    Returns:
        int: The total number of posts created by the user.

    Raises:
        PostRetrievalError: If there is an issue retrieving the post count from the database.
    """
    try:
        async with database.get_schema("collaborative").get_async_session() as db_session:
            posts_table = database.get_schema("collaborative").tables["Posts"]

            # Count posts for the given user
            statement = select(func.count()).select_from(posts_table).where(posts_table.c.despUserId == user_id)
            result = await db_session.execute(statement)
            count = result.scalar()

            return count if count is not None else 0

    except SQLAlchemyError as sae:
        message = "Failed to retrieve post count from database"
        logger.exception(message)
        raise PostCountError(message) from sae
