# terraform-meadowbio

## Project Overview

Security-first API service for Meadow Bio, built with Terraform on AWS serverless technologies. 
The first set of application services that will run will be an endpoint the main patient application
can send data to which will then be sent to HubSpot.

The application will recieve a webhook event and process it to store in Hubspot. The list of events 
to expect are below.

## User Experience

### General
- Two main flows of the experience
  - New Order / Patient intake
  - Refill / Prescription Order

### Detail
- Patient, most likely patient guardian, begins registration process
- Registration process has various steps and questions 
- Occasionally, patients may fall out of the flow (abandoned cart-like) 
- Once registration completed the patient will recieve next set of communcation from the platform
- Patient will use the Telehealth Portal to manage communcications and purchase/pay for service
- Throughout the user journey various data points will be shared to this service

## Webhook Events
| Category | Event Types |
|----------|-------------|
| Registration | `patient.registered` |
| Intake | `intake.started`, `intake.abandoned` |
| Checkout | `checkout.abandoned`, `order.created` |
| Subscription | `subscription.canceled` |
| Payment | `payment.succeeded`, `payment.failed` |

## Webhook Payloads
Located in the `docs/json_objects` directory are example payloads to be sent to our endpoint. These 
objects will be critical to the application and determining the appropriate action from this 
process.

## External Systems
### Hubspot
Hubspot is the source of truth for customer records for marketing and communciations purposes to drive email automation 
such as drip campaigns.

Hubspot "workflows" are what's to be driving the outreach/communications to customers.
Detail explanation of how the "workflows" will be configured is located in `docs/HUBSPOT_WORKFLOWS.md`.

The following is a proposed event to Hubspot mapping:
```
Guardian Contact ←→ Patient Contact (native contact-to-contact association)
Guardian Contact ←→ Deal (native)
Patient Contact ←→ Deal (native)
Guardian Contact ←→ Ticket (native)
```
#### Considerations
- HubSpot requires API key authentication (stored in AWS Secrets Manager)
- HubSpot provides "associations" to link objects together
- Any custom object may require more expensive license
- Contains PHI/PII - HIPAA compliance considerations

#### HubSpot Data Model

**Contact Structure**
1. **Guardian/Parent Contact** (e.g., sarah.johnson@example.com)
   - Properties: `email`, `firstname`, `lastname`, `phone`, `state`
   - Custom Properties: `parent_external_id`, `patient_relationship="parent"`

2. **Patient Contact** (e.g., tommy.johnson+p43@meadowbio.com)
   - **Synthetic Email Pattern**: `{firstname}.{lastname}+p{patient_id}@meadowbio.com`
   - Why? Minors don't have their own emails, but HubSpot requires unique email per contact
   - Custom Properties: `patient_external_id`, `is_minor=true`, `guardian_external_id`

**Deal Structure (Patient Journey Pipeline)**
- **One deal per patient** - represents their entire journey through the system
- **Pipeline stages** map to patient journey:
  - `registration` - Patient registered, intake not started
  - `intake_in_progress` - Patient started intake form
  - `intake_abandoned` - Patient abandoned intake (needs follow-up)
  - `checkout_abandoned` - Patient started checkout but didn't complete
  - `active_subscription` - Order created, patient is active subscriber
  - `closedlost` - Subscription canceled (churned)
- Deal properties track:
  - `patient_external_id` - Links deal to patient
  - `subscription_external_id` - Order ID when subscription created
  - `mrr` - Monthly recurring revenue
  - `last_payment_date` - Last successful payment
  - `next_refill_date` - Next scheduled refill

**Associations**
- Contact-to-Contact: Parent ↔ Child (using HubSpot native parent/child association type)
- Contact-to-Deal: Both parent and patient contacts associated to Deal

**Example**:
```
Parent Contact: sarah.johnson@example.com
  ↓ (parent/child association)
Patient Contact: tommy.johnson+p43@meadowbio.com
  ↓ (both associated to)
Deal: "Tommy Johnson - Patient Journey"
  Pipeline Stage: active_subscription
  MRR: $99.00
  Subscription ID: 101
```

### Event Mapping
| Event Type | HubSpot Action | Object(s) |
|------------|----------------|-----------|
| `patient.registered` | Create Contacts (parent + patient) + Create Deal in "registration" stage + Associate all | Contacts + Deal |
| `intake.started` | Move Deal to "intake_in_progress" stage | Deal |
| `intake.abandoned` | Move Deal to "intake_abandoned" stage | Deal |
| `checkout.abandoned` | Move Deal to "checkout_abandoned" stage | Deal |
| `order.created` | Move Deal to "active_subscription" stage, set `subscription_external_id`, `mrr` | Deal |
| `subscription.canceled` | Move Deal to "closedlost" stage | Deal |
| `payment.succeeded` | Update Deal `last_payment_date`, `mrr` properties | Deal |
| `payment.failed` | (No action - payment failures handled outside HubSpot) | None |

**Important:**
- **ONE deal per patient** tracks their entire journey from registration → active → churned
- Deal moves through pipeline stages as patient progresses


## Event Routing Strategy

