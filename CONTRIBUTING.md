# Contributing to Zane

Thank you for showing an interest in contributing to Zane! All kinds of contributions are valuable to us. In this guide,
we will cover how you can quickly onboard and make your first contribution.

## Submitting an issue

Before submitting a new issue, please search the [issues](https://github.com/fredkiss3/zane-ops/issues) tab. Maybe an
issue or discussion already exists and might inform you of workarounds. Otherwise, you can give new information.

While we want to fix all the [issues](https://github.com/fredkiss3/zane-ops/issues), before fixing a bug we need to be
able to reproduce and confirm it. Please provide us with a minimal reproduction scenario using a repository
or [Gist](https://gist.github.com/). Having a live, reproducible scenario gives us the information without asking
questions back & forth with additional questions like:

- 3rd-party libraries being used and their versions
- a use-case that fails

Without said minimal reproduction, we won't be able to investigate
all [issues](https://github.com/fredkiss3/zane-ops/issues), and the issue might not be resolved.

You can open a new issue with this [issue form](https://github.com/fredkiss3/zane-ops/issues/new).

## Projects setup and Architecture

## Requirements

- [Node](https://nodejs.org/en) >= v20.11.1
- [pnpm](https://pnpm.io/installation) >= v8.7.1
- [docker](https://docs.docker.com/engine/install/)
- [docker-compose](https://docs.docker.com/compose/install/)
- [caddy](https://caddyserver.com/download)
- [python](https://www.python.org/downloads/) >= v3.11.7
- [biome extension installed in VSCode](https://biomejs.dev/reference/vscode/)

## 🚀 How to work on the project ?

1. First you have to clone the repository

    ```bash
    git clone https://github.com/Fredkiss3/zane-ops.git
    ``` 

2. **Then, Install the dependencies :**

   From the root of the project :
    ```bash
    pnpm install --frozen-lockfile
    ```

   For the backend
    ```bash
    cd backend
    # Create a virtual env
    python -m venv ./venv
    # activate the virtualenv
    source ./venv/bin/activate
    # Install all the packages
    pip install uv
    uv pip install -r requirements.txt
    ```

3. **Start the project**

   From the root
    ```bash
    make dev
    ```

4. **Run DB migrations :**

   From the Backend
    ```bash
    cd backend
    python manage.py migrate
    ```

5. Go to `/etc/hosts` and append this entry to that file :

    ```
    127.0.0.1       zane.local 
    ```

   The API will be available at [https://zane.local](https://zane.local).

6. **Open the source code and start rocking ! 😎**

## 🧐 Project structure

A quick look at the top-level files and directories you will see in this project.

    .
    ├── .github/
    │    └── workflows
    │        ├── pytests.yaml
    │        ├── push-docker-images.yaml
    │        └── build-cli.yaml
    ├── backend/
    │   └── zane_api
    ├── frontend/
    │   └── src/
    ├── cli
    └── docker-compose.yaml

1. **`.github/`**: this folder contains the GitHub Actions workflow configuration for Continuous Integration/Continuous
   Deployment.

    1. **`pytests.yaml`** : this workflow is used to test the api of the project.

    2. **`push-docker-images.yaml`** : this workflow is used to build and push the docker images for the project.

    3. **`build-cli.yaml`** : this workflow is used to build the cli app to different OSes (debian/ubuntu, macOS and
       windows).

2. **`backend/`**: A standard Django App, the code source of the API is in the `backend/zane_api/` folder.

3. **`frontend/`**: this folder contains the frontend made with vite and react, you can find the source files of the
   frontend in `frontend/src/`.

4. **`cli/`**: this folder contains the source for the CLI to setup the project

5. **`docker-compose.yaml`**: this file contains the docker-compose configuration for the services used in development

## Missing a Feature?

If a feature is missing, you can directly _request_ a new
one [here](https://github.com/fredkiss3/zane-ops/issues/new?assignees=&labels=feature&template=feature_request.yml&title=%F0%9F%9A%80+Feature%3A+).
You also can do the same by choosing "🚀 Feature" when raising
a [New Issue](https://github.com/fredkiss3/zane-ops/issues/new/choose) on our GitHub Repository.
If you would like to _implement_ it, an issue with your proposal must be submitted first, to be sure that we can use it.
Please consider the guidelines given below.

## Coding guidelines

To ensure consistency throughout the source code, please keep these rules in mind as you are working:

- All backend features or bug fixes must be tested by one or more specs (unit-tests).
- Be sure to update the `requirements.txt` file if you installed new packages
- For the frontend we use [biome](https://biomejs.dev/) as our formatter, be sure to format your code before pushing
  your code.

## Need help? Questions and suggestions

Questions, suggestions, and thoughts are most welcome, please use [discussions](https://github.com/fredkiss3/zane-ops/)
for such cases.

## Ways to contribute

- Try Zaneops on your local machine or VM and give feedback
- Help with open [issues](https://github.com/fredkiss3/zane-ops/issues)
  or [create your own](https://github.com/fredkiss3/zane-ops/issues/new/choose)
- Share your thoughts and suggestions with us
- Help create tutorials and blog posts
- Request a feature by submitting a proposal
- Report a bug
