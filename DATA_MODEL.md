# HubSpot Data Model - Meadow Bio

## Overview

This document explains the HubSpot data model used for tracking patients through their journey from registration to active subscription.

## Core Principle: ONE Deal Per Patient

**Key Concept:** Each patient has exactly ONE deal that represents their entire journey through the system. The deal moves through pipeline stages as the patient progresses, rather than creating multiple deals for different events.

## Objects and Their Purposes

### Contacts (2 per patient)

1. **Guardian Contact** - The parent/guardian (real email)
   - Properties: email, firstname, lastname, phone, state
   - Custom: `parent_external_id`, `patient_relationship="parent"`

2. **Patient Contact** - The minor patient (synthetic email)
   - Synthetic email: `{firstname}.{lastname}+p{patient_id}@meadowbio.com`
   - Custom: `patient_external_id`, `is_minor=true`, `guardian_external_id`

### Deal (1 per patient)

**Purpose:** Track the patient's journey through the entire lifecycle using pipeline stages

**Pipeline Stages:**
- `registration` - Patient registered, deal created
- `intake_in_progress` - Patient started intake questionnaire
- `intake_abandoned` - Patient abandoned intake (needs follow-up)
- `checkout_abandoned` - Patient started checkout but didn't complete
- `active_subscription` - Order created, patient is active subscriber
- `closedlost` - Subscription canceled (churned)

**Key Properties:**
- `patient_external_id` - Links deal to patient (set at creation)
- `subscription_external_id` - Order ID (set when order created)
- `mrr` - Monthly recurring revenue
- `last_payment_date` - Last successful payment
- `next_refill_date` - Next scheduled refill
- `product_name` - Treatment product name

### Tickets (created on-demand for issues)

**Purpose:** Track operational issues that need resolution

**Use Cases:**
1. **Payment Failed** - Customer needs to update payment method
   - Category: `BILLING_ISSUE`
   - Priority: `HIGH` (if multiple failures) or `MEDIUM`
   - Associated to guardian contact

2. **Subscription Canceled** - Track churn reason, potential win-back
   - Category: `GENERAL_INQUIRY`
   - Priority: `MEDIUM`
   - Associated to guardian contact

## Event Flow

### Registration Flow

```
Event: patient.registered
├─ lambda_contact
│  ├─ Create guardian contact (if not exists)
│  ├─ Create patient contact (if not exists)
│  ├─ Associate guardian ↔ patient
│  ├─ Create deal in "registration" stage
│  └─ Associate deal with both contacts
```

### Intake Flow

```
Event: intake.started
└─ lambda_deal
   ├─ Find deal by patient_external_id
   └─ Move to "intake_in_progress" stage

Event: intake.abandoned
└─ lambda_deal
   ├─ Find deal by patient_external_id
   └─ Move to "intake_abandoned" stage
```

### Checkout Flow

```
Event: checkout.abandoned
└─ lambda_deal
   ├─ Find deal by patient_external_id
   └─ Move to "checkout_abandoned" stage

Event: order.created
└─ lambda_deal
   ├─ Find deal by patient_external_id
   ├─ Move to "active_subscription" stage
   ├─ Set subscription_external_id = order.external_id
   ├─ Set mrr, product_name, amount
   └─ (Now deal can be found by subscription_external_id for future events)
```

### Active Subscription Flow

```
Event: payment.succeeded
└─ lambda_deal
   ├─ Find deal by subscription_external_id
   └─ Update last_payment_date, mrr

Event: payment.failed
└─ lambda_ticket
   ├─ Find guardian contact
   ├─ Create ticket (BILLING_ISSUE)
   └─ Associate ticket with guardian

Event: subscription.canceled
└─ lambda_ticket
   ├─ Find guardian contact
   ├─ Create ticket (GENERAL_INQUIRY) with cancellation reason
   ├─ Associate ticket with guardian
   ├─ Find deal by subscription_external_id
   └─ Move deal to "closedlost" stage
```

## Associations

```
Guardian Contact ←→ Patient Contact (parent/child association)
       ↓                    ↓
       └──── Deal ──────────┘
              ↓
         (moves through stages)
              ↓
          Ticket (when issues occur)
              ↓
       Guardian Contact
```

## Why This Model?

### Deal as Journey Tracker
- **HubSpot's reporting** is built around deals (funnel, conversion rates, forecasting)
- **Pipeline stages** perfectly map to patient journey phases
- **Revenue reporting** (MRR) ties naturally to deals
- **Stage-to-stage conversion** metrics available out of the box

### Tickets for Operational Issues
- **SLA tracking** - Tickets have built-in resolution tracking
- **Assignment** - Can assign to customer success team
- **Clean separation** - "Open issues" queue vs. "journey progress" view
- **Workflow automation** - HubSpot workflows can trigger on ticket creation

### One Deal vs. Multiple Deals
- **ONE deal per patient** = Clear lifecycle view, accurate conversion rates
- Multiple deals = Inflated deal count, confusing revenue attribution, harder to track patient journey

## Example: Complete Patient Journey

```
1. Sarah Johnson registers her son Tommy
   └─ Creates: Guardian contact, Patient contact, Deal in "registration"

2. Tommy starts intake questionnaire
   └─ Updates: Deal → "intake_in_progress"

3. Tommy abandons intake at 60%
   └─ Updates: Deal → "intake_abandoned"
   └─ HubSpot workflow sends reminder email to Sarah

4. Tommy completes intake and goes to checkout
   └─ Updates: Deal → "checkout_abandoned" (if they don't complete)

5. Order created for Autism Treatment subscription
   └─ Updates: Deal → "active_subscription"
   └─ Sets: subscription_external_id=101, mrr=$99

6. Monthly payment succeeds
   └─ Updates: Deal last_payment_date, mrr

7. Payment fails (card expired)
   └─ Creates: Ticket "Payment Failed - Sarah Johnson"
   └─ HubSpot workflow sends email to Sarah to update card

8. Sarah cancels subscription (reason: cost)
   └─ Creates: Ticket "Subscription Canceled - Sarah Johnson"
   └─ Updates: Deal → "closedlost"
   └─ HubSpot workflow triggers win-back campaign
```

## Searching for Records

### Find Deal by Patient ID
```python
deal = hubspot.search_deal_by_patient_id("43")
# Used when patient is still progressing through journey
# Events: intake.started, intake.abandoned, checkout.abandoned, order.created
```

### Find Deal by Subscription ID
```python
deal = hubspot.search_deal_by_external_id("101")
# Used after subscription created (order.created event)
# Events: payment.succeeded, subscription.canceled, refill updates
```

### Find Contact by External ID
```python
contact = hubspot.search_contact_by_external_id("420392-")
# Used to find guardian or patient contacts
# Events: All events need to find contacts
```

## Dashboard & Reporting

With this model, HubSpot provides:

1. **Conversion Funnel**
   - Registration → Intake → Checkout → Active Subscription
   - See drop-off rates at each stage

2. **Revenue Metrics**
   - MRR by cohort
   - Churn rate (% moving to closedlost)
   - LTV per patient

3. **Operational Metrics**
   - Open tickets by category
   - Average resolution time
   - Payment failure rate

4. **Workflow Automation**
   - Abandoned intake → Send reminder email
   - Payment failed → Notify customer success team
   - Subscription canceled → Trigger win-back sequence
