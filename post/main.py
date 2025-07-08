"""Manage the API entrypoints"""

from uuid import UUID

from msfwk.application import app, openapi_extra
from msfwk.context import current_user
from msfwk.models import BaseDespResponse, DespResponse
from msfwk.utils.logging import get_logger

from .constants import (
    FAILED_TO_CREATE_POST,
    FAILED_TO_CREATE_POST_NOT_UNIQUE_NAME,
    FAILED_TO_DELETE_POST,
    FAILED_TO_GET_POST,
)
from .handler import (
    complete_post_list_from_discourse,
    complete_single_post_from_discourse,
    create_post,
    delete_post_from_db_and_discourse,
    get_current_user_roles,
    get_post,
    get_posts_from_database,
    get_user_post_count,
)
from .interfaces import BasicPost, PostCreationData, PostsResponse
from .models.exceptions import (
    PostCountError,
    PostCreationError,
    PostDeletionError,
    PostPermissionError,
    PostRetrievalError,
    TopicCreationError,
)

logger = get_logger("application")

###############
#     VM
###############


@app.post(
    "/",
    summary="Create a post owned by the user",
    response_description="The status of the request",
    response_model=BaseDespResponse,
    tags=["post-management"],
    openapi_extra=openapi_extra(secured=True, roles=["user"]),
)
async def create_post_api(
    post_creation_data: PostCreationData,
) -> DespResponse:
    """_summary_

    Args:
        post_creation_data (PostCreationData): object representing the data needed to create a new post

    Returns:
        DespResponse: _description_
    """
    response = {}
    try:
        logger.info("Creating post %s ...", post_creation_data.title)
        if len(post_creation_data.title) == 0 or len(post_creation_data.title) > 64:
            msg = "Failed to create post: Post name is too long (64 characters max)"
            logger.error(msg)
            return DespResponse(data={}, error=msg, code=(FAILED_TO_CREATE_POST), http_status=400)
        post = await create_post(post_creation_data)
        response = post.model_dump()
        logger.debug("Post created")
        return DespResponse(data=response)
    except TopicCreationError as tce:
        logger.exception("Failed to create topic for post", exc_info=tce)
        return DespResponse(data={}, error=str(tce), code=FAILED_TO_CREATE_POST_NOT_UNIQUE_NAME, http_status=400)
    except PostCreationError as gce:
        return DespResponse(data=response, error=str(gce), code=FAILED_TO_CREATE_POST, http_status=500)


@app.get(
    "/",
    summary="Get posts, returns a list of posts",
    response_model=BaseDespResponse[list[BasicPost]],
    response_description="The list of posts",
    openapi_extra=openapi_extra(secured=False, roles=["user"]),
)
async def posts_retrieval(categories: str | None = None) -> DespResponse[list[BasicPost]]:
    """Retrieves all posts with their participants.

    This endpoint fetches a list of posts from the database, including their associated participants.
    Each post will have its relevant metadata and a list of participant details.

    Returns
        DespResponse[list[PostDatabaseClass]]: A response containing a list of posts and their participants.

    Raises
        PostRetrievalError: If there is an issue retrieving the posts from the database.
    """
    logger.debug("Handling post retrieval")

    try:
        post_list = await get_posts_from_database(
            None if categories is None else [int(item) for item in categories.split(",")]
        )
        await complete_post_list_from_discourse(post_list)
        return DespResponse(data=[p.to_json() for p in post_list])
    except PostRetrievalError as gre:
        logger.exception("failed to get post", exc_info=gre)
        return DespResponse(data={}, error="post retrieval failed", code=FAILED_TO_GET_POST)


@app.get(
    "/{post_id}",
    summary="Returns a post based on the given id",
    response_model=BaseDespResponse[PostsResponse],
    response_description="The id of the post in database",
    openapi_extra=openapi_extra(secured=False, roles=["user"]),
)
async def retrieve_post(post_id: UUID) -> DespResponse[PostsResponse]:
    """Return a specific post based on the given id

    Args:
        post_id (int): identified of the post

    Returns:
        DespResponse[PostsResponse]: Default DESP response with a data
    """
    logger.debug("Handling post retrieval")

    try:
        single_post = await get_post(post_id)
        await complete_single_post_from_discourse(single_post)
        return DespResponse(data=single_post.to_json())
    except PostRetrievalError as gre:
        logger.exception("failed to get post", exc_info=gre)
        return DespResponse(error="post retrieval failed", code=FAILED_TO_GET_POST, http_status=404)


@app.delete(
    "/{post_id}",
    summary="Delete a post.",
    response_description="The post has been deleted successfully.",
    openapi_extra=openapi_extra(secured=True, roles=["user"]),
)
async def delete_post(post_id: UUID) -> DespResponse:
    """Delete a post and its participants.

    Args:
        post_id (UUID): The unique identifier of the post.

    Returns:
        DespResponse: Response indicating success or failure.
    """
    try:
        # Fetch the post data
        post_data = await get_post(post_id)

        # Check if the current user is the owner or admin of the post
        current_user_roles = await get_current_user_roles()
        is_admin = "admin" in [role.lower() for role in current_user_roles]
        logger.debug("is_admin: %s", is_admin)

        if post_data.despUserId != current_user.get().id and not is_admin:
            message = "Only the post owner or admin can delete the post."
            logger.error(message)
            return DespResponse(
                data={},
                error=message,
                code=FAILED_TO_DELETE_POST,
                http_status=403,
            )

        # Perform the post deletion
        await delete_post_from_db_and_discourse(post_id)

        return DespResponse(data={"message": f"Post {post_id} deleted successfully."})

    except PostPermissionError as pe:
        message = str(pe)
        logger.exception(message)
        return DespResponse(data={}, error=message, code=FAILED_TO_DELETE_POST, http_status=403)
    except PostDeletionError as gde:
        message = str(gde)
        logger.exception(message)
        return DespResponse(data={}, error=message, code=FAILED_TO_DELETE_POST, http_status=400)
    except Exception as e:
        message = "An unexpected error occurred while deleting the post."
        logger.exception(message, exc_info=e)
        return DespResponse(data={}, error=message, code=FAILED_TO_DELETE_POST, http_status=500)


@app.get(
    "/count/{user_id}",
    summary="Get the total number of posts created by a user",
    response_model=BaseDespResponse[int],
    response_description="The total number of posts created by the user",
    openapi_extra=openapi_extra(secured=False, roles=["user"]),
)
async def get_user_post_count_api(user_id: str) -> DespResponse[int]:
    """Get the total number of posts created by a user.

    Args:
        user_id (str): The ID of the user to count posts for.

    Returns:
        DespResponse[int]: A response containing the total number of posts created by the user.

    Raises:
        PostRetrievalError: If there is an issue retrieving the post count from the database.
    """
    logger.debug("Handling post count retrieval for user %s", user_id)

    try:
        count = await get_user_post_count(user_id)
        return DespResponse(data=count)
    except PostCountError as gre:
        logger.exception("failed to get post count", exc_info=gre)
        return DespResponse(data=0, error="post count retrieval failed", code=FAILED_TO_GET_POST)
