## Implementation plan

- [x] Implement license install/uninstall
-  Implement feature checks:
  - [ ] limit of 3 users
  - [x] Limit of more than 1 workspace

- [ ] Write the license for the licensing stuff 
  - [ ] Either writes the license in `licensing/LICENSE` or modify the license file to indicate 
    that files with a certain header are under another license 
  - [ ] Need to find the right license template for the enterprise edition, some ideas
    - https://github.com/fosrl/pangolin/blob/dev/LICENSE
    - https://github.com/Infisical/infisical/blob/main/LICENSE
    - https://github.com/Infisical/infisical/blob/main/backend/src/ee/LICENSE.md
    - https://spdx.org/licenses/BUSL-1.1.html

- [ ] Write the code to distributes the enterprise edition or business edition ? probably enterprise edition as people are more 
  used to that naming
- [ ] Strip out the enterprise code from the OSS build : 
  - [ ] Using https://pypi.org/project/pypreprocessor/, some example code:
    - https://github.com/interpreters/pypreprocessor/blob/main/Examples/debug.py
    - https://github.com/interpreters/pypreprocessor/blob/main/Examples/debug2production.py
    - https://pypi.org/project/pypreprocessor/

- [ ] Writes the licensing server/API:
  - [ ] Will require to setting up stripe enterprise tax info
  - [ ] Using stripe Quick checkout
  - [ ] Implement the stripe webhook endpoint for when the user buys a license
  - [ ] Implement the license get endpoint
  - [ ] Deploy the API on ZaneOps
  - [ ] Test to be sure