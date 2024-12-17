## Description

Please provide a brief summary of the changes. If it fixes a bug or resolves a feature request, be sure to link to that issue.

fixes #


> [!WARNING]
> Please do not delete the sections below

### ⚠️ If you modify backend code, be sure to run these commands : 

```bash
cd backend
pnpm run openapi # will generate OpenAPI schema at `/openapi/schema.yaml`
pnpm run freeze # will update the `requirements.txt` file if you added new packages
```

### ⚠️ If you modify frontend code, be sure to run these commands : 

```bash
pnpm install --frozen-lockfile # Install the packages at the exact version listed in the lockfile
pnpm run format # format the files using biome
```


## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
