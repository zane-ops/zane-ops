# Contributing to Zane

Thank you for showing an interest in contributing to ZaneOps! All kinds of contributions are valuable to us. In this guide,
we will cover how you can quickly onboard and make your first contribution.

## Testing the app

One of the best ways to contribute is by installing and using the application. You can even do so locally and report any bugs you encounter or suggest features you need. For instructions on how to install and set up ZaneOps, [see here](https://zane.fredkiss.dev/docs/get-started/).


## Submitting an issue

Before submitting a new issue, please search the [issues](https://github.com/zane-ops/zane-ops/issues) tab. Maybe an
issue or discussion already exists and might inform you of workarounds. Otherwise, you can give new information.

While we want to fix all the [issues](https://github.com/zane-ops/zane-ops/issues), before fixing a bug we need to be
able to reproduce and confirm it. Please provide us with a minimal reproduction scenario using a repository
or [Gist](https://gist.github.com/). Having a live, reproducible scenario gives us the information without asking
questions back & forth with additional questions like:

- 3rd-party libraries being used and their versions
- a use-case that fails

Without said minimal reproduction, we won't be able to investigate
all [issues](https://github.com/zane-ops/zane-ops/issues), and the issue might not be resolved.

You can open a new issue with this [issue form](https://github.com/zane-ops/zane-ops/issues/new).

## How to work on the project ?


1. First you have to clone the repository

    ```shell
    git clone https://github.com/zane-ops/zane-ops.git
    ``` 

2. Then run the setup script :

   ```shell
   make setup
   ```

   If you receive this error message :

    ```
    Error response from daemon: This node is already part of a swarm. Use "docker swarm leave" to leave this swarm and join another one.
    ```
   You can safely ignore it, it means that you have already initialized docker swarm.

3. Start the project :

   Start the DEV server for docker and the frontend :
    ```shell
    make dev
    # or
    pnpm run  --filter='!backend' --recursive --parallel dev
    ```

   Wait until you see `Server launched at http://app.127-0-0-1.sslip.io` in the terminal . Then, start the development server for the API:
    ```shell
    make dev-api
    # or
	pnpm run  --filter='backend' --recursive dev
    ```

4. Run DB migrations :

    ```shell
    make migrate
    ```

5. Open the source code and start working :

   The app should be available at http://app.127-0-0-1.sslip.io

## Debugging

You may end up having issues where the project is not working, the app is not reachable on the browser, or the API seems
to be down, this section is to help debugging this case, if the app is working fine on your end, you don't need to read
this section.

1. make sure you ran `make dev` and it didn't exit unexpectedly
2. make sure that all the containers are up, you can check it in your docker tool of choice, [orbstack](https://orbstack.dev/) or [docker desktop](https://www.docker.com/products/docker-desktop/)
   <img src="/docs/images/illustration.webp" />
3. make sure that the API is launched, and that no error is in thrown in the terminal where `make dev` is running
4. make sure to setup the project and install the packages with `make setup`
5. If the app is still unresponsive, run `make reset-db` However, it's crucial to note that this action will completely
   erase all data in the database and reset the project to its initial state.

## Project structure

A quick look at the top-level files and directories you will see in this project.

```
.
├── .github/
│   └── workflows/
│       ├── pytests.yaml
│       ├── check-format.yaml
│       ├── build-push-images-dev.yaml
│       └── build-push-images-canary.yaml
├── backend/
├── frontend/
├── cli/
├── docker/
│   ├── docker-stack.yaml
│   └── docker-compose.yaml
└── openapi/
    └── schema.yaml
```


1. **`backend/`**: A standard Django app. The API source code is located in the `backend/zane_api/` folder.

2. **`frontend/`**: Contains the frontend code built with Vite and React. The source files are in `frontend/src/`.

3. **`cli/`**: Contains the source code for the CLI used to set up the project, written in Go.

4. **`.github/`**: Contains the GitHub Actions workflow configurations for Continuous Integration/Continuous Deployment (CI/CD).
    1. **`check-format.yaml`**: Checks that the frontend files are properly formatted using Biome.
    2. **`pytests.yaml`**: Runs tests for the project's API.
    3. **`build-push-images-dev.yaml`**: Builds the docker images of each component of zaneops for each Pull Request 
    4. **`build-push-images-canary.yaml`**:  Builds the docker images of each component of zaneops when PR are merged to `main`, each image will have the tag of `canary`

5. **`docker/`**: Contains Docker-specific files for working with the project locally:
    1. **`docker-compose.yaml`**: Defines the Docker Compose configuration for services used in development, such as Redis, Postgres, and Temporal.
    2. **`docker-stack.yaml`**: Specifies services in development that need to work within Docker Swarm, notably Caddy (Zane Proxy), which exposes the deployed services to HTTP.

6. **`openapi/schema.yaml`**: Contains the OpenAPI schema generated from the backend API.


## Missing a Feature?

If a feature is missing, you can directly _request_ a new
one [here](https://github.com/zane-ops/zane-ops/issues/new?assignees=&labels=feature&template=feature_request.yml&title=%F0%9F%9A%80+Feature%3A+).
You also can do the same by choosing "🚀 Feature" when raising
a [New Issue](https://github.com/zane-ops/zane-ops/issues/new/choose) on our GitHub Repository.
If you would like to _implement_ it, an issue with your proposal must be submitted first, to be sure that we can use it.
Please consider the guidelines given below.

## Coding guidelines

To ensure consistency throughout the source code, please keep these rules in mind as you are working:

- All backend features or bug fixes must be tested by one or more specs (unit-tests or functionnal tests).
- Be sure to update the `requirements.txt` file if you installed new packages
- For the frontend we use [biome](https://biomejs.dev/) as our formatter, be sure to format your code before pushing
  your code.

## Need help? Questions and suggestions

Questions, suggestions, and thoughts are most welcome, please use [discussions](https://github.com/zane-ops/zane-ops/)
for such cases.

## Ways to contribute

- Try Zaneops on your local machine or VM and give feedback
- Help with open [issues](https://github.com/zane-ops/zane-ops/issues)
  or [create your own](https://github.com/zane-ops/zane-ops/issues/new/choose)
- Share your thoughts and suggestions with us
- Help create tutorials and blog posts
- Request a feature by submitting a proposal
- Report a bug
