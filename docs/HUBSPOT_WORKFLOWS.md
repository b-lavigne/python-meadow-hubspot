# Meadow Bio - HubSpot Workflow Configuration Guide

## Architecture Overview

Your API sets contact/deal properties → HubSpot workflows trigger automatically on property changes → Emails and actions execute without any code on your side.

```
┌─────────────────────┐     ┌──────────────────────┐     ┌─────────────────────┐
│   Patient Portal    │────▶│   Your Lambda API    │────▶│      HubSpot        │
│   (Meadow Bio)      │     │  (Webhook Handler)   │     │   (Automations)     │
└─────────────────────┘     └──────────────────────┘     └─────────────────────┘
         │                            │                            │
   User abandons               API updates:                  Workflow triggers:
   intake form            intake_status = abandoned         "Send recovery email"
```

---

## Step 1: Create Custom Properties

Before building workflows, create these properties in HubSpot → Settings → Properties → Contact Properties:

### Contact Properties

| Property Name | Internal Name | Type | Options |
|--------------|---------------|------|---------|
| Registration Status | `registration_status` | Dropdown | `started`, `complete` |
| Intake Status | `intake_status` | Dropdown | `not_started`, `in_progress`, `complete`, `abandoned` |
| Intake Completion % | `intake_completion_pct` | Number | 0-100 |
| Intake Abandoned At | `intake_abandoned_at` | Date/Time | — |
| Payment Status | `payment_status` | Dropdown | `active`, `failed`, `pending` |
| Subscription Status | `subscription_status` | Dropdown | `none`, `active`, `paused`, `canceled` |
| Patient External ID | `patient_external_id` | Single-line text | Portal patient ID |
| Parent External ID | `parent_external_id` | Single-line text | Links parent↔patient |
| Patient Relationship | `patient_relationship` | Dropdown | `self`, `parent`, `guardian` |
| Cancellation Reason | `cancellation_reason` | Dropdown | `cost`, `side_effects`, `not_effective`, `other` |

### Deal Properties

| Property Name | Internal Name | Type |
|--------------|---------------|------|
| Next Refill Date | `next_refill_date` | Date |
| Last Payment Date | `last_payment_date` | Date |
| MRR | `mrr` | Number (currency) |
| Subscription External ID | `subscription_external_id` | Single-line text |

---

## Step 2: Create Deal Pipeline

**Pipeline Name:** Patient Journey

| Stage | Internal ID | Probability |
|-------|-------------|-------------|
| Registration Started | `registration_started` | 10% |
| Intake In Progress | `intake_in_progress` | 20% |
| Intake Complete | `intake_complete` | 40% |
| Checkout Started | `checkout_started` | 60% |
| Checkout Abandoned | `checkout_abandoned` | 30% |
| Closed Won | `closedwon` | 100% |
| Active Subscription | `active_subscription` | 100% |
| Churned | `churned` | 0% |

---

## Step 3: Workflow Configurations

### Workflow 1: Abandoned Intake Recovery

**Purpose:** Re-engage parents who started but didn't complete the intake questionnaire

**Trigger:**
- Property: `intake_status` is equal to `abandoned`
- AND: `intake_completion_pct` is greater than `20`

**Enrollment Settings:**
- Re-enrollment: OFF (once per contact per workflow)
- Suppress by: Contact has completed goal (intake_status = complete)

```
┌─────────────────────────────────────────────────────────────────┐
│  TRIGGER: intake_status = abandoned AND intake_completion_pct > 20
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  DELAY: 2 hours                                                  │
│  (Allows user to return on their own)                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  IF/THEN BRANCH: Check if still abandoned                       │
│  ├─ IF intake_status = abandoned:                               │
│  │      → SEND EMAIL: "Almost There" (Email 1)                  │
│  └─ ELSE:                                                       │
│         → END (they completed)                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  DELAY: 24 hours                                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  IF/THEN BRANCH: Check if still abandoned                       │
│  ├─ IF intake_status = abandoned:                               │
│  │      → SEND EMAIL: "Questions? We're Here" (Email 2)         │
│  └─ ELSE:                                                       │
│         → END                                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  DELAY: 48 hours                                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  IF/THEN BRANCH: Final attempt                                  │
│  ├─ IF intake_status = abandoned:                               │
│  │      → SEND EMAIL: "Last Chance" (Email 3)                   │
│  │      → CREATE TASK: "Follow up on abandoned intake"          │
│  │        Assigned to: Care Coordinator                         │
│  │        Due: 1 day                                            │
│  └─ ELSE:                                                       │
│         → END                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Email Templates:**

**Email 1 - "Almost There" (2 hours after abandonment)**
```
Subject: Tommy's intake is {{intake_completion_pct}}% complete

