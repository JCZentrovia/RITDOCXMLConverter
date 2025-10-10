#!/bin/sh
export AWS_PROFILE=jadmin

version=$1
aws ecr get-login-password --region us-east-1 |  docker login --username AWS --password-stdin 307654412330.dkr.ecr.us-east-1.amazonaws.com
docker buildx build --platform linux/amd64 -t manuscript_processor .
docker tag manuscript_processor:latest 307654412330.dkr.ecr.us-east-1.amazonaws.com/manuscript_processor:$version
docker push 307654412330.dkr.ecr.us-east-1.amazonaws.com/manuscript_processor:$version