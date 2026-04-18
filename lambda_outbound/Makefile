FUNCTION_NAME        = meadow-hubspot-outbound
LAMBDA_FUNCTION_NAME = hubspot-meadowbio-dev-hubspot-outbound
CONTAINER_NAME       = $(FUNCTION_NAME)-local
AWS_REGION           = us-east-2
AWS_ACCOUNT_ID       = $(shell aws sts get-caller-identity --query Account --output text --profile meadow)
ECR_REPO             = $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/$(FUNCTION_NAME)
BUILD_CONTEXT        = ./docker-build-context
EVENT               ?= ../docs/json_objects/event_patient_register.json
RIE_PORT             = 9000

.PHONY: build push invoke run stop clean

build:
	rm -rf $(BUILD_CONTEXT)
	mkdir -p $(BUILD_CONTEXT)
	cp Dockerfile $(BUILD_CONTEXT)/
	cp requirements.txt $(BUILD_CONTEXT)/
	cp lambda_function.py $(BUILD_CONTEXT)/
	cp -r ../shared $(BUILD_CONTEXT)/
	docker build --platform linux/arm64 -t $(FUNCTION_NAME):local $(BUILD_CONTEXT)
	rm -rf $(BUILD_CONTEXT)

push: build
	aws ecr get-login-password --region $(AWS_REGION) --profile meadow \
		| docker login --username AWS --password-stdin $(ECR_REPO)
	docker tag $(FUNCTION_NAME):local $(ECR_REPO):latest
	docker push $(ECR_REPO):latest
	aws lambda update-function-code \
		--function-name $(LAMBDA_FUNCTION_NAME) \
		--image-uri $(ECR_REPO):latest \
		--profile meadow \
		--region $(AWS_REGION) \
		--query 'FunctionArn' --output text

invoke: build
	docker run --rm \
		-p $(RIE_PORT):8080 \
		--env-file ../.env \
		-e AWS_DEFAULT_REGION=$(AWS_REGION) \
		--name $(CONTAINER_NAME) \
		-d $(FUNCTION_NAME):local
	sleep 1
	curl -s -X POST http://localhost:$(RIE_PORT)/2015-03-31/functions/function/invocations \
		-H "Content-Type: application/json" \
		-d @$(EVENT) | python3 -m json.tool
	docker stop $(CONTAINER_NAME) 2>/dev/null || true

run: build
	docker run --rm \
		-p $(RIE_PORT):8080 \
		--env-file ../.env \
		-e AWS_DEFAULT_REGION=$(AWS_REGION) \
		--name $(CONTAINER_NAME) \
		$(FUNCTION_NAME):local

stop:
	docker stop $(CONTAINER_NAME) 2>/dev/null || true

clean:
	rm -rf $(BUILD_CONTEXT)
	docker stop $(CONTAINER_NAME) 2>/dev/null || true
	docker rmi $(FUNCTION_NAME):local 2>/dev/null || true
	find . -type d -name __pycache__ -exec rm -rf {} +
