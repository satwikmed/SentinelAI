# Information Security Policy — Acme Corp (Internal)

## 1. Purpose
This policy establishes requirements for protecting Acme Corp information assets,
including customer data, intellectual property, and employee records.

## 2. Scope
Applies to all employees, contractors, and systems that process, store, or transmit
Acme Corp data.

## 3. Classification
Data is classified as Public, Internal, Confidential, or Restricted.
Restricted data includes government identifiers, payment card data, and authentication secrets.

## 4. Data Retention
### 4.1 Active Accounts
Customer data for active accounts is retained for the duration of the business relationship.

### 4.2 Post-Termination Retention
Customer data must be retained for a maximum of **36 months** after contract termination,
unless a longer period is required by applicable law. Backups follow the same retention
schedule and must be purged within 45 days of the primary deletion event.

### 4.3 Legal Holds
Retention clocks pause when a documented legal hold is issued by the Legal department.

## 5. Access Control
Access to Confidential and Restricted data requires role-based authorization reviewed quarterly.
Shared accounts are prohibited for production systems.

## 6. Encryption
Data in transit must use TLS 1.2+. Data at rest for Confidential and Restricted
classifications must use AES-256 or equivalent.

## 7. Acceptable Use
Employees must not upload customer data to unsanctioned generative AI tools.
All AI system usage for customer data must go through approved enterprise gateways
with audit logging enabled.
