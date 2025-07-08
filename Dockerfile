# This argument is used to build in the CI
ARG BASE_VERSION=v5.2.0
ARG REGISTRY=harbor.shared.acrist-services.com/dsy/desp-aas/
FROM ${REGISTRY}desp-base-image:${BASE_VERSION}

ARG CI_COMMIT_SHORT_SHA=xxxxxx
ARG CI_COMMIT_TAG=x.x.x
ENV GIT_HASH=$CI_COMMIT_SHORT_SHA
ENV VERSION=$CI_COMMIT_TAG
# This line indicates what folder contains the main.py file
ENV ENTRYPOINT=post
# This copy change the owner, this is needed for Tilt to override during development
COPY --chown=$LOCAL_USER:$LOCAL_GROUP ./${ENTRYPOINT} ./${ENTRYPOINT}
# COPY requirements.txt ./${ENTRYPOINT}
# Install dependencies in addition to the parents ones
# RUN pip install --no-cache-dir -r ./${ENTRYPOINT}/requirements.txt
# DO NOT OVERRIDE THE ENTRYPOINT BUT USE THE ENTRYPOINT ENV VAR