Hi {{contact.firstname}},

You're almost there! Tommy's intake form is {{intake_completion_pct}}% complete.

Finishing takes just a few more minutes, and our care team will review 
everything within 24 hours.

[Continue Intake →] (link to portal)

Questions? Just reply to this email.

The Meadow Bio Team
```

**Email 2 - "Questions? We're Here" (24 hours)**
```
Subject: Need help finishing Tommy's intake?

Hi {{contact.firstname}},

We noticed you haven't had a chance to complete Tommy's intake yet.

Common questions we hear:
• "How long does this take?" → Usually 5-10 more minutes
• "What happens next?" → A provider reviews within 24 hours
• "Is this secure?" → Yes, we're fully HIPAA compliant

[Continue Where You Left Off →]

Or call us: (555) 123-4567

Best,
The Meadow Bio Care Team
```

**Email 3 - "Last Chance" (72 hours)**
```
Subject: We're holding Tommy's spot

Hi {{contact.firstname}},

Just a quick note - Tommy's intake has been waiting for 3 days. 
We'd hate for you to have to start over.

If something came up or you have concerns, we're here to help. 

[Complete Intake Now →]

Or reply to this email and we'll reach out.

Take care,
The Meadow Bio Team
```

---

### Workflow 2: Abandoned Checkout Recovery

**Purpose:** Recover patients who completed intake but didn't finish checkout

**Trigger:**
- Deal Stage is equal to `Checkout Abandoned`

**Enrollment Settings:**
- Based on: Deal
- Re-enrollment: OFF

```
┌─────────────────────────────────────────────────────────────────┐
│  TRIGGER: Deal enters "Checkout Abandoned" stage                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  DELAY: 1 hour                                                  │
│  (User may have gotten distracted, give time to return)         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  IF/THEN: Check if deal still in Checkout Abandoned             │
│  ├─ IF yes:                                                     │
│  │      → SEND EMAIL: "Your care plan is ready" (Email 1)       │
│  └─ ELSE:                                                       │
│         → END                                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  DELAY: 24 hours                                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  IF/THEN: Check if deal still in Checkout Abandoned             │
│  ├─ IF yes:                                                     │
│  │      → SEND EMAIL: "Questions about pricing?" (Email 2)      │
│  └─ ELSE:                                                       │
│         → END                                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  DELAY: 48 hours                                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  IF/THEN: Final outreach                                        │
│  ├─ IF yes:                                                     │
│  │      → SEND EMAIL: "Special offer" (Email 3)                 │
│  │      → CREATE TASK: "Call checkout abandonment"              │
│  └─ ELSE:                                                       │
│         → END                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Email Templates:**

**Email 1 - "Your care plan is ready" (1 hour)**
```
Subject: Tommy's care plan is waiting

Hi {{contact.firstname}},

Great news - a provider has reviewed Tommy's intake and prepared 
a personalized care plan.

Your next step: Complete checkout to get started.

[Complete Checkout →]

Questions? We're here to help.
```

**Email 2 - "Questions about pricing?" (24 hours)**
```
Subject: Quick question about Tommy's care

Hi {{contact.firstname}},

I noticed you haven't finished checkout for Tommy's care plan.

A few things that might help:
• Our subscription includes unlimited messaging with your provider
• Most families see improvement within 4-6 weeks  
• You can pause or cancel anytime

If cost is a concern, reply and we can discuss options.

[Continue to Checkout →]
```

**Email 3 - "Special offer" (72 hours)**
```
Subject: 10% off Tommy's first month

Hi {{contact.firstname}},

We'd love to get Tommy started on his care plan.

Use code FIRST10 for 10% off your first month.

[Claim Your Discount →]

This offer expires in 48 hours.

The Meadow Bio Team
```

---

### Workflow 3: Welcome - Registration Complete

**Purpose:** Onboard new patients after successful registration

