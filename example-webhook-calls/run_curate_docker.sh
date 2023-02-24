#!/bin/sh

ARTI_WEBHOOK_USER="webhookservice"
ARTI_WEBHOOK_PASS="Admin1234"
ARTI_WEBHOOK_HOST="rcjfrogpoc.jfrog.io"
ARTI_WEBHOOK_NUM="22"

curl -T docker_images.json -H'Content-Type:application/json' -XPOST "https://webhookservice:Admin1234@rcjfrogpoc-pipelines-api.jfrog.io/v1/projectIntegrations/22/hook"
