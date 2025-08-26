# CLAUDE.md - Project Context for Zane-Ops

## Quick Commands

### Testing
- **Run tests (fast, parallel)**: `pnpm test` (from backend directory)
- **Run tests with keepdb**: `pnpm test -- --keepdb` (preserves database between runs)
- **Run specific tests**: `pnpm test <test_path>`
- **Alternative (slower)**: `uv run python manage.py test`

### Development
- **Regenerate OpenAPI schema**: `pnpm openapi` (from root)
- **Run backend**: `pnpm dev` (from backend)
- **Run frontend**: `pnpm dev` (from frontend)

## Important Project Notes

### RBAC System
- 5 roles: INSTANCE_OWNER, ADMIN, MEMBER, CONTRIBUTOR, GUEST
- 16 granular permissions
- Use DRF permission classes, not manual checks
- Permission matrix in `backend/zane_api/permissions.py`
- **ALL endpoints** must have permission_classes applied (not just RBAC ones)

### Database Configuration
- Default host should be `127.0.0.1` (not `0.0.0.0`)
- Test database: `test_zane`

### Code Conventions
- Always use DRF permission classes for authorization
- Delete objects directly instead of using CANCELLED status
- Generate OpenAPI schema with `pnpm openapi`, never edit manually
- **Apply permission_classes to ALL authenticated endpoints**
- **Remove manual owner=request.user checks** (use DRF object permissions)

### File Structure
- Backend: Django REST Framework in `/backend`
- Frontend: React/Remix in `/frontend`
- OpenAPI schema: `/openapi/schema.yml` (NOT .yaml)

### Testing Best Practices
- **Prefer integration tests over unit tests** (Fred's feedback)
- **Use `pnpm test` for fast parallel execution**
- **Always inherit from AuthAPITestCase** (located in `backend/zane_api/tests/base.py`)
- **Use --keepdb flag** to preserve database between runs and avoid locks
- **Test database is preserved** between runs with --keepdb
- **All tests must pass** before committing
- **AuthAPITestCase provides**: mocking helpers, authentication setup, test utilities

## Recent Updates
- RBAC implementation (PR #500)
- Permission system refactoring
- Invitation system without CANCELLED status

## Useful Context

### Fred's Preferences
- Clean, maintainable code
- Proper Django/DRF patterns
- No manual permission checks scattered in views
- Generate schemas, don't edit manually
- Tests must pass before review
- **Frequent commits** for better review process
- **Integration tests preferred** over unit tests
- **Avoid generating too much code** that's hard to review

### Project Architecture
- Django backend with Temporal workflows
- React frontend with Remix routing
- Docker-based deployment system
- Role-based access control with granular permissions