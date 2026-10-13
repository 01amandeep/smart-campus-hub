# Security design (supports the Implementation marks)

| Layer | Control | Where in the project |
|---|---|---|
| Identity | Cognito user pool, e-mail verification, password policy (8+, upper, lower, number), `PreventUserExistenceErrors` | `template.yaml` -> UserPool |
| Authentication | API Gateway **JWT authorizer** validates issuer + audience on every request | `HttpApi.Auth` |
| Authorisation (RBAC) | `Admins` Cognito group -> checked **server-side** in Lambda (`get_user().is_admin`); UI hiding is only cosmetic | `backend/common.py`, `complaints.py` |
| Object-level access | Students can only read their own complaints; unknown and forbidden IDs both return 404 (no ID probing) | `complaints._fetch` |
| Least privilege IAM | Each Lambda gets only its table, its bucket prefix, `comprehend:DetectSentiment` | `Policies:` blocks |
| Encryption at rest | DynamoDB SSE, S3 SSE-S3 | tables and buckets |
| Encryption in transit | CloudFront redirects HTTP->HTTPS; API Gateway is HTTPS only | Distribution |
| No public buckets | Block Public Access ON; website served via CloudFront **Origin Access Control** | buckets |
| Safe uploads | Presigned POST with content-type whitelist (png/jpg/pdf) and 5 MB size limit; key forced under `attachments/<user-id>/`; download via 5-minute presigned URL | `presign_upload`, `get_one` |
| Input validation | Length checks, angle brackets stripped, frontend escapes all output (XSS) | `common.clean`, `app.js esc()` |
| Abuse protection | API throttling 100 rps / 200 burst | `DefaultRouteSettings` |
| Backup | DynamoDB point-in-time recovery; S3 lifecycle | tables, bucket |
| Audit & detection | CloudWatch alarms (Lambda errors, p95 latency), X-Ray traces, CloudTrail (enabled by default for management events) | CloudWatch |
| Token handling | Short-lived (60 min) tokens held in `sessionStorage`, refreshed with the refresh token | `app.js` |

**Known limitations (honest answer for viva):** tokens in `sessionStorage` are exposed if an XSS bug exists (mitigated by output escaping;
a production system could use the Cognito hosted UI with PKCE and HttpOnly cookies); attachments are not virus-scanned
(could add S3 -> Lambda -> ClamAV); MFA is not enforced (Cognito supports TOTP MFA); WAF is not attached (adds ~$5/month).
