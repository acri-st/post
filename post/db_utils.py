"""Manage the API entrypoints"""

import uuid
from uuid import UUID

from aiohttp import ClientConnectorError
from msfwk import database
from msfwk.context import current_user
from msfwk.request import HttpClient
from msfwk.utils.logging import get_logger
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from post.constants import DISCOURSE_POST_CATEGORY_UUID

from .interfaces import (
    BasicPost,
    DiscussionResponse,
    PostCreationData,
    PostDatabaseClass,
    TopicResponse,
)
from .models.exceptions import (
    DiscussionCommunicationError,
    PostCreationDatabaseError,
    PostCreationError,
    RepositoryDeletionError,
    TopicCreationError,
)

logger = get_logger("application")


async def create_post_in_database(
    post_creation_data: PostCreationData, post_id: str, topic_id: str, db_session: AsyncSession
) -> PostDatabaseClass:
    """Creates a new post in the database"""
    try:
        logger.debug("Inserting post in database")
        user = current_user.get()
        if user is None:
            raise ValueError("Current user not defined !")
        post_database_updated: PostDatabaseClass = PostDatabaseClass(
            id=uuid.UUID(post_id),
            title=post_creation_data.title,
            despUserId=user.id,
            topicId=topic_id,
            categoryId=post_creation_data.category_id,
            message=post_creation_data.message,
        )
        statement = database.get_schema("collaborative").tables["Posts"].insert().values(**dict(post_database_updated))
        await db_session.execute(statement)
        # Do not commit here! Transaction is managed by the caller.
    except IntegrityError as ie:
        message = "Failed to create post because the name is not unique"
        logger.exception(message)
        raise PostCreationDatabaseError(message) from ie
    except SQLAlchemyError as sae:
        message = "Failed to create post in database"
        logger.exception(message)
        raise PostCreationError(message) from sae
    return post_database_updated


async def get_posts_list_from_rows(rows: list) -> list[BasicPost]:
    """Constructs a list of BasicPost objects from the raw database query rows.

    Args:
        rows (list): Raw database rows retrieved by the SQL query.
        current_user_id (str): The ID of the current user.

    Returns:
        list[BasicPost]: A list of BasicPost objects populated with post and participant data.
    """
    post_dict = {}  # Dictionary to consolidate post data
    for row in rows:
        post_id = str(row.id)
        # Add new post to the dictionary if it hasn't been processed
        if post_id not in post_dict:
            post_dict[post_id] = {
                "id": post_id,
                "title": row.title,
                "message": row.message,
                "despUserId": row.despUserId,
                "categoryId": row.categoryId,
                "topicId": row.topicId,
                "categoryName": row.category_name,
            }

    # Convert the dictionary values into BasicPost instances
    return [BasicPost(**post_info) for post_info in post_dict.values()]


async def delete_storage(resource_id: UUID) -> None:
    """Deletes the storage repository associated with an asset.

    Args:
        resource_id (int): The ID of the resource to delete.

    Raises:
        RepositoryDeletionError: If the repository cannot be deleted.
    """
    http_client = HttpClient()
    try:
        # Make a DELETE request to the storage service
        async with (
            http_client.get_service_session("storage") as session,
            session.delete(f"/repository/{resource_id}") as response,
        ):
            if response.status not in (200, 204):  # Assuming 200 or 204 indicate success
                message = f"Storage service responded with status {response.status}"
                error = await response.json()
                logger.error("Failed to delete repository for the resource  %s: %s", resource_id, error)
                raise RepositoryDeletionError(error)
            logger.info("Repository for resource  %s deleted successfully", resource_id)
    except ClientConnectorError as cce:
        message = "Failed to delete storage due to service unavailability"
        logger.exception(message, exc_info=cce)
        raise RepositoryDeletionError(message) from cce


async def create_discussion(post_id: UUID, post_data: PostCreationData) -> int:
    """Create a discussion for a post

    Args:
        post_id (UUID): Post uuid
        post_name (str): name of the post

    Returns:
        int: discourse id
    """
    logger.debug("creating discussion for post %s", post_id)
    await get_or_create_discourse_category(uuid.UUID(DISCOURSE_POST_CATEGORY_UUID))
    return await _create_post_topic(
        payload={"title": post_data.title, "text": post_data.message, "asset_id": DISCOURSE_POST_CATEGORY_UUID}
    )


async def get_or_create_discourse_category(category_id: UUID) -> DiscussionResponse:
    """
    Call the discussion module, creating a category if it does not exist yet
    """
    http_client = HttpClient()
    try:
        async with (
            http_client.get_service_session("discussion") as session,
            session.get(
                f"/discussion/{category_id}",
            ) as response,
        ):
            if response.status not in (200, 201):
                message = f"Discussion service answered {response.status}"
                error = await response.json()
                logger.error("Failed to create discussion %s, %s", response.status, error)
                raise DiscussionCommunicationError(error)

            logger.info("Discussion Created")
            response_content = await response.json()
            logger.info("Reponse from the discussion module: %s", response_content)
            return DiscussionResponse(**response_content["data"])
    except ClientConnectorError as cce:
        message = "Failed to create discourse due to service unavailability"
        logger.exception(message, exc_info=cce)
        raise DiscussionCommunicationError(message) from cce


async def get_topic_info_from_discourse(topic_id: int) -> TopicResponse:
    """
    Call the discussion module, creating a category if it does not exist yet
    """
    http_client = HttpClient()
    try:
        async with (
            http_client.get_service_session("discussion") as session,
            session.get(
                f"/topic/{topic_id}",
            ) as response,
        ):
            if response.status not in (200, 201):
                message = f"Discussion service answered {response.status}"
                error = await response.json()
                logger.error("Failed to fetch topic info status=%s, error=%s", response.status, error)
                raise DiscussionCommunicationError(error)

            response_content = await response.json()
            logger.info("Reponse from the discussion module: %s", response_content)
            return TopicResponse(**response_content["data"])
    except ClientConnectorError as cce:
        message = "Failed to call discussion-service due to service unavailability"
        logger.exception(message, exc_info=cce)
        raise DiscussionCommunicationError(message) from cce


async def _create_post_topic(payload: dict) -> int:
    http_client = HttpClient()
    # Call the search service to register the repository into gitlab
    try:
        async with (
            http_client.get_service_session("discussion") as session,
            session.post(
                "/topic",
                json=payload,
            ) as response,
        ):
            if response.status not in (200, 201):
                message = f"Topic service answered {response.status}"
                error = await response.json()
                logger.error("Failed to create topic %s, %s", response.status, error)
                raise TopicCreationError(error["error"]["message"])

            logger.info("Topic Created")
            response_content = await response.json()
            logger.info("Reponse from the topic: %s", response_content)
            return response_content["data"]["topic_id"]
    except ClientConnectorError as cce:
        message = "Failed to create topic due to service unavailability"
        logger.exception(message, exc_info=cce)
        raise DiscussionCommunicationError(message) from cce
