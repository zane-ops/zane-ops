## Implementation plan

- [x] Implement license install/uninstall
-  Implement feature checks:
  - [x] limit of 3 users
  - [x] Limit of more than 1 workspace

- Write the license for the licensing stuff:
  - [x] Register company name as ZaneOps
  - [x] Writes the license in `ee/LICENSE` ~~or modify the license file to indicate 
    that files with a certain header are under another license~~ 
  - Need to find the right license template for the enterprise edition, some ideas
    - https://github.com/fosrl/pangolin/blob/dev/LICENSE
    - https://github.com/Infisical/infisical/blob/main/LICENSE
    - https://github.com/Infisical/infisical/blob/main/backend/src/ee/LICENSE.md
    - https://spdx.org/licenses/BUSL-1.1.html
    - https://gitlab.com/gitlab-org/gitlab/-/blob/master/ee/LICENSE
    - https://gitlab.com/gitlab-org/gitlab/-/blob/master/LICENSE

- [x] Write the code to distributes the enterprise edition or business edition ? probably enterprise edition as people are more 
  used to that naming
- [x] Strip out the enterprise code from the OSS build : 
  -  ~~Using https://pypi.org/project/pypreprocessor/~~ -> No need, some example code:
    - https://github.com/interpreters/pypreprocessor/blob/main/Examples/debug.py
    - https://github.com/interpreters/pypreprocessor/blob/main/Examples/debug2production.py
    - https://pypi.org/project/pypreprocessor/

- [x] Write the terms & privacy policy of ZaneOps in the docs repo, some ideas:
  - https://handbook.gitlab.com/handbook/legal/professional-services-agreement/
  - https://about.gitlab.com/privacy/
  - https://infisical.com/terms/self-hosted
  - https://infisical.com/privacy
  - https://pangolin.net/fcl
  - https://pangolin.net/tos
  - https://pangolin.net/privacy

- Writes the licensing server/API:
  - [x] Will require to setting up stripe enterprise tax info
  - [x] Using stripe Quick checkout
  - [x] Implement the stripe webhook endpoint for when the user buys a license
  - [x] Implement the license get endpoint
  - [x] Deploy the API on ZaneOps in DEV
    - [x] Test to be sure
  - [x] Deploy the API on ZaneOps in PROD
    - [ ] Test to be sure


- Implement frontend for Workspace admin :
  - [ ] New dashboard header to show workspace & user profile
  - [ ] Instance dashboard admin
  - [ ] New cmd+k as a dialog with more options (?)
  - [ ] List invitations
- [ ] Implement Guest UI: show only the accessible projects
- Implement Instance Admin UI
  - [ ] Workspaces CRUD
  - [ ] Users CRUD
  - [ ] License CRUD: Show, Install, Uninstall, Buy