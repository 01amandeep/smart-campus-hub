# 2. Implementation & Technical Execution  (4 marks)

Everything is defined in `template.yaml` (Infrastructure as Code). Follow the steps and **take a screenshot where marked 📸** -
those become the evidence in your report.

## Step 0 - Prerequisites (30 min)
1. AWS account (free tier) - enable MFA on the root user, create an IAM admin user, and **set a billing budget alert** (Billing -> Budgets -> $5).
2. Install: AWS CLI v2, AWS SAM CLI, Python 3.12, Git. (Windows: use Git Bash or WSL.)
3. `aws configure` with the IAM user's keys. Region: `ap-south-1`.
4. 📸 Screenshot: IAM user with MFA; budget alert.

## Step 1 - Run the unit tests locally
```bash
pip install pytest
python -m pytest tests -q          # 22 tests: classifier, sanitiser, role parsing, and API handlers with mocked AWS
```

## Step 2 - Deploy the whole stack (one command)
```bash
chmod +x scripts/*.sh
./scripts/deploy.sh your.email@college.edu ap-south-1
```
This builds the Lambdas, creates **19 resources** (Cognito, 2 DynamoDB tables, 2 S3 buckets, CloudFront, API Gateway, 3 Lambdas,
2 SNS topics, alarms, dashboard), then publishes the website and prints the URL.
**Click the two "Confirm subscription" e-mails from AWS** or you will not receive alerts.
📸 Screenshots: CloudFormation stack (CREATE_COMPLETE) + Resources tab.

## Step 3 - Configure each service (what to show/explain)
| Area | Where | What to screenshot / explain |
|---|---|---|
| **Networking** | CloudFront -> Distribution | HTTPS-only (redirect HTTP->HTTPS), HTTP/2, edge caching, Origin Access Control so S3 is never public |
| **Networking** | API Gateway -> Routes | 8 routes, CORS limited to your CloudFront domain, throttling 100 rps / 200 burst |
| **Storage** | S3 -> both buckets | *Block all public access = ON*, SSE-S3 encryption, lifecycle rule (Standard-IA after 30 days) |
| **Database** | DynamoDB -> Tables | On-demand billing, 2 GSIs, PITR (backups) ON, encryption ON, Streams ON |
| **Compute** | Lambda -> functions | Python 3.12, 256 MB, X-Ray ON, IAM role per function |
| **Auth** | Cognito -> User pool | E-mail verification, password policy, `Admins` group |
| **Messaging** | SNS -> Topics | Subscriptions confirmed |
| **Monitoring** | CloudWatch -> Dashboards | `smart-campus-smart-campus` dashboard + 2 alarms |

## Step 4 - Create users and an admin
1. Open the site URL -> **Create account** -> enter the e-mail code -> sign in (this is your student account).
2. Create a second account for the admin, verify it, then:
```bash
./scripts/make_admin.sh admin@college.edu ap-south-1
```
3. Log out and in again - the **🛠 Admin** tab appears.
📸 Screenshots: sign-up, verification, Cognito user list with group membership.

## Step 5 - Demo script (this is your "working implementation")
1. **Student:** New complaint -> "Sparking socket near Lab 3, danger of fire" + a photo -> notice the banner: *auto-tagged Electricity · HIGH*.
2. **Admin e-mail arrives** (SNS) with category + priority. 📸
3. **Admin:** Admin tab -> filter OPEN -> click *IN PROGRESS* with a note -> *RESOLVED*.
4. **Student:** My complaints -> see the new status and note (and an e-mail if SES is configured).
5. **Admin:** Post a notice -> appears for all users + e-mail. 📸
6. Try as a student: open `GET /complaints?scope=all` -> **403 Admins only** (authorisation proof).

## Step 6 - Automated end-to-end test
```bash
TOKEN=$(python scripts/get_token.py <ClientId> student@college.edu '<password>' ap-south-1)
python tests/smoke_check.py https://<api-id>.execute-api.ap-south-1.amazonaws.com "$TOKEN"
```
Expected: `8/8 checks passed`. 📸 the terminal.

## Step 7 - Optional: e-mail students on status change (SES)
Verify a sender address in SES, then redeploy with `--parameter-overrides AdminEmail=... SenderEmail=you@college.edu`.
(SES sandbox only sends to verified recipients - fine for a demo with 2-3 accounts.)

## Step 8 - Monitoring evidence
Open CloudWatch dashboard while running the load test (see Results doc) - screenshot the spike in requests, Lambda concurrency, and latency.
Open **X-Ray -> Traces** and screenshot one trace (API GW -> Lambda -> DynamoDB -> Comprehend).

## Step 9 - Clean up (important!)
```bash
./scripts/teardown.sh ap-south-1
```

## Troubleshooting
| Symptom | Fix |
|---|---|
| Login says *Incorrect username or password* right after sign-up | You must verify the e-mail code first |
| Admin tab missing | Run `make_admin.sh`, then **log out and in** (the group is inside the token) |
| 401 on every call | Token expired - log in again; the app sends the **ID token** |
| CORS error in the browser | Open the site via the CloudFront URL (only it and localhost:8080 are allowed) |
| No e-mails | Confirm the SNS subscription e-mails; check spam |
| `AccessDenied` on Comprehend | Comprehend must be available in your region (ap-south-1 is supported) |
| 429 errors in load test | Expected once you exceed the 100 rps throttle - this is a feature; raise it in `template.yaml` |
| Lambda throttles at low load | New accounts can have a low concurrent-execution quota; request an increase in Service Quotas |
