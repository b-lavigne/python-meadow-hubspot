# HubSpot Data Model - Simple

## What Each Object Is

| Real World | HubSpot Object | Example |
|------------|----------------|---------|
| **Family/Household** | Company | "The Johnson Family" |
| **Mom/Dad** | Contact | Sarah Johnson |
| **Kid/Patient** | Contact | Tommy Johnson |
| **Kid's Journey** | Deal | "Tommy Johnson — Patient Journey" |

## Pipeline: Patient Journey

| Stage Name | Status | Trigger Event |
|------------|--------|---------------|
| Family Registered | Open | patient.registered |
| Registration Complete | Open | patient.registration_completed |
| Intake In Progress | Open | intake.started |
| Intake Complete | Open | intake.completed |
| Consultation Scheduled | Open | consult.scheduled |
| Consultation Complete | Open | consult.completed |
| Checkout Started | Open | checkout.started |
| **Active Subscriber** | **Won** | checkout.completed / order.created |
| Intake Incomplete | Lost | intake.abandoned |
| Checkout Incomplete | Lost | checkout.abandoned |
| Subscription Ended | Lost | subscription.canceled |

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
| **lambda_company** | Company (Family) | patient.registered |
| **lambda_contact** | 2 Contacts + Deal | patient.registered |
| **lambda_deal** | Updates Deal stages | intake.started, checkout.abandoned, order.created, subscription.canceled, etc. |

## What Gets Created When

```
Event: patient.registered
    ↓
lambda_company → Create "The Johnson Family" (Company)
lambda_contact → Create Sarah (Contact), Tommy (Contact), Deal (stage=familyregistered)
    ↓
Associate: Company ↔ Contacts, Company ↔ Deal, Contacts ↔ Deal

Event: order.created
    ↓
lambda_deal → Move Deal to "activesubscriber" stage, set subscription_external_id, mrr

Event: subscription.canceled
    ↓
lambda_deal → Move Deal to "subscriptionended" stage
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