**Trigger:**
- Property: `registration_status` becomes `complete`

**Enrollment Settings:**
- Re-enrollment: OFF

```
┌─────────────────────────────────────────────────────────────────┐
│  TRIGGER: registration_status = complete                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  IMMEDIATELY                                                    │
│  → SEND EMAIL: "Welcome to Meadow Bio"                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  DELAY: 2 days                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  IF/THEN: Check subscription status                             │
│  ├─ IF subscription_status = active:                            │
│  │      → SEND EMAIL: "Getting the most from your care"         │
│  └─ ELSE:                                                       │
│         → END (other workflows handle non-subscribers)          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  DELAY: 5 days                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  → SEND EMAIL: "How to message your provider"                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  DELAY: 14 days                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  → SEND EMAIL: "Check-in: How's everything going?"              │
│  → SET PROPERTY: onboarding_complete = true                     │
└─────────────────────────────────────────────────────────────────┘
```

---

### Workflow 4: Payment Failed Recovery

**Purpose:** Recover failed payments before they cause churn

**Trigger:**
- Property: `payment_status` becomes `failed`

**Enrollment Settings:**
- Re-enrollment: ON (allow re-enrollment after 30 days)

```
┌─────────────────────────────────────────────────────────────────┐
│  TRIGGER: payment_status = failed                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  IMMEDIATELY                                                    │
│  → SEND EMAIL: "Action needed: Update payment"                  │
│  → CREATE TICKET: "Payment failed - {{contact.email}}"          │
│       Pipeline: Support                                         │
│       Priority: High                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  DELAY: 3 days                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  IF/THEN: Check if payment still failed                         │
│  ├─ IF payment_status = failed:                                 │
│  │      → SEND EMAIL: "Care interrupted - update card"          │
│  └─ ELSE:                                                       │
│         → CLOSE TICKET                                          │
│         → END                                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  DELAY: 4 days (7 days total)                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  IF/THEN: Final warning                                         │
│  ├─ IF payment_status = failed:                                 │
│  │      → SEND EMAIL: "Account suspension warning"              │
│  │      → CREATE TASK: "Call about payment - final attempt"     │
│  │        Assigned to: Billing Team                             │
│  └─ ELSE:                                                       │
│         → CLOSE TICKET                                          │
│         → END                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Email Templates:**

**Email 1 - Immediate**
```
Subject: Action needed: Update your payment method

Hi {{contact.firstname}},

We couldn't process your recent payment for Tommy's care subscription.

To avoid any interruption in care:

[Update Payment Method →]

If you have questions, just reply to this email.
```

**Email 2 - Day 3**
```
Subject: Tommy's care may be interrupted

Hi {{contact.firstname}},

We still haven't been able to process your payment. Tommy's care 
will be paused if we don't hear from you.

Common fixes:
• Card expired? Update to your new card
• Insufficient funds? We can try again in a few days
• Changed banks? Add your new payment method

[Update Payment Now →]

Or call us: (555) 123-4567
```

**Email 3 - Day 7**
```
Subject: Final notice: Subscription will be paused

Hi {{contact.firstname}},

This is a final notice that Tommy's subscription will be paused 
tomorrow unless we can process payment.

If you're experiencing financial difficulty, please reach out - 
we have options to help.

[Update Payment →]

