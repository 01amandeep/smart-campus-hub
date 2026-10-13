# 1. Problem Analysis & Cloud Design  (2 marks)

## 1.1 Problem identification
In most colleges, complaints (broken Wi-Fi, hostel water, lab systems) and notices (exam dates, holidays) travel through
WhatsApp groups, paper letters and word of mouth. Consequences:

| Pain point | Effect |
|---|---|
| No single record of complaints | Issues are forgotten, repeated, or never reach the right department |
| No priority or category | A short-circuit hazard is handled like a request for a new bench |
| No status tracking | Students cannot see whether anyone is working on their issue |
| Notices buried in chat groups | Students miss deadlines and events |
| Evidence (photos) lost in chats | Admins cannot verify problems |
| No analytics | Management cannot see which area has the most problems |

**Proposed solution:** *Smart Campus Hub* - a cloud-hosted web platform where students file complaints (with photo
proof), the system **auto-categorises and prioritises** them using rules + Amazon Comprehend sentiment analysis, admins
manage status, and notices are published once and e-mailed to everyone.

## 1.2 Requirements

### Functional
| ID | Requirement |
|---|---|
| FR1 | Users sign up with e-mail verification and log in securely |
| FR2 | Students submit complaints with title, location, description and optional photo/PDF |
| FR3 | System auto-assigns category, priority and sentiment to each complaint |
| FR4 | Students view only their own complaints and live status |
| FR5 | Admins view all complaints, filter by status, and update status with a note |
| FR6 | Admins publish/delete notices; all users can read them |
| FR7 | Admins are alerted (e-mail) on each new complaint; notices are e-mailed to subscribers |
| FR8 | Students are e-mailed when their complaint status changes (optional SES) |

### Non-functional
| Attribute | Target | How the design meets it |
|---|---|---|
| Availability | >= 99.9% | Managed multi-AZ services (Lambda, DynamoDB, S3, CloudFront) |
| Scalability | 500 -> 50,000 users with no re-design | Serverless, on-demand capacity, CDN |
| Performance | p95 API latency < 500 ms | HTTP API + Lambda 256 MB + DynamoDB single-digit-ms reads, CDN for static files |
| Security | Authenticated, least privilege, encrypted | Cognito JWT, per-function IAM, SSE at rest, HTTPS only |
| Cost | Pay only for use; near-zero when idle | Pay-per-request billing everywhere |
| Maintainability | Reproducible one-command deploy | Infrastructure as code (AWS SAM / CloudFormation) |
| Observability | Metrics, alarms, traces | CloudWatch dashboard + alarms, X-Ray |

## 1.3 Architecture
See `docs/architecture.png` (also in the report).

**Request flow:** Browser -> CloudFront -> S3 (static site) -> user signs in with **Cognito** -> JWT sent to
**API Gateway** (validates token) -> **Lambda** -> **DynamoDB** / **S3** / **Comprehend** -> DynamoDB Stream -> **Lambda** -> **SNS/SES**.

## 1.4 Selection of IaaS / PaaS / SaaS (justification)

| Component | Service | Model | Why this and not the alternative |
|---|---|---|---|
| Authentication | Amazon Cognito | **SaaS** | Building password storage, MFA and e-mail verification ourselves is risky and slow |
| AI tagging | Amazon Comprehend | **SaaS** (AI) | Ready-made sentiment API; no ML team needed |
| Notifications | SNS, SES | **SaaS** | Managed e-mail delivery, no mail server |
| Compute | AWS Lambda | **PaaS / FaaS** | No servers to patch; scales per request; free tier covers a college pilot |
| API layer | API Gateway (HTTP API) | **PaaS** | Built-in JWT auth, throttling, CORS; cheaper than REST API |
| Database | DynamoDB (on-demand) | **PaaS** | Key-value access patterns, auto-scaling, no capacity planning |
| File storage | Amazon S3 | **PaaS** | 99.999999999% durability, lifecycle rules, presigned uploads |
| Delivery | CloudFront | **PaaS** | HTTPS, caching, low latency across India |
| Monitoring | CloudWatch, X-Ray | **PaaS** | Native metrics, alarms, tracing |
| Virtual machines | *(none)* | **IaaS** | Deliberately avoided: EC2 would need patching, scaling groups and 24x7 cost |

**Why serverless instead of EC2?** Complaint traffic is bursty (busy after exams, quiet at night). Always-on servers
would sit idle most of the time (see cost analysis: ~94% cheaper for a 5,000-user college).

## 1.5 Data model
**Complaints** (PK `complaintId`; GSI `UserIndex` userId+createdAt; GSI `StatusIndex` status+createdAt)
`userId, userEmail, title, description, location, category, priority, sentiment, status, adminNote, attachmentKey, createdAt, updatedAt`

**Notices** (PK `pk="NOTICE"`, SK `createdAt#id` -> newest first without scans)
`title, content, audience, postedBy, createdAt`

Access patterns: *my complaints* -> UserIndex; *admin by status* -> StatusIndex; *latest notices* -> single Query. No table scans anywhere.

## 1.6 API design
| Method & path | Who | Purpose |
|---|---|---|
| POST /complaints | any user | Create + auto-tag |
| GET /complaints | any user | My complaints |
| GET /complaints?scope=all&status= | admin | All complaints |
| GET /complaints/{id} | owner/admin | Detail + presigned attachment URL |
| PATCH /complaints/{id} | admin | Change status, add note |
| POST /uploads | any user | Presigned S3 POST (<= 5 MB, png/jpg/pdf) |
| GET /notices | any user | Notice board |
| POST /notices, DELETE /notices/{id} | admin | Publish / remove |

## 1.7 Assumptions & scope
Single AWS region (ap-south-1 Mumbai for low latency in India); English-language complaints; e-mail as the notification channel;
pilot of 500-5,000 users. Out of scope: mobile app, multi-college tenancy, payment.
