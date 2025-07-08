from fastapi.testclient import TestClient
from unittest.mock import MagicMock, Mock, AsyncMock, patch
import logging
import pytest
import aiohttp
from msfwk.utils.conftest import mock_read_config, mock_http_client, mock_user, mock_request
from .utils import fake_table, mock_database_class, is_valid_uuid
from sqlalchemy.engine.result import MappingResult
from msfwk.models import DespUser
from msfwk.utils.user import set_current_user
from .config import test_post_config


logger = logging.getLogger("test")

from fastapi.testclient import TestClient
from unittest.mock import MagicMock, Mock, AsyncMock, patch
import logging
import pytest
import aiohttp
from msfwk.utils.conftest import mock_read_config, mock_http_client, mock_user, mock_request
from .utils import fake_table, mock_database_class, is_valid_uuid
from sqlalchemy.engine.result import MappingResult
from msfwk.models import DespUser
from msfwk.utils.user import set_current_user
from .config import test_post_config
from types import SimpleNamespace  # For mocking attribute-based access

logger = logging.getLogger("test")

# Mock external microservice calls
def mock_microservice_calls(path: str = None, json=None):
    logger.debug("Request hooked %s %s", path, json)
    mock_response = MagicMock()
    mock_response.headers = {'Content-Type': 'application/json'}
    mock_response.status = 200

    if path.startswith("/discussion/"):
        logger.debug("Mocked JsonResponse %s", path)
        mock_response.json.return_value = {
            "data": {
                "id": "1",
                "name": "postdiscussion",
                "topics": [],
            }
        }

    async_mock = AsyncMock(return_value=mock_response)
    async_mock.__aenter__ = async_mock
    return async_mock

@pytest.mark.skip(reason="Have to mock the table Categories")
# @pytest.mark.component
def test_list_posts(mock_read_config, mock_http_client, mock_database_class):
    """Test for the list_posts endpoint."""
    from post.main import app

    # Mock the configuration and HTTP client
    mock_http_client.get = Mock(side_effect=mock_microservice_calls)
    mock_read_config.return_value = test_post_config

    # Mock database tables
    posts_data = [
        # Post with participants
        SimpleNamespace(
            id="2c81a431-af77-48fc-b7e9-198f4af8f8f4", 
            despUserId="9999", 
            name=" first post",
            description="We use this post for test",
            categoryId=1, 
            resourceId="fd7299d4-a750-498a-89e1-e9535cfe77ab", 
            discussionId=123,
            participant_user_id="tom",
            username="OTOM",
            participant_status="member"
        ),
        # Post without participants
        SimpleNamespace(
            id="bfc7fe75-74c7-42b6-aa93-c0cfd4f8f44b", 
            despUserId="no-robot", 
            name=" second post",
            description="This post is created without other members",
            categoryId=1, 
            resourceId="23dbd9c7-0560-48ad-8ac6-bf28d6bbd16d", 
            discussionId=123,
            participant_user_id=None,
            username=None,
            participant_status=None
        )
    ]
    
    # Mock database calls
    mock_database_class.tables = {
        "Posts": fake_table(
            "Posts",
            ["id", "despUserId", "name", "description", "categoryId", "resourceId", "discussionId"]
        ),
        "PostParticipants": fake_table(
            "PostParticipants",
            ["postId", "despUserId", "username", "status"]
        ),
    }

    # Mock the execute call to return the prepared rows
    async def mock_execute(query):
        return posts_data  # Return the mock data representing the result of the SQL query

    mock_database_class.get_async_session().execute.side_effect = mock_execute

    # Set the current user
    set_current_user(DespUser("9999", "Yves"))

    # Perform the test using the FastAPI test client
    with TestClient(app) as client:
        response = client.get("/")
        # Validate the response
        assert response.status_code == 200

        # Validate the response structure
        data = response.json()["data"]
        assert isinstance(data, list)

        for post in data:
            assert is_valid_uuid(post["id"]), f"id is an invalid UUID: {post['id']}"
            # assert "name" in post
            assert "despUserId" in post
            assert "name" in post
            assert "categoryId" in post
            assert "participants" in post
            assert isinstance(post["participants"], list)