Or call: (555) 123-4567
```

---

### Workflow 5: Subscription Canceled - Win-back

**Purpose:** Attempt to win back canceled subscribers

**Trigger:**
- Property: `subscription_status` becomes `canceled`

**Enrollment Settings:**
- Re-enrollment: OFF
- Suppress: Contact has re-subscribed (subscription_status = active)

```
┌─────────────────────────────────────────────────────────────────┐
│  TRIGGER: subscription_status = canceled                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  DELAY: 7 days                                                  │
│  (Give space, don't be pushy)                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  IF/THEN BRANCH: Personalize by cancellation reason             │
│                                                                 │
│  ├─ IF cancellation_reason = "cost":                            │
│  │      → SEND EMAIL: "We've adjusted our pricing"              │
│  │                                                              │
│  ├─ IF cancellation_reason = "not_effective":                   │
│  │      → SEND EMAIL: "New treatment options available"         │
│  │                                                              │
│  ├─ IF cancellation_reason = "side_effects":                    │
│  │      → SEND EMAIL: "Alternative medications"                 │
│  │                                                              │
│  └─ ELSE:                                                       │
│         → SEND EMAIL: "We miss you" (generic)                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  DELAY: 14 days (21 days total)                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  IF subscription_status still = canceled:                       │
│  → SEND EMAIL: "Special offer to return"                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  DELAY: 9 days (30 days total)                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  IF subscription_status still = canceled:                       │
│  → SEND EMAIL: "We're still here when you need us"              │
│  → SET PROPERTY: winback_attempted = true                       │
└─────────────────────────────────────────────────────────────────┘
```

---

### Workflow 6: Refill Reminder

**Purpose:** Remind patients about upcoming medication refills

**Trigger:**
- Deal Property: `next_refill_date` is less than 7 days from now
- AND: Deal Stage is `Active Subscription`

**Enrollment Settings:**
- Re-enrollment: ON (every 30 days minimum)

```
┌─────────────────────────────────────────────────────────────────┐
│  TRIGGER: next_refill_date < 7 days away                        │
│           AND Deal Stage = Active Subscription                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  SEND EMAIL to associated contact:                              │
│  "Your refill is coming up"                                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  DELAY: 5 days                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  IF/THEN: Check if refill date is tomorrow or past              │
│  ├─ IF next_refill_date <= 1 day:                               │
│  │      → SEND EMAIL: "Refill ships tomorrow"                   │
│  └─ ELSE:                                                       │
│         → END                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

### Workflow 7: Subscription Restarted - Welcome Back

**Purpose:** Re-onboard returning subscribers

**Trigger:**
- Property: `subscription_status` becomes `active`
- AND: Contact has property `winback_attempted` = true (they previously churned)

```
┌─────────────────────────────────────────────────────────────────┐
│  TRIGGER: subscription_status = active                          │
│           AND winback_attempted = true                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  IMMEDIATELY                                                    │
│  → SEND EMAIL: "Welcome back!"                                  │
│  → CLEAR PROPERTY: winback_attempted = false                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  DELAY: 3 days                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  → SEND EMAIL: "What's new since you've been gone"              │
│  → CREATE TASK: "Check in with returning patient"               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Summary: Event → Property → Workflow

| Event from Portal | Property Changed | Workflow Triggered |
|-------------------|------------------|-------------------|
| `patient.registration_completed` | `registration_status = complete` | Welcome - Registration Complete |
| `intake.abandoned` | `intake_status = abandoned` | Abandoned Intake Recovery |
| `checkout.abandoned` | Deal stage = "Checkout Abandoned" | Abandoned Checkout Recovery |
| `checkout.completed` | Deal stage = "Closed Won" | (No workflow - success path) |
| `subscription.restarted` | `subscription_status = active` | Subscription Restarted - Welcome Back |
| `subscription.canceled` | `subscription_status = canceled` | Subscription Canceled - Win-back |
| `subscription.refill_pushed` | `next_refill_date` updated | (Refill Reminder adjusts automatically) |
| `payment.succeeded` | `payment_status = active` | (Clears failed payment workflow) |
| `payment.failed` | `payment_status = failed` | Payment Failed Recovery |

---

## Implementation Checklist

### Phase 1: Setup (Day 1)
- [ ] Create all custom Contact properties
- [ ] Create all custom Deal properties
- [ ] Create Deal Pipeline with stages
- [ ] Test property creation in sandbox

### Phase 2: Core Workflows (Days 2-3)
- [ ] Build Abandoned Intake Recovery workflow
- [ ] Build Abandoned Checkout Recovery workflow
- [ ] Build Payment Failed Recovery workflow
- [ ] Create email templates for each workflow

### Phase 3: Growth Workflows (Days 4-5)
- [ ] Build Welcome - Registration Complete workflow
- [ ] Build Subscription Canceled - Win-back workflow
- [ ] Build Refill Reminder workflow
- [ ] Build Subscription Restarted workflow

### Phase 4: Testing (Day 6)
- [ ] Test each workflow with sandbox contacts
- [ ] Verify emails render correctly
- [ ] Confirm workflows suppress properly when goals are met
- [ ] Test API property updates trigger workflows

### Phase 5: Go Live
- [ ] Enable workflows in production
- [ ] Monitor workflow performance dashboard
- [ ] Set up workflow error notifications