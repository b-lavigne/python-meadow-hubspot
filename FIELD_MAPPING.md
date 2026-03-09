# Field Mapping: Portal Webhook → HubSpot

## Guardian Contact Mapping

| Portal Webhook Field | HubSpot Property | Notes |
|---------------------|------------------|-------|
| `contact.first_name` | `firstname` | Standard property |
| `contact.last_name` | `lastname` | Standard property |
| `contact.email` | `email` | Standard property (unique identifier) |
| `contact.phone` | `phone` | Standard property |
| `contact.state` | `state` | Standard property (must be valid US state) |
| `contact.external_id` | `parent_external_id` | Custom property |
| (hardcoded) | `patient_relationship` = "parent" | Custom property |

## Patient Contact Mapping

| Portal Webhook Field | HubSpot Property | Notes |
|---------------------|------------------|-------|
| `patient.first_name` | `firstname` | Standard property |
| `patient.last_name` | `lastname` | Standard property |
| (generated) | `email` | Synthetic: `{firstname}.{lastname}+p{patient_id}@meadowbio.com` |
| `patient.external_id` | `patient_external_id` | Custom property |
| `patient.is_minor` | `is_minor` | Custom property (converted to string "true"/"false") |
| `contact.external_id` | `guardian_external_id` | Custom property (links to guardian) |
| `patient.date_of_birth` | `date_of_birth` | Custom property |

## Company (Family) Mapping

| Portal Webhook Field | HubSpot Property | Notes |
|---------------------|------------------|-------|
| (derived) | `name` | "The {contact.last_name} Family" |
| `contact.external_id` | `family_external_id` | Custom property (same as guardian external_id) |

## Deal (Patient Journey) Mapping

| Portal Webhook Field | HubSpot Property | Notes |
|---------------------|------------------|-------|
| (derived) | `dealname` | "{patient.first_name} {patient.last_name} — Patient Journey" |
| (hardcoded) | `pipeline` | "869949826" (Patient Journey Pipeline) |
| (event-driven) | `dealstage` | Numeric stage ID (e.g., "1302219588" for activesubscriber) |
| `patient.external_id` | `patient_external_id` | Custom property (links deal to patient) |
| `orders[0].external_id` | `subscription_external_id` | Custom property (set on order.created) |
| `orders[0].price_in_cents / 100` | `mrr` | Custom property (converted to dollars as string) |
| `orders[0].product_name` | `product_name` | Custom property |
| `orders[0].price_in_cents / 100` | `amount` | Standard property (converted to dollars as string) |
| `event.timestamp` | `last_payment_date` | Custom property (set on payment.succeeded) |

## Event-to-Stage Mapping

| Webhook Event | Deal Stage | Stage ID |
|--------------|------------|----------|
| `checkout.abandoned` | checkoutincomplete | 1302219587 |
| `order.created` | activesubscriber | 1302219588 |
| `subscription.canceled` | subscriptionended | 1302219589 |

## Notes

- **Synthetic Email**: Patients (minors) don't have real emails in the webhook payload. The lambda generates a synthetic email using the pattern `{firstname}.{lastname}+p{patient_id}@meadowbio.com`
- **State Validation**: HubSpot only accepts valid US state abbreviations (AL, AK, AZ... WY). International states will cause validation errors.
- **Price Conversion**: Portal sends prices in cents (`price_in_cents`). HubSpot stores as dollars (divide by 100 and convert to string).
- **Boolean Conversion**: HubSpot custom properties for booleans must be strings "true" or "false", not actual boolean values.
- **External IDs**: Used to link objects across systems:
  - `family_external_id` = `parent_external_id` (same value, links Company to Guardian)
  - `patient_external_id` links Deal to Patient
  - `guardian_external_id` links Patient to Guardian