**Stage 1 Approach**: Separate Lambda functions by HubSpot object type
- All webhook events → API Gateway → Route to appropriate Lambda based on event type
- Each Lambda is responsible for one HubSpot object type (Contact or Deal)
- Simple, focused functions that are easy to understand and maintain

| Event Type | Lambda Function | HubSpot Operations |
|------------|-----------------|-------------------|
| `patient.registered` | lambda_contact | Create 2 Contacts + Create Deal in "registration" stage + Associate all |
| `intake.started` | lambda_deal | Move Deal to "intake_in_progress" stage |
| `intake.abandoned` | lambda_deal | Move Deal to "intake_abandoned" stage |
| `checkout.abandoned` | lambda_deal | Move Deal to "checkout_abandoned" stage |
| `order.created` | lambda_deal | Move Deal to "active_subscription" stage + set subscription_external_id + mrr |
| `payment.succeeded` | lambda_deal | Update Deal last_payment_date + mrr |
| `subscription.canceled` | lambda_deal | Move Deal to "closedlost" |
| `payment.failed` | (none) | No action |

**Rationale**: Two Lambda functions - one for contacts, one for deals. Simple and focused.

## Phased Implementation
- Stage 1
  - Two Lambda functions (lambda_contact, lambda_deal)
  - AWS to HubSpot communication via API
  - General AWS infrastructure (separate project)
  - HubSpot workflow triggering via property updates
  - API Gateway API key authentication
  - Basic error handling and logging
- Stage 2
  - More robust infrastructure: WAF, DDoS protection
  - HMAC webhook signature validation
  - Dead Letter Queue (DLQ) for failed events
  - Idempotency checking with DynamoDB
  - Potentially build reusable HubSpot library

## Tech Stack

- **IaC**: Terraform
- **Cloud**: AWS
- **Compute**: Lambda
- **API**: API Gateway (REST API)
- **Auth (Stage 1)**: API Gateway API keys with usage plans
- **Auth (Stage 2+)**: HMAC signature validation, Cognito for user-facing auth
- **Data (Optional)**: DynamoDB for idempotency tracking (Stage 1: HubSpot as source of truth)
- **Secrets**: AWS Secrets Manager / SSM Parameter Store
- **Monitoring**: CloudWatch, X-Ray
- **Containerization**: Docker + ECR

## Python App Code
- Pipenv as dependency management
- Avoid building 'classes' - these are scripts/functions

## Project Structure

```
python-meadow-hubspot/
  shared/                    # Shared code used by all Lambda functions
    hubspot.py               # Unified HubSpot API client (contacts, deals, tickets, associations)
  lambda_contact/            # Handles registration and intake events
    lambda_function.py       # Main handler for patient/guardian contacts
    requirements.txt         # Python dependencies
    Dockerfile               # Container image definition
    Makefile                 # Build, test, deploy automation
  lambda_deal/               # Handles checkout and subscription events
    lambda_function.py       # Main handler for deals
    requirements.txt
    Dockerfile
    Makefile
  lambda_ticket/             # Handles payment failures and cancellations
    lambda_function.py       # Main handler for tickets
    requirements.txt
    Dockerfile
    Makefile
  docs/
    json_objects/            # Example webhook payloads
    references/              # Reference templates (Makefile, Dockerfile)
    HUBSPOT_WORKFLOWS.md     # HubSpot workflow configuration guide
    meadow-intake-flow.png   # User journey diagram
    meadow-refill-flow.png   # Refill flow diagram
  tests/                     # Unit and integration tests
    test_lambda_contact.py
    test_lambda_deal.py
    test_lambda_ticket.py
    fixtures/                # Test data
  terraform/                 # Infrastructure as code (separate repo)
  Pipfile                    # Local development dependencies
  Pipfile.lock
  .env.example               # Environment variable template
  .gitignore                 # Git exclusions (includes .env)
```

## Security Principles

- Least-privilege IAM policies on all resources
- Encryption at rest and in transit for all data stores
- No secrets in code or state — use Secrets Manager / SSM
- Enable CloudTrail and access logging

### Secrets Management
- ❌ **NEVER** commit credentials to version control
- ✅ Use AWS Secrets Manager for production secrets (HubSpot API key, webhook secrets)
- ✅ Use `.env` file for local development (see `.env.example`)
- ✅ Rotate API keys quarterly
- ✅ Reference Makefile uses environment variables only (no hardcoded values)

### Webhook Security

**Stage 1: API Gateway API Key**
- Patient portal sends `x-api-key` header with each webhook
- API Gateway validates key before invoking Lambda
- Keys managed via AWS API Gateway usage plans
- Rotate keys quarterly

**Stage 2: HMAC Signature Validation**
- Patient portal signs webhook payload with shared secret
- Lambda verifies `X-Meadow-Signature` header before processing
- Prevents replay attacks and unauthorized webhooks
- Example: `X-Meadow-Signature: sha256=<hmac_hex_digest>`

**Rejected Approaches**
- ❌ IP allowlisting (portal may use dynamic IPs, CDNs)
- ❌ mTLS (overkill for Stage 1, complex certificate management)

