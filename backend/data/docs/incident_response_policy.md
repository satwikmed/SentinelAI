# Incident Response Policy — Acme Corp

## 1. Objective
Define roles, timelines, and escalation paths for security incidents and data breaches.

## 2. Definitions
- **Security Incident**: Unauthorized access, malware, denial of service, or policy violation
  affecting systems or data.
- **Personal Data Breach**: A security incident leading to accidental or unlawful destruction,
  loss, alteration, or unauthorized disclosure of personal data.

## 3. Reporting Timelines
- Suspected security incidents must be reported to the Security Operations Center (SOC)
  within **1 hour** of discovery.
- Confirmed breaches affecting personal data must be escalated to Legal within **24 hours**
  for regulatory notification assessment (including GDPR 72-hour obligations where applicable).

## 4. Severity Levels
| Severity | Description | Response SLA |
|----------|-------------|--------------|
| SEV-1 | Active breach / customer impact | Immediate war room |
| SEV-2 | Confirmed compromise, contained | 4 hours |
| SEV-3 | Suspicious activity | 1 business day |

## 5. Roles
- **Incident Commander**: Owns coordination and communication.
- **SOC Analyst**: Triage and containment.
- **Legal / Privacy**: Regulatory assessment and external notifications.
- **Communications**: Customer and media messaging when required.

## 6. Evidence Preservation
Logs, disk images, and relevant artifacts must be preserved before remediation that
would destroy forensic evidence, except when immediate containment is required to
stop active exfiltration.

## 7. Post-Incident Review
SEV-1 and SEV-2 incidents require a written post-incident review within 10 business days.
