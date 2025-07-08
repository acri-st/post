from fastapi.testclient import TestClient
from unittest.mock import MagicMock, Mock, AsyncMock, patch
import pytest
import aiohttp
from msfwk.utils.conftest import mock_read_config, mock_http_client
from msfwk.models import DespUser
from msfwk.utils.user import set_current_user
from .utils import mock_database_class, is_valid_uuid, fake_table
from .config import test_post_config
from types import SimpleNamespace
from msfwk.utils.logging import get_logger
import datetime
import uuid

logger = get_logger("test")

# Helper functions to create mocks and test data
def create_mock_post(owner_id="1234", post_id=None):
    """Create a mock post with the given owner ID"""
    if post_id is None:
        post_id = str(uuid.uuid4())
        
    return SimpleNamespace(
        id=post_id,
        despUserId=owner_id,
        topicId=123,
        categoryId=1,
        title="Test Post Title",
        message="Test post message",
        categoryName="Test Category",
        created_at=datetime.datetime.now(),
        reply_count=0,
        replies=[],
        to_json=lambda: {
            "id": post_id,
            "despUserId": owner_id,
            "title": "Test Post Title"
        }
    )

def setup_database_mocks(mock_database_class, post_owner_id="1234"):
    """Set up database mocks for the tests"""
    # Mock database tables
    mock_database_class.tables = {
        "Posts": fake_table("Posts", ["id", "despUserId", "topicId", "categoryId", "name", "description"]),
        "Discourses": fake_table("Discourses", ["assetId"]),
        "Categories": fake_table("Categories", ["id", "name"])
    }
    
    # For collaborative schema
    schema_mock = MagicMock()
    schema_mock.tables = {
        "Posts": fake_table("Posts", ["id", "despUserId", "topicId", "categoryId", "name", "description"]),
        "Discourses": fake_table("Discourses", ["assetId"]),
        "Categories": fake_table("Categories", ["id", "name"])
    }
    schema_mock.get_async_session.return_value = mock_database_class.get_async_session()
    
    # Set up the execute result for database operations
    record_obj = SimpleNamespace(
        id="2c81a431-af77-48fc-b7e9-198f4af8f8f4",
        despUserId=post_owner_id,
        topicId=123,
        categoryId=1,
        title="Test Post Title",
        message="Test post message",
        category_name="Test Category",
        created_at=datetime.datetime.now()
    )
    
    execute_result = MagicMock()
    execute_result.fetchone.return_value = record_obj
    mock_database_class.get_async_session().execute.return_value = execute_result
    
    # Mock database session commit
    mock_database_class.get_async_session().commit = AsyncMock()
    
    return schema_mock

# Mock external microservice calls
def create_microservice_mock(is_admin=False):
    """Create a mock for microservice calls with appropriate roles"""
    def mock_microservice_calls(path: str = None, json=None):
        logger.debug("Request hooked %s %s", path, json)
        mock_response = MagicMock(spec=aiohttp.ClientResponse)
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.status = 200

        # Make json() an async method
        async def async_json():
            if path == '/profile':
                roles = ["user", "admin"] if is_admin else ["user"]
                logger.debug(f"Mocked profile response with roles: {roles}")
                return {
                    "data": {
                        "roles": roles
                    },
                    "roles": roles
                }
            return {}

        mock_response.json = async_json

        async_mock = AsyncMock(return_value=mock_response)
        async_mock.__aenter__ = async_mock
        return async_mock
        
    return mock_microservice_calls

# Fixtures for test data
@pytest.fixture
def test_post_id():
    """Return a fixed test post ID"""
    return "2c81a431-af77-48fc-b7e9-198f4af8f8f4"

@pytest.fixture
def post_owner():
    """Return a post owner user object"""
    return {"id": "1234", "name": "PostOwner"}

@pytest.fixture
def admin_user():
    """Return an admin user object"""
    return {"id": "9999", "name": "AdminUser"}

@pytest.fixture
def regular_user():
    """Return a regular user object (neither owner nor admin)"""
    return {"id": "5555", "name": "RegularUser"}

