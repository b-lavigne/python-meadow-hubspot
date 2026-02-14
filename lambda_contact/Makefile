# Meadow HubSpot Lambda - Reference Makefile
# This is a TEMPLATE - replace all credential placeholders with environment variables
# NEVER commit actual credentials to version control

# IMPORTANT: Create a .env file locally with your credentials (see .env.example)
# Then run: export $(cat .env | xargs) before using this Makefile

# Define variables
BUILD_CONTEXT = ./docker-build-context
DOCKERFILE_PATH = ./Dockerfile
IMAGE_NAME = meadow-hubspot-contact
TAG = latest
LAMBDA_FUNCTION = meadow-hubspot-contact
AWS_ACCOUNT ?= $(AWS_ACCOUNT_ID)  # Set via environment
AWS_PROFILE ?= meadow
AWS_REGION ?= us-east-2

# Security: These should NEVER have hardcoded values
# Set these via environment variables or load from AWS Secrets Manager
AWS_ACCESS_KEY_ID ?= $(AWS_ACCESS_KEY_ID)
AWS_SECRET_ACCESS_KEY ?= $(AWS_SECRET_ACCESS_KEY)
HUBSPOT_API_KEY ?= $(HUBSPOT_API_KEY)

.PHONY: all
all: clean aws-login build aws-deploy aws-update-lambda
	@echo "Building and sending to AWS - image and Lambda..."


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
	cp -r ../shared $(BUILD_CONTEXT)/

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
	aws lambda update-function-code \
		--profile $(AWS_PROFILE) \
		--region $(AWS_REGION) \
		--function-name $(LAMBDA_FUNCTION) \
		--image-uri $(AWS_ACCOUNT).dkr.ecr.$(AWS_REGION).amazonaws.com/$(IMAGE_NAME):$(TIMESTAMP)
	@echo "Waiting for Lambda to be active..."
	aws lambda wait function-updated \
		--profile $(AWS_PROFILE) \
		--region $(AWS_REGION) \
		--function-name $(LAMBDA_FUNCTION)
	@echo "✓ Lambda function updated and ready"

# Clean the build context
.PHONY: clean
clean:
	@echo "Cleaning the build context..."
	rm -rf $(BUILD_CONTEXT)

# Local testing with environment variables
.PHONY: lambda-run
lambda-run: build
	@echo "Starting container for local testing..."
	@if [ -z "$(HUBSPOT_API_KEY)" ]; then echo "ERROR: HUBSPOT_API_KEY not set"; exit 1; fi
	docker run \
		-e LOCAL=True \
		-e AWS_ACCESS_KEY_ID=$(AWS_ACCESS_KEY_ID) \
		-e AWS_SECRET_ACCESS_KEY=$(AWS_SECRET_ACCESS_KEY) \
		-e HUBSPOT_API_KEY=$(HUBSPOT_API_KEY) \
		-e AWS_REGION=$(AWS_REGION) \
		-p 9000:8080 \
		$(IMAGE_NAME):latest

.PHONY: lambda-test
lambda-test:
	@echo "Testing Lambda with sample event..."
	curl "http://localhost:9000/2015-03-31/functions/function/invocations" -d @../docs/json_objects/event_patient_register.json

# Load secrets from AWS Secrets Manager (alternative to .env file)
.PHONY: load-secrets
load-secrets:
	@echo "Loading secrets from AWS Secrets Manager..."
	$(eval SECRETS := $(shell aws secretsmanager get-secret-value --secret-id meadow/hubspot/dev --query SecretString --output text --profile $(AWS_PROFILE)))
	@echo "Secrets loaded (use this in CI/CD, not locally)"

# Validate environment before deploy
.PHONY: validate-env
validate-env:
	@echo "Validating required environment variables..."
	@if [ -z "$(AWS_ACCOUNT)" ]; then echo "ERROR: AWS_ACCOUNT not set"; exit 1; fi
	@if [ -z "$(HUBSPOT_API_KEY)" ]; then echo "ERROR: HUBSPOT_API_KEY not set"; exit 1; fi
	@echo "✓ Environment validated"

# Run unit tests
.PHONY: test
test:
	@echo "Running unit tests..."
	pipenv run pytest tests/ -v

# Format code
.PHONY: format
format:
	@echo "Formatting code with black..."
	pipenv run black lambda_function.py hubspot.py

# Lint code
.PHONY: lint
lint:
	@echo "Linting code..."
	pipenv run flake8 lambda_function.py hubspot.py
	pipenv run mypy lambda_function.py hubspot.py
