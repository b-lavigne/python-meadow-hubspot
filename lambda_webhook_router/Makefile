# Meadow HubSpot Lambda Webhook Router - Makefile
# This is a TEMPLATE - replace all credential placeholders with environment variables
# NEVER commit actual credentials to version control

# IMPORTANT: Create a .env file locally with your credentials (see .env.example)
# Then run: export $(cat .env | xargs) before using this Makefile

# Define variables
BUILD_CONTEXT = ./docker-build-context
DOCKERFILE_PATH = ./Dockerfile
IMAGE_NAME = meadow-hubspot-webhook-router
TAG = latest
LAMBDA_FUNCTION = meadow-hubspot-webhook-router
AWS_ACCOUNT ?= 253260000779
AWS_PROFILE ?= meadow
AWS_REGION ?= us-east-2

.PHONY: all
all: clean aws-login build aws-deploy aws-update-lambda
	@echo "Building and sending to AWS - image and Lambda..."

# Build and push to ECR only (skip Lambda update if function doesn't exist yet)
.PHONY: build-only
build-only: clean aws-login build aws-deploy
	@echo "✓ Image built and pushed to ECR"
	@echo "To update Lambda later, run: make aws-update-lambda"


.PHONY: aws-login
aws-login:
	@echo "Logging in to AWS Account - $(AWS_ACCOUNT)"
	aws ecr get-login-password --region $(AWS_REGION) --profile $(AWS_PROFILE) | docker login --username AWS --password-stdin $(AWS_ACCOUNT).dkr.ecr.$(AWS_REGION).amazonaws.com

# Ensure the build context directory exists
.PHONY: prepare-context
prepare-context: clean
	@echo "Preparing fresh build context..."
	mkdir -p $(BUILD_CONTEXT)
	cp $(DOCKERFILE_PATH) $(BUILD_CONTEXT)
	cp requirements.txt $(BUILD_CONTEXT)
	cp lambda_function.py $(BUILD_CONTEXT)

# Single timestamp per make invocation (build + deploy use the same tag)
TIMESTAMP := $(shell date +%s)

# Build the Docker image
.PHONY: build
build: prepare-context
	@echo "Building Docker image..."
	docker build \
		--no-cache \
		--platform linux/amd64 \
		-t $(IMAGE_NAME):latest \
		-t $(IMAGE_NAME):$(TIMESTAMP) \
		$(BUILD_CONTEXT)

.PHONY: aws-deploy
aws-deploy:
	@echo "Deploying code to AWS - ECR"
	docker tag $(IMAGE_NAME):$(TIMESTAMP) $(AWS_ACCOUNT).dkr.ecr.$(AWS_REGION).amazonaws.com/$(IMAGE_NAME):$(TIMESTAMP)
	docker tag $(IMAGE_NAME):latest $(AWS_ACCOUNT).dkr.ecr.$(AWS_REGION).amazonaws.com/$(IMAGE_NAME):latest
	docker push $(AWS_ACCOUNT).dkr.ecr.$(AWS_REGION).amazonaws.com/$(IMAGE_NAME):$(TIMESTAMP)
	docker push $(AWS_ACCOUNT).dkr.ecr.$(AWS_REGION).amazonaws.com/$(IMAGE_NAME):latest

.PHONY: aws-update-lambda
aws-update-lambda:
	@echo "Updating Lambda function with new code..."
	@aws lambda update-function-code \
		--profile $(AWS_PROFILE) \
		--region $(AWS_REGION) \
		--function-name $(LAMBDA_FUNCTION) \
		--image-uri $(AWS_ACCOUNT).dkr.ecr.$(AWS_REGION).amazonaws.com/$(IMAGE_NAME):$(TIMESTAMP) \
		--output text --query 'FunctionArn' > /dev/null
	@echo "✓ Lambda function update initiated"
	@echo "Note: Function may take a few seconds to become active. Check with: aws lambda get-function --function-name $(LAMBDA_FUNCTION)"

# Clean the build context
.PHONY: clean
clean:
	@echo "Cleaning the build context..."
	rm -rf $(BUILD_CONTEXT)

# Validate environment before deploy
.PHONY: validate-env
validate-env:
	@echo "Validating required environment variables..."
	@if [ -z "$(AWS_ACCOUNT)" ]; then echo "ERROR: AWS_ACCOUNT not set"; exit 1; fi
	@echo "✓ Environment validated"
