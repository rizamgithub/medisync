# Runbook 02 — Create IAM Users (`medisync-admin` + `medisync-mcp`)

> **Purpose:** Create the two non-root IAM users we'll use from here on. Root user gets locked away forever after this.
> **Estimated time:** 15 minutes.
> **Pre-requisite:** Runbook 01 complete (billing alarm + budget + Cost Explorer).

---

## Why two users

| User | Used by | Permissions | Why separate |
|---|---|---|---|
| `medisync-admin` | You, from your laptop, for occasional manual work | Almost-everything, scoped to resources tagged `Project=MediSync` | If your laptop is compromised, attacker can't touch unrelated AWS resources |
| `medisync-mcp` | The AI agent (Claude Code) via MCP servers | Read-mostly, scoped to MediSync resources | The AI never needs broad write; least privilege limits blast radius |

**Both use long-lived access keys** for now. Rotate every 90 days (calendar reminder recommended).

---

## Step 1 — Create `medisync-admin`

### 1a. Create the user

1. Console search → **IAM** → Users → **Create user**.
2. User name: `medisync-admin`
3. **Do NOT** tick "Provide user access to the AWS Management Console" — we only need programmatic access (CLI/Terraform). Console access stays on root for emergencies.
4. **Next**.
5. Permissions options: **Attach policies directly**.
6. **Skip selecting any managed policy** — we'll attach our custom one in step 1c.
7. **Next** → **Create user**.

### 1b. Create the custom policy

1. IAM → Policies → **Create policy** → **JSON** tab.
2. Paste the JSON below.
3. **Next** → name it `MediSyncAdminScoped` → description `Admin permissions restricted to resources tagged Project=MediSync` → **Create policy**.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowReadOnlyOnEverything",
      "Effect": "Allow",
      "Action": [
        "iam:Get*",
        "iam:List*",
        "iam:SimulatePrincipalPolicy",
        "ec2:Describe*",
        "logs:Describe*",
        "logs:Get*",
        "logs:List*",
        "cloudwatch:Describe*",
        "cloudwatch:Get*",
        "cloudwatch:List*",
        "ce:Get*",
        "ce:Describe*",
        "ce:List*",
        "budgets:Describe*",
        "budgets:View*",
        "tag:Get*",
        "sts:GetCallerIdentity",
        "support:DescribeTrustedAdvisorChecks"
      ],
      "Resource": "*"
    },
    {
      "Sid": "AllowFullActionsOnMediSyncTaggedResources",
      "Effect": "Allow",
      "Action": [
        "lambda:*",
        "apigateway:*",
        "dynamodb:*",
        "cognito-idp:*",
        "events:*",
        "states:*",
        "ses:*",
        "sns:*",
        "ssm:*",
        "s3:*",
        "logs:*",
        "xray:*",
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:PassRole",
        "iam:CreatePolicy",
        "iam:DeletePolicy",
        "iam:CreatePolicyVersion",
        "iam:DeletePolicyVersion",
        "iam:TagRole",
        "iam:TagPolicy",
        "iam:UntagRole",
        "iam:UntagPolicy"
      ],
      "Resource": "*",
      "Condition": {
        "StringEqualsIfExists": {
          "aws:RequestTag/Project": "MediSync",
          "aws:ResourceTag/Project": "MediSync"
        }
      }
    },
    {
      "Sid": "DenyExpensiveServices",
      "Effect": "Deny",
      "Action": [
        "rds:*",
        "ecs:*",
        "eks:*",
        "fsx:*",
        "elasticache:*",
        "elasticfilesystem:*",
        "redshift:*",
        "opensearch:*",
        "kafka:*",
        "kinesisanalytics:*",
        "iot:*",
        "appsync:*",
        "sagemaker:*",
        "bedrock:*",
        "datazone:*",
        "comprehend:*",
        "transcribe:*",
        "translate:*",
        "rekognition:*"
      ],
      "Resource": "*"
    },
    {
      "Sid": "DenyAccountAndOrgChanges",
      "Effect": "Deny",
      "Action": [
        "organizations:*",
        "account:*",
        "aws-portal:Modify*",
        "iam:CreateUser",
        "iam:DeleteUser",
        "iam:CreateAccessKey",
        "iam:DeleteAccessKey",
        "iam:UpdateAccountPasswordPolicy"
      ],
      "Resource": "*"
    }
  ]
}
```

**What the policy does:**
- ✅ Read-only on most account-wide resources (so you can browse and inspect).
- ✅ Full write on Lambda, DynamoDB, API Gateway, Cognito, EventBridge, Step Functions, SES, SNS, SSM, S3, CloudWatch Logs, X-Ray, and IAM roles — but only if the resource is tagged `Project=MediSync`.
- ❌ Hard-denied: RDS, ECS, EKS, IoT, AppSync, SageMaker, Bedrock, and other expensive services. Even if you try, AWS refuses.
- ❌ Hard-denied: changing the account, the organization, or creating other IAM users.

### 1c. Attach the policy to the user

1. IAM → Users → `medisync-admin` → **Permissions** tab → **Add permissions** → **Attach policies directly** → search `MediSyncAdminScoped` → tick → **Next** → **Add permissions**.

### 1d. Create access key

1. Same user page → **Security credentials** tab → scroll to **Access keys** → **Create access key**.
2. Use case: **Command Line Interface (CLI)**.
3. Tick the confirmation box → **Next**.
4. Description: `Local laptop CLI - rotate by YYYY-MM-DD` (set 90 days out).
5. **Create access key**.
6. **DOWNLOAD .csv** or copy both values immediately — the secret is shown only once.

### 1e. Configure local AWS CLI profile

In PowerShell:

```powershell
aws configure --profile medisync-admin
# AWS Access Key ID:     <paste from above>
# AWS Secret Access Key: <paste from above>
# Default region name:   ap-southeast-1
# Default output format: json
```

Verify:

```powershell
aws sts get-caller-identity --profile medisync-admin
```

Should print your account ID and the ARN ending in `:user/medisync-admin`.

---

## Step 2 — Create `medisync-mcp`

### 2a. Create the user

1. IAM → Users → **Create user**.
2. User name: `medisync-mcp`
3. Do NOT tick console access (programmatic only).
4. **Next** → permissions: **Attach policies directly** → skip selecting → **Next** → **Create user**.

### 2b. Create the custom policy

1. IAM → Policies → **Create policy** → **JSON** tab.
2. Paste the JSON below.
3. Name: `MediSyncMcpReadOnly` → description `Read-mostly access for AI agent MCP servers, scoped to MediSync resources` → **Create policy**.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadOnlyAcrossAccount",
      "Effect": "Allow",
      "Action": [
        "lambda:Get*",
        "lambda:List*",
        "apigateway:GET",
        "dynamodb:Describe*",
        "dynamodb:List*",
        "dynamodb:Get*",
        "dynamodb:Query",
        "dynamodb:Scan",
        "cognito-idp:Describe*",
        "cognito-idp:List*",
        "cognito-idp:Get*",
        "cognito-idp:AdminGet*",
        "cognito-idp:AdminList*",
        "events:Describe*",
        "events:List*",
        "states:Describe*",
        "states:List*",
        "states:Get*",
        "ses:Get*",
        "ses:List*",
        "ses:Describe*",
        "sns:Get*",
        "sns:List*",
        "ssm:Describe*",
        "ssm:Get*",
        "ssm:List*",
        "s3:List*",
        "s3:GetBucketLocation",
        "s3:GetBucketTagging",
        "s3:GetObject",
        "logs:Describe*",
        "logs:Get*",
        "logs:List*",
        "logs:FilterLogEvents",
        "logs:StartQuery",
        "logs:StopQuery",
        "logs:GetQueryResults",
        "cloudwatch:Describe*",
        "cloudwatch:Get*",
        "cloudwatch:List*",
        "xray:Get*",
        "xray:BatchGetTraces",
        "xray:GetTraceSummaries",
        "ce:Get*",
        "ce:Describe*",
        "ce:List*",
        "budgets:Describe*",
        "budgets:View*",
        "tag:Get*",
        "iam:Get*",
        "iam:List*",
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    },
    {
      "Sid": "DenyExpensiveAndSensitive",
      "Effect": "Deny",
      "Action": [
        "rds:*",
        "ecs:*",
        "eks:*",
        "iot:*",
        "appsync:*",
        "sagemaker:*",
        "bedrock:*",
        "organizations:*",
        "account:*",
        "iam:CreateAccessKey",
        "iam:DeleteAccessKey"
      ],
      "Resource": "*"
    }
  ]
}
```

**What this policy does:**
- ✅ Reads everything Lambda/DynamoDB/Cognito/Logs/CloudWatch/X-Ray/Cost Explorer for the MCPs to function.
- ✅ DynamoDB `Query` and `Scan` so the agent can inspect table contents during dev.
- ✅ CloudWatch Logs `FilterLogEvents` so the agent can pull error logs.
- ❌ No write actions are listed in `Allow`, so IAM denies all writes by default. (We don't need an explicit `Deny *:Create*` block — IAM doesn't allow wildcards on the service prefix anyway, that syntax is invalid.)
- ❌ Hard-deny on RDS / ECS / EKS / IoT / AppSync / SageMaker / Bedrock — defense in depth even if a future edit accidentally added them to Allow.

### 2c. Attach policy

Same as 1c, with `MediSyncMcpReadOnly`.

### 2d. Create access key

Same as 1d, but description: `MCP server - rotate by YYYY-MM-DD`.

### 2e. Configure local AWS CLI profile

```powershell
aws configure --profile medisync-mcp
# (same as above, paste the medisync-mcp keys, region ap-southeast-1, json)
```

Verify:

```powershell
aws sts get-caller-identity --profile medisync-mcp
```

Should print ARN ending in `:user/medisync-mcp`.

---

## Step 3 — Verify deny rules actually work

This proves the guardrails aren't theatre.

```powershell
# Should succeed (read allowed)
aws sts get-caller-identity --profile medisync-mcp

# Should FAIL with AccessDenied (RDS is denied)
aws rds describe-db-instances --profile medisync-mcp --region ap-southeast-1

# Should FAIL with AccessDenied (any create is denied for mcp user)
aws dynamodb create-table `
  --table-name test `
  --attribute-definitions AttributeName=pk,AttributeType=S `
  --key-schema AttributeName=pk,KeyType=HASH `
  --billing-mode PAY_PER_REQUEST `
  --profile medisync-mcp `
  --region ap-southeast-1
```

Expected: first command succeeds, the other two return `AccessDeniedException`. If RDS succeeds or the create succeeds, the policy is wrong — **stop and re-check** before continuing.

---

## Step 4 — Set environment for Claude Code MCPs

Set the default AWS profile that the MCP servers will use:

```powershell
[Environment]::SetEnvironmentVariable("AWS_PROFILE", "medisync-mcp", "User")
[Environment]::SetEnvironmentVariable("AWS_REGION", "ap-southeast-1", "User")
```

These persist across PowerShell sessions. Verify in a **new** PowerShell window:

```powershell
echo $env:AWS_PROFILE  # medisync-mcp
echo $env:AWS_REGION   # ap-southeast-1
```

---

## Step 5 — Lock down root

1. Sign out of root.
2. From now on always log in as `medisync-admin` *(once you've given it console access if/when needed)*, or stay programmatic-only.
3. Root user — never again, except for billing emergencies or account closure.

---

## Verification checklist

- [ ] `medisync-admin` user exists with `MediSyncAdminScoped` policy attached.
- [ ] `medisync-mcp` user exists with `MediSyncMcpReadOnly` policy attached.
- [ ] Both have access keys configured in `~/.aws/credentials` under their profile names.
- [ ] `aws sts get-caller-identity` works for both profiles.
- [ ] `aws rds describe-db-instances --profile medisync-mcp` fails with AccessDenied.
- [ ] `AWS_PROFILE` env var is set to `medisync-mcp` in user environment.
- [ ] Calendar reminder set for 90 days from now to rotate both access keys.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "AccessDenied" on something you expect to work | Policy doesn't list that action | Add it to the relevant Sid in the policy JSON, re-save the policy |
| `aws configure` says command not found | AWS CLI not installed | `winget install --id Amazon.AWSCLI -e` |
| `get-caller-identity` returns root's ARN | Forgot `--profile` flag | Add `--profile medisync-admin` or set `AWS_PROFILE` env var |
| MCP server can't connect | Wrong profile name in `.claude/settings.json` | Confirm it matches `medisync-mcp` exactly |

---

## Related runbooks

- [01-aws-account-bootstrap.md](./01-aws-account-bootstrap.md) — prerequisite
- `03-terraform-bootstrap.md` — S3 state bucket + DynamoDB lock + GitHub OIDC role *(next)*
