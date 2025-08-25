GITLAB_NULL_COMMIT = "0000000000000000000000000000000000000000"

PREVIEW_DEPLOYMENT_COMMENT_MARKDOWN_TEMPLATE = """
### ZaneOps Preview Deployment

| Service                                       | Deployment                                         | Preview URL                            | Updated (UTC)             |
| :-------------------------------------------- | :------------------------------------------------- | :------------------------------------- | :------------------------ |
| [{{dpl.service_fqdn}}]({{dpl.service_url}})   | {{dpl.status_icon}} [{{dpl.status}}]({{dpl.url}})  | {{dpl.preview_url}}                    | {{dpl.updated_at}}        |
"""

# PREVIEW_BLOCKED_COMMENT_MARKDOWN_TEMPLATE = """
# | Service                               | Deployment                                                             | Preview URL             | Updated (UTC)             |
# | ------------------------------------- | ---------------------------------------------------------------------- | ----------------------- | ------------------------- |
# | [{{service.fqdn}}]({{service.url}})   | {{deployment.status_icon}} [{{deployment.status}}]({{deployment.url}}) | {{sevrice.preview_url}} | {{deployment.updated_at}} |
# """
