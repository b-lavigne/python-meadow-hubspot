IMAGE_NAME      = meadow-hubspot-gtm-proxy
LAMBDA_FUNCTION = meadow-hubspot-gtm-proxy
AWS_ACCOUNT    ?= 253260000779
AWS_PROFILE    ?= meadow
AWS_REGION     ?= us-east-2

TIMESTAMP := $(shell date +%s)

.PHONY: all
all: aws-login build aws-deploy aws-update-lambda

.PHONY: aws-login
aws-login:
	aws ecr get-login-password --region $(AWS_REGION) --profile $(AWS_PROFILE) | \
		docker login --username AWS --password-stdin $(AWS_ACCOUNT).dkr.ecr.$(AWS_REGION).amazonaws.com

.PHONY: build
build:
	docker build \
		--no-cache \
		--platform linux/amd64 \
		-t $(IMAGE_NAME):latest \
		-t $(IMAGE_NAME):$(TIMESTAMP) \
		.

.PHONY: aws-deploy
aws-deploy:
	docker tag $(IMAGE_NAME):$(TIMESTAMP) $(AWS_ACCOUNT).dkr.ecr.$(AWS_REGION).amazonaws.com/$(IMAGE_NAME):$(TIMESTAMP)
	docker tag $(IMAGE_NAME):latest $(AWS_ACCOUNT).dkr.ecr.$(AWS_REGION).amazonaws.com/$(IMAGE_NAME):latest
	docker push $(AWS_ACCOUNT).dkr.ecr.$(AWS_REGION).amazonaws.com/$(IMAGE_NAME):$(TIMESTAMP)
	docker push $(AWS_ACCOUNT).dkr.ecr.$(AWS_REGION).amazonaws.com/$(IMAGE_NAME):latest

.PHONY: aws-update-lambda
aws-update-lambda:
	aws lambda update-function-code \
		--profile $(AWS_PROFILE) \
		--region $(AWS_REGION) \
		--function-name $(LAMBDA_FUNCTION) \
		--image-uri $(AWS_ACCOUNT).dkr.ecr.$(AWS_REGION).amazonaws.com/$(IMAGE_NAME):$(TIMESTAMP) \
		--output text --query 'FunctionArn' > /dev/null
	@echo "Lambda update initiated"

.PHONY: lambda-run
lambda-run: build
	docker run \
		-e ENVIRONMENT=local \
		-e HUBSPOT_WEBHOOK_URL=$(HUBSPOT_WEBHOOK_URL) \
		-p 9000:8080 \
		$(IMAGE_NAME):latest

.PHONY: lambda-test
lambda-test:
	curl -X POST http://localhost:9000/2015-03-31/functions/function/invocations \
		-H "Content-Type: application/json" \
		-d '{"httpMethod":"POST","headers":{"Origin":"https://meadowbiosciences.com"},"body":"{\"eventName\":\"test.ping\",\"properties\":{}}"}'

.PHONY: clean
clean:
	docker rmi $(IMAGE_NAME):latest 2>/dev/null || true
