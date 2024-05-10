# 🏗️ Architecture of the project


## Overview
To run ZaneOps needs many components to run user's services and to run itself but the main point is that ZaneOps is built on docker and [docker-swarm](https://docs.docker.com/engine/swarm/), the app itself runs on swarm and it controls all the other services using swarm also.



<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../images/architecture-dev-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="../images/architecture-dev-light.png">
    <img src="../images/architecture-dev-dark.png" alt="Zane logo"  width="80%" />
  </picture>
</p>

The main components needed to run ZaneOps are : 

1. The **Proxy** which is the entrypoint of the app, its role is to redirect all connections to the appropriate services you defined or to redirect to the ZaneOps dashboard depending on the domain you set for it. it uses a [caddy](https://hub.docker.com/_/caddy) docker image
   1. The

2. The **API** which is written in Python with the framework Django and Django Rest Framework for the Rest API part : it handles authentication, authorization and saving objects in the database.

3. The **Frontend** which is written in React and scaffolded with [Vite](https://vitejs.dev/), it is a pure SPA that talks whith the API to get the data to render.

4. The **database** which is a [postgres](https://hub.docker.com/_/postgres) docker container.



## Schema of a request going to create a service

> TODO

## How is this setup in production ?

> TODO
