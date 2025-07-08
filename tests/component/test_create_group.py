from unittest.mock import AsyncMock, MagicMock, Mock
import aiohttp
from fastapi.testclient import TestClient

from msfwk.models import DespUser
from msfwk.utils.user import set_current_user
from .utils import is_valid_uuid,mock_database_class,fake_table
from msfwk.utils.conftest import mock_read_config,mock_http_client
import pytest
from msfwk.utils.logging import get_logger
import re
from .config import test_post_config

logger = get_logger("test")

def mock_microservice_calls(
        path: str=None,
        json=None):
        logger.debug("Request hooked %s %s",path,json)
        mock = MagicMock(spec=aiohttp.ClientResponse)
        mock.headers = {'Content-Type':'application/json'}
        mock.status = 200
        pattern = r'^/discussion/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'

        if re.match(pattern, path) :
            logger.debug("Mocked JsonResponse %s",path)
            mock.json.return_value = {
                                        "data": {
                                            "id": "1",
                                            "name": "postdiscussion",
                                            "topics": []
                                        }
                                    }
        if path == '/repository':
            logger.debug("Mocked JsonResponse %s",path)
            mock.json.return_value = {
                                        "data": {
                                            "resource_id": "b594cb91-0dec-4ab8-8005-cf95f4e55d30",
                                            "url": "http://gitlab.example.com/1234/",
                                            "token": "blablablabla"
                                        }
                                    }
        amock = AsyncMock(return_value=mock)
        amock.__aenter__ = amock
        return amock

@pytest.mark.skip(reason="Mock PostParticipants table")
# @pytest.mark.component
def test_create_post(mock_read_config,mock_http_client, mock_database_class):
    mock_http_client.post = Mock(side_effect=mock_microservice_calls)
    mock_read_config.return_value = test_post_config
    mock_database_class.tables = {
        "Posts": fake_table("Posts", [{"id": "123", "name": "test_post"}]),
        "PostParticipants": fake_table("PostParticipants", []),
    }
    from post.main import app
    set_current_user(DespUser(f"{9999}", "Yves"))
    # Mock the call to the Search Service
    with TestClient(app) as client:
        payload={
            "name": "post_test_name",
            "category_id": "1",
            "description": "description_test"
        }
        response = client.post("/create_post",json=payload)
        assert response.status_code == 200
        data = response.json()["data"]
        assert is_valid_uuid(data['id']), f"id is an invalid UUID"
        #TODO(tchassanit): add more assert if needed
