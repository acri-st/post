from typing import AsyncGenerator
from sqlalchemy import Column, MetaData, Table
from msfwk.schema.schema import Schema
import pytest
import uuid

from msfwk import database
from unittest.mock import MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import MagicMock, Mock

from msfwk.utils.logging import get_logger

logger = get_logger("test")

def is_valid_uuid(uuid_to_test, version=4):
    try:
        # check for validity of Uuid
        uuid_obj = uuid.UUID(uuid_to_test, version=version)
    except ValueError:
        return False
    return True

@pytest.fixture(autouse=True)
async def mock_database_class() -> AsyncGenerator[Schema, None] :
    """Mock the database and return the session result can be mocked
    record = MagicMock(MappingResult)
    record._mapping = {"field1":1}
    mock_database_class.tables= {"mytable":fake_table("mytable",["col1","coln"])}
    mock_database_class.get_async_session().execute.return_value=[record]
    """
    logger.info("Mocking the database session")
    with patch("msfwk.database.get_schema") as mock:
        schema = Schema("postgresql+asyncpg://test:test@test:5432/test")
        session = MagicMock(spec=AsyncSession)
        session.__aenter__.return_value = session
        schema.get_async_session = Mock(return_value=session)
        mock.return_value = schema
        yield schema
    logger.info("Mocking database reset")

def fake_table(name:str,columns:list[str])-> Table:
    return Table(name,MetaData(),*[Column(col) for col in columns])