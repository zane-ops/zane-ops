<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/ZaneOps-SYMBOL-WHITE.svg">
    <source media="(prefers-color-scheme: light)" srcset="./images/ZaneOps-SYMBOL-BLACK.svg">
    <img src="./images/ZaneOps-SYMBOL-WHITE.svg" alt="Zane logo"  height="100" />
  </picture>
</p>

# <div align="center">Zane Ops</div>

### <div align="center">ZaneOps is a self-hosted, open source platform for hosting static sites, web apps, databases, CRONS, Workers using docker swarm as the engine.</div>

---

## 📸 Screenshots

### Login

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./images/login-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="./images/login-light.png">
    <img src="./images/login-dark.png" alt="Login page" />
  </picture>
</p>

### Dashboard

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./images/dashboard-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="./images/dashboard-light.png">
    <img src="./images/dashboard-dark.png" alt="Login page" />
  </picture>
</p>

### Creating a Project

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./images/create-project-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="./images/create-project-light.png">
    <img src="./images/create-project-dark.png" alt="Login page" />
  </picture>
</p>

### Project detail

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./images/project-detail-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="./images/project-detail-light.png">
    <img src="./images/project-detail-dark.png" alt="Login page" />
  </picture>
</p>

> More to come

## 🛣️ ROADMAP 

### beta

- [ ] Docker services frontend 
  - [ ] Details page 
  - [ ] Env variables page
  - [ ] Settings page
  - [ ] Single deployment page
  - [ ] Single deployment application logs page
  - [ ] Single deployment http logs page
  - [ ] deploy & redeploy deployments
- [ ] Project frontend
  - [ ] settings page 
- [ ] CLI
  - [ ] install & setup zaneops
  - [ ] authenticate with token (require token UI+API in ZaneOps)
  - [ ] Deploy a service using the CLI

### v1 

- [ ] Rewrite from celery to temporal (not sure)
- [ ] Managing environments (stating, production, and ephemeral envs)
- [ ] Support workers (A.K.A sleeping services)
- [ ] Git services API
  - [ ] create service from a public repo
  - [ ] deploy service  
    - [ ] Building service with nixpacks  
  - [ ] archive service
  - [ ] Pull Request environments
  - [ ] Auto-comments with deployment status on github
- [ ] Git services frontend & API (same as docker services)

### v2

- [ ] CRONs support for services
- [ ] Template List
- [ ] Multi-server support

## 🍙 Getting Started

All the steps to install and run ZaneOps are listed in the [documentation](https://zane.fredkiss.dev/docs).

## ❤️ Contributing

Interested in contributing? Check out the [contribution guidelines](./CONTRIBUTING.md).

## Credits

- [Plane](https://github.com/makeplane/plane): for giving us content for the contributions templates (contribution
  guidelines).