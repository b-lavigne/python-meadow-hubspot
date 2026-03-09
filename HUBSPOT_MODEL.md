# HubSpot Data Model - Simple

## What Each Object Is

| Real World | HubSpot Object | Example |
|------------|----------------|---------|
| **Family/Household** | Company | "The Johnson Family" |
| **Mom/Dad** | Contact | Sarah Johnson |
| **Kid/Patient** | Contact | Tommy Johnson |
| **Kid's Journey** | Deal | "Tommy Johnson — Patient Journey" |

## Pipeline: Patient Journey (ID: 869949826)

| Stage Name | Stage ID | Status | Trigger Event |
|------------|----------|--------|---------------|
| Family Registered | 1302219584 | Open | NOT USED - no deal at registration |
| Intake In Progress | 1302219585 | Open | NOT USED - no intake flow |
| Intake Incomplete | 1302219586 | Lost | NOT USED - no intake flow |
| Checkout Incomplete | 1302219587 | Lost | checkout.abandoned |
| **Active Subscriber** | **1302219588** | **Won** | order.created |
| Subscription Ended | 1302219589 | Lost | subscription.canceled |

## Associations

```
Company (Family: "The Johnson Family")
    ↓
    ├─ Contact (Sarah Johnson - guardian)
    ├─ Contact (Tommy Johnson - patient)
    └─ Deal ("Tommy Johnson — Patient Journey")
```

## Lambda Functions

| Lambda | Creates | Event |
|--------|---------|-------|
| **lambda_registration** | Company (Family), Guardian Contact, Patient Contact | patient.registered |
| **lambda_deal** | Creates/Updates Deal | checkout.abandoned, order.created, payment.succeeded, subscription.canceled |

## What Gets Created When

```
Event: patient.registered
    ↓
lambda_registration → Creates:
    - Company: "The Moore Family"
    - Guardian Contact: Frank Moore
    - Patient Contact: Ashley Moore (synthetic email: ashley.moore+p57@meadowbio.com)
    - Associations: Company ↔ Guardian, Company ↔ Patient, Guardian ↔ Patient

Event: order.created
    ↓
lambda_deal → Creates Deal (if doesn't exist) OR Updates existing Deal:
    - Deal: "Ashley Moore — Patient Journey"
    - Stage: activesubscriber (1302219588)
    - Properties: subscription_external_id, mrr, product_name, amount
    - Associations: Deal ↔ Guardian, Deal ↔ Patient, Deal ↔ Company

Event: checkout.abandoned
    ↓
lambda_deal → Creates Deal (if doesn't exist) with stage=checkoutincomplete (1302219587)

Event: payment.succeeded
    ↓
lambda_deal → Updates Deal: last_payment_date, mrr

Event: subscription.canceled
    ↓
lambda_deal → Updates Deal stage to subscriptionended (1302219589)
```

## Custom Properties

| Object | Property | Purpose |
|--------|----------|---------|
| Company | family_external_id | Link to guardian external_id |
| Contact (Guardian) | parent_external_id | Link to portal |
| Contact (Patient) | patient_external_id | Link to portal |
| Deal | patient_external_id | Link to patient |
| Deal | subscription_external_id | Link to order (set when order created) |
| Deal | mrr | Monthly recurring revenue |