### Data Privacy
- PHI/PII is transmitted to HubSpot (HIPAA considerations)
- All data encrypted in transit (TLS 1.2+)
- HubSpot API calls use HTTPS only
- Logs must NOT contain sensitive patient data (SSN, full medical records)
- CloudWatch logs: sanitize before logging (use patient_id, not patient_name)

## Conventions
- Env variables to run locally (see `.env.example`)
- Simple naming conventions (snake_case for Python)
- Small and deliberate functions - prefer composition over classes
- Functional programming style for handlers

## Error Handling & Reliability

### Idempotency
- Use `event.idempotency_key` from webhook payload to deduplicate events
- **Stage 1**: Use HubSpot search API to check if record already exists (e.g., search by `patient_external_id`)
- **Stage 2**: Store processed event IDs in DynamoDB with TTL (e.g., 7 days)
- Prevents duplicate contacts/deals from webhook retries

### Retry Logic
- Lambda built-in retry: 2 automatic retries on failure
- **Stage 2**: Dead Letter Queue (SQS) for events that fail after all retries
- CloudWatch alerts when DLQ depth > 0
- Manual intervention queue for persistent failures

### HubSpot API Rate Limits
- **Professional tier**: 100 requests per 10 seconds (burst), 10,000 per day
- Implement exponential backoff on 429 (rate limit) responses
- **Stage 2**: Consider SQS queue for high-volume scenarios (buffer bursts)
- Log rate limit warnings to CloudWatch

### Error Handling Patterns
```python
# Graceful degradation example
try:
    create_hubspot_contact(payload)
except HubSpotRateLimitError:
    # Retry with exponential backoff
    retry_with_backoff()
except HubSpotAPIError as e:
    # Log error, send to DLQ for manual review
    logger.error(f"HubSpot API error: {e}", extra={"event": payload})
    send_to_dlq(payload)
```

### Logging & Observability
- **Structured JSON logging** with context:
  - `event_type`, `idempotency_key`, `patient_external_id`, `timestamp`
  - Do NOT log PII (names, emails, addresses) - use IDs only
- CloudWatch Logs Insights queries for debugging
- X-Ray tracing for Lambda → HubSpot API call paths
- Metrics: success rate, latency, error rate by event type

## Getting Started

### Prerequisites
- Python 3.12+
- Pipenv (`pip install pipenv`)
- Docker Desktop
- AWS CLI configured (`aws configure`)
- HubSpot account with API key (Professional or Enterprise tier recommended)

### Local Development Setup

1. **Clone repository**
   ```bash
   git clone <repo-url>
   cd python-meadow-hubspot
   ```

2. **Install dependencies**
   ```bash
   pipenv install --dev
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your actual values:
   # - AWS credentials
   # - HubSpot API key
   # - Other configuration
   ```

4. **Run tests**
   ```bash
   pipenv run pytest tests/ -v
   ```

5. **Build Docker image locally**
   ```bash
   cd lambda_contact
   make build
   ```

6. **Run Lambda locally**
   ```bash
   # Ensure .env is loaded
   export $(cat .env | xargs)
   make lambda-run
   ```

7. **Test with sample webhook**
   ```bash
   # In another terminal
   make lambda-test
   # Or manually:
   curl "http://localhost:9000/2015-03-31/functions/function/invocations" \
     -d @../docs/json_objects/event_patient_register.json
   ```

### Deploy to AWS

1. **Set up infrastructure** (separate Terraform project)
   ```bash
   cd terraform/
   terraform init
   terraform plan
   terraform apply
   ```

2. **Deploy Lambda functions**
   ```bash
   # Deploy lambda_contact
   cd lambda_contact
   export $(cat ../.env | xargs)
   make validate-env  # Verify required env vars are set
   make all           # Build, push to ECR, update Lambda

   # Deploy lambda_deal
   cd ../lambda_deal
   make all

   # Deploy lambda_ticket
   cd ../lambda_ticket
   make all
   ```

3. **Verify deployment**
   ```bash
   aws lambda invoke \
     --function-name meadow-hubspot-contact \
     --payload file://docs/json_objects/event_patient_register.json \
     response.json
   cat response.json
   ```

### Development Workflow

1. Make code changes in the appropriate Lambda directory (`lambda_contact/`, `lambda_deal/`, or `lambda_ticket/`)
2. Run tests: `pipenv run pytest`
3. Test locally: `cd lambda_contact && make lambda-run` and `make lambda-test`
4. Deploy: `make all` (builds, pushes, updates Lambda)
5. Monitor: Check CloudWatch Logs for errors

### Useful Commands

```bash
# Format code
make format

# Lint code
make lint

# Run tests with coverage
pipenv run pytest --cov=lambda_contact --cov=lambda_deal --cov=lambda_ticket tests/

# View CloudWatch logs
aws logs tail /aws/lambda/meadow-hubspot-contact --follow
aws logs tail /aws/lambda/meadow-hubspot-deal --follow
aws logs tail /aws/lambda/meadow-hubspot-ticket --follow

# Test HubSpot API connectivity
pipenv run python -c "from hubspot import Client; print(Client().get_account_info())"
```