@pytest.fixture
def owner_post(test_post_id, post_owner):
    """Return a post owned by the post_owner"""
    return create_mock_post(owner_id=post_owner["id"], post_id=test_post_id)

@pytest.fixture
def schema_with_owner_post(mock_database_class, post_owner):
    """Return a schema mock with a post owned by post_owner"""
    return setup_database_mocks(mock_database_class, post_owner["id"])

@pytest.fixture
def admin_client(mock_http_client):
    """Return a client with admin role"""
    mock_http_client.get = Mock(side_effect=create_microservice_mock(is_admin=True))
    return mock_http_client

@pytest.fixture
def regular_client(mock_http_client):
    """Return a client with regular user role (not admin)"""
    mock_http_client.get = Mock(side_effect=create_microservice_mock(is_admin=False))
    return mock_http_client

@pytest.mark.component
def test_delete_post_admin(mock_read_config, admin_client, mock_database_class, 
                          test_post_id, post_owner, admin_user, owner_post, schema_with_owner_post):
    """Test for the delete_post endpoint as an admin user."""
    from post.main import app

    # Set up config
    mock_read_config.return_value = test_post_config
    
    # Mock the database.get_schema to return our mocked schema
    with patch('msfwk.database.get_schema', side_effect=lambda schema_name=None: 
               schema_with_owner_post if schema_name == "collaborative" else mock_database_class):

        # Mock get_post to return our test data
        with patch('post.handler.get_post', return_value=owner_post):
            # Set current user as admin
            set_current_user(DespUser(admin_user["id"], admin_user["name"]))
            
            # Test the endpoint
            with TestClient(app) as client:
                response = client.delete(f"/{test_post_id}")
                
                # Verify response
                assert response.status_code == 200
                data = response.json()
                assert "data" in data
                assert "message" in data["data"]
                assert test_post_id in data["data"]["message"]

@pytest.mark.component
def test_delete_post_owner(mock_read_config, regular_client, mock_database_class,
                          test_post_id, post_owner, schema_with_owner_post):
    """Test for the delete_post endpoint as the post owner."""
    from post.main import app

    # Set up config
    mock_read_config.return_value = test_post_config
    
    # Create post owned by the current user
    owner_post = create_mock_post(owner_id=post_owner["id"], post_id=test_post_id)

    # Mock the database.get_schema to return our mocked schema
    with patch('msfwk.database.get_schema', side_effect=lambda schema_name=None: 
               schema_with_owner_post if schema_name == "collaborative" else mock_database_class):

        # Mock get_post to return our test data
        with patch('post.handler.get_post', return_value=owner_post):
            # Set current user as the owner
            set_current_user(DespUser(post_owner["id"], post_owner["name"]))
            
            # Test the endpoint
            with TestClient(app) as client:
                response = client.delete(f"/{test_post_id}")
                
                # Verify response
                assert response.status_code == 200
                data = response.json()
                assert "data" in data
                assert "message" in data["data"]
                assert test_post_id in data["data"]["message"]

@pytest.mark.component
def test_delete_post_unauthorized(mock_read_config, regular_client, mock_database_class,
                                 test_post_id, post_owner, regular_user, owner_post, schema_with_owner_post):
    """Test for the delete_post endpoint with unauthorized user."""
    from post.main import app

    # Set up config
    mock_read_config.return_value = test_post_config

    # Mock the database.get_schema to return our mocked schema
    with patch('msfwk.database.get_schema', side_effect=lambda schema_name=None: 
               schema_with_owner_post if schema_name == "collaborative" else mock_database_class):

        # Mock get_post to return our test data
        with patch('post.handler.get_post', return_value=owner_post):
            # Set current user as a regular user (not owner, not admin)
            set_current_user(DespUser(regular_user["id"], regular_user["name"]))
            
            # Test the endpoint
            with TestClient(app) as client:
                response = client.delete(f"/{test_post_id}")
                
                # Verify response indicates forbidden
                assert response.status_code == 403
                data = response.json()
                assert "error" in data
                assert "Only the post owner or admin can delete the post" in data["error"]["message"] 