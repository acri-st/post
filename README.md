# Post

## Table of Contents

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Development](#development)
- [Testing](#testing)
- [Contributing](#contributing)
- [Deployment](#deployment)
- [License](#license)
- [Support](#support)

## Introduction

### What is the Post Service?

The Post service is a microservice that enables communication around assets and posts. It provides the infrastructure and tools necessary for users to create, manage, and participate in discussions, topics, and posts related to assets.

The Post service handles:
- **Discussion Management** Creating and managing discussion categories linked to assets
- **Topic and Post Management** Creating, editing, and retrieving topics and posts
- **Moderation Integration** Sending posts and topics for moderation
- **Integration** Working with other  microservices like Asset Management, Auth, and Notification

## Prerequisites

Before you begin, ensure you have the following installed:
- **Git**
- **Docker** Docker is mainly used for the test suite, but can also be used to deploy the project via docker compose

## Installation

1. Clone the repository:
```bash
git clone https://github.com/acri-st/post.git
cd post
```

## Development

## Development Mode

### Standard local development

Setup environment
```bash
make setup
```

Start the development server:
```bash
make start
```

To clean the project and remove generated files, use:
```bash
make clean
```

## Contributing

Check out the **CONTRIBUTING.md** for more details on how to contribute.