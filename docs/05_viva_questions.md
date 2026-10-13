# Likely viva questions (with short answers)

1. **Why serverless?** Bursty campus traffic; pay-per-request; no servers to patch; auto-scales. (Cost: ~94% cheaper than always-on for 5,000 users.)
2. **Which parts are IaaS/PaaS/SaaS?** SaaS: Cognito, Comprehend, SNS/SES. PaaS/FaaS: Lambda, API Gateway, DynamoDB, S3, CloudFront. IaaS: none by design.
3. **How is an admin different from a student?** Cognito `Admins` group in the JWT; Lambda checks it server-side, so hiding a button is not the security.
4. **How do you stop a student reading someone else's complaint?** `_fetch` compares `userId` with the token `sub`; non-owners get 404.
5. **How are uploads secured?** Presigned POST, type whitelist, 5 MB limit, key prefixed with the user id, private bucket, 5-minute download URLs.
6. **What is a cold start and how did you measure it?** First invocation after idle initialises the runtime; seen in the first load-test stage p99; fix = provisioned concurrency.
7. **How does it scale?** Each concurrent request gets its own Lambda environment; DynamoDB on-demand; CloudFront for static content; limited only by account quotas and our throttle.
8. **Why DynamoDB and not MySQL?** Key-based access patterns, no connection pooling issues with Lambda, auto-scaling. Trade-off: no joins.
9. **How does auto-tagging work?** Whole-word keyword scoring for category, urgency words for priority, Comprehend sentiment escalates priority if strongly negative; falls back safely if AI fails.
10. **What happens if SNS/SES fails?** The complaint is already saved; notifications come from a DynamoDB Stream with retries (max 2), failures are logged.
11. **How do you handle disaster recovery?** DynamoDB PITR, S3 durability (11 nines) + lifecycle, IaC redeploys in minutes; multi-region would be next.
12. **How is cost controlled?** Billing budget alert, on-demand billing, API throttle, S3 lifecycle, teardown script.
13. **What would you improve?** MFA, WAF, antivirus scan on uploads, multi-language, analytics, multi-tenant.
14. **Why HTTP API instead of REST API?** Cheaper, faster, native JWT authorizer; we do not need API keys/usage plans.
15. **Where is the infrastructure code?** `template.yaml` (AWS SAM -> CloudFormation); `sam deploy` creates every resource.
