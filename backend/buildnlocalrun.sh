#!/bin/sh
export AWS_PROFILE=jadmin

version=$1

docker buildx build --platform linux/amd64 -t xmlconverter .

echo "Running with default entrypoint..."
docker run -p 8000:8000 --env-file .env -v ~/.aws:/home/appuser/.aws:ro --network="host" --rm -it xmlconverter