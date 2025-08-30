GITLAB_NULL_COMMIT = "0000000000000000000000000000000000000000"

PREVIEW_DEPLOYMENT_COMMENT_MARKDOWN_TEMPLATE = """
### ZaneOps Preview Deployment

| Service                                       | Deployment                                         | Preview                                | Deployment duration       | Updated (UTC)             |
| :-------------------------------------------- | :------------------------------------------------- | :------------------------------------- | :------------------------ | :------------------------ |
| [{{dpl.service_fqdn}}]({{dpl.service_url}})   | {{dpl.status_icon}} [{{dpl.status}}]({{dpl.url}})  | {{dpl.preview_url}}                    | {{dpl.duration}}         | {{dpl.updated_at}}        |
"""

PREVIEW_DEPLOYMENT_BLOCKED_COMMENT_MARKDOWN_TEMPLATE = """
### 🚨 ZaneOps Preview Deployment Blocked - Security Protection

@{{dpl.pr_author}} attempted to deploy a pull request to the service [{{dpl.service_fqdn}}]({{dpl.service_url}}) on ZaneOps.

A member of the ZaneOps instance needs to [review and approve this deployment]({{dpl.approval_url}}) before it can run.  

---  
*This safeguard prevents untrusted code from running in preview environments. Only verified team members can approve and trigger these deployments.*  

<details>
<summary>🛡️ Why this protection matters</summary>

Without this check, unauthorized users could:
- Run harmful code on the preview server  
- Access sensitive environment variables and secrets  
- Put the infrastructure at risk  

Preview deployments are powerful, but they must come from trusted contributors with repository write access.  
</details>

"""

PREVIEW_DEPLOYMENT_DECLINED_COMMENT_MARKDOWN_TEMPLATE = """
### ❌ ZaneOps Preview Deployment Declined

The preview deployment for this pull request targeting [{{dpl.service_fqdn}}]({{dpl.service_url}}) has been declined.

No preview environment will be created, and future commits to this pull request will not trigger deployments.

To deploy your changes, please open a new pull request.
"""
