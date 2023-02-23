#!/bin/sh

ARTI_WEBHOOK_USER="example"
ARTI_WEBHOOK_PASS="example"
ARTI_WEBHOOK_HOST="example.jfrog.io"
ARTI_WEBHOOK_NUM="21"

curl -T pypi.json -H'Content-Type:application/json' -XPOST "https://${ARTI_WEBHOOK_USER}:${ARTI_WEBHOOK_PASS}@${ARTI_WEBHOOK_HOST}/v1/projectIntegrations/${ARTI_WEBHOOK_NUM}/hook"
