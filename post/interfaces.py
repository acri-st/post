"""Models of interface"""

import datetime
from uuid import UUID

from msfwk.models import BaseModelAdjusted
from pydantic import BaseModel

###############
#    Post
###############


class BasicPost(BaseModel):
    """Class used for a basic post"""

    id: UUID
    title: str
    message: str
    despUserId: str
    topicId: int
    categoryId: int
    categoryName: str
    created_at: datetime.datetime
    reply_count: int | None = None
    replies: list[dict] | None = None

    @staticmethod
    def from_record(record: any) -> "BasicPost":
        """Return Post from a business object"""
        return BasicPost(
            id=record.id,
            title=record.title,
            despUserId=record.despUserId,
            topicId=record.topicId,
            message=record.message,
            categoryId=record.categoryId,
            categoryName=record.category_name,
            created_at=record.created_at,
        )

    def to_json(self) -> dict:
        """Dict to be inserted in database"""
        json = {
            "id": str(self.id),
            "title": self.title,
            "despUserId": self.despUserId,
            "message": self.message,
            "categoryId": self.categoryId,
            "topicId": self.topicId,
            "categoryName": self.categoryName,
            "created_at": self.created_at,
            "reply_count": self.reply_count,
            "replies": self.replies,
        }
        return {k: v for k, v in json.items() if v is not None}


class PostCreationData(BaseModelAdjusted):
    """Payload for creating a new post"""

    title: str
    category_id: str
    message: str


class PostDatabaseClass(BaseModelAdjusted):
    """Class used for creating a new post in the database"""

    id: UUID
    title: str
    message: str
    despUserId: str
    topicId: int
    categoryId: int


class PostsResponse(BasicPost):
    """Class to return information on a post"""

    pass


###############
#  Repository
###############


class RepositoryDatabaseBase(BaseModelAdjusted):
    url: str
    username: str
    token: str


class RepositoryCreationPayload(RepositoryDatabaseBase):
    """Class describing a repository that will be registered"""

    pass


class RepositoryDatabaseClass(RepositoryDatabaseBase):
    """Class describing a project that has been updated."""

    id: UUID


class RepositoryResponseStorage(BaseModelAdjusted):
    """Representation of the storage creation response"""

    resource_id: str
    url: str
    token: str


###############
#   Storage
###############


class GitServer(BaseModelAdjusted):
    url: str
    token: str


class StoragePayload(BaseModelAdjusted):
    repositoryName: str
    repositoryGroupe: str
    gitServer: GitServer | None


###############
#  Discussion
###############


class DiscussionResponse(BaseModelAdjusted):
    """Returned object on get discussion"""

    id: int
    name: str
    topics: list


class TopicResponse(BaseModelAdjusted):
    """Returned object on get topic"""

    id: int
    posts: list
