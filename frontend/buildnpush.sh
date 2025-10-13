#!/bin/sh
export AWS_PROFILE=jadmin

ng build --configuration production
cd dist/manuscript-processor-frontend/browser
aws s3 sync . s3://frontends-zentrovia/xmlconverter/
cd ../../..
