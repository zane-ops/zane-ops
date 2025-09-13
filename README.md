<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/ZaneOps-HORIZONTAL-WHITE.svg">
    <source media="(prefers-color-scheme: light)" srcset="./images/ZaneOps-HORIZONTAL-BLACK.svg">
    <img src="./images/ZaneOps-HORIZONTAL-WHITE.svg" alt="Zane logo"  height="100" />
  </picture>
</p>

<div align="center">
<p>
your all-in-one self-hosted platform for deploying apps with ✨ zen ✨.
</p>


<img  src="https://img.shields.io/discord/1348034264670933002?logo=discord&style=for-the-badge&label=Community">

<picture>
 <source media="(prefers-color-scheme: dark)" srcset="https://zaneops.dev/images/project-detail-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="https://zaneops.dev/images/project-detail-light.png">
<img src="https://zaneops.dev/images/project-detail-light.png" />
</picture>

</div>


## What is ZaneOps ?

ZaneOps is a **beautiful, self-hosted, open-source** platform for hosting static sites, web apps, databases, services (like Supabase, WordPress, Ghost), workers, or anything else you need—whether you're launching a startup or managing an enterprise.  

It is a **free** and **open-source** alternative to platforms like **Heroku**, **Railway**, and **Render**, leveraging the **scalability** of [Docker Swarm](https://docs.docker.com/engine/swarm/) and the **flexibility** of [Caddy](https://caddyserver.com/).  


## 🚀 Installation

You can install zaneops like this :

```shell
# create a folder for installing ZaneOps
mkdir -p /var/www/zaneops
cd /var/www/zaneops

# download the ZaneOps "cli"
curl https://cdn.zaneops.dev/makefile > Makefile
make setup 
make deploy
```

> [!NOTE]
> If you have any issue, be sure to checkout the [instructions steps](https://zaneops.dev/installation/) in the documentation for more detailled setup.

## 📸 Some Screenshots


1. Onboarding

  <p align="center">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="./images/create-user-dark.png">
      <source media="(prefers-color-scheme: light)" srcset="./images/create-user-light.png">
      <img src="./images/create-user-dark.png" alt="Login page" />
    </picture>
  </p>

2. Login

  <p align="center">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="./images/login-dark.png">
      <source media="(prefers-color-scheme: light)" srcset="./images/login-light.png">
      <img src="./images/login-dark.png" alt="Login page" />
    </picture>
  </p>

3. Dashboard

  <p align="center">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="./images/dashboard-dark.png">
      <source media="(prefers-color-scheme: light)" srcset="./images/dashboard-light.png">
      <img src="./images/dashboard-dark.png" alt="Login page" />
    </picture>
  </p>

4. Project detail

  <p align="center">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="./images/project-detail-dark.png">
      <source media="(prefers-color-scheme: light)" srcset="./images/project-detail-light.png">
      <img src="./images/project-detail-dark.png" alt="Login page" />
    </picture>
  </p>

5. HTTP logs

  <p align="center">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="./images/http-logs-dark.png">
      <source media="(prefers-color-scheme: light)" srcset="./images/http-logs-light.png">
      <img src="./images/http-logs-dark.png" alt="Login page" />
    </picture>
  </p>

6. Runtime logs

  <p align="center">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="./images/logs-octane-dark.png">
      <source media="(prefers-color-scheme: light)" srcset="./images/logs-octane-light.png">
      <img src="./images/logs-octane-dark.png" alt="Login page" />
    </picture>
  </p>

> [!NOTE]
> More screenshots [in the documentation](https://zaneops.dev/screenshots/)

## ❤️ Contributing

Interested in contributing? Check out the [contribution guidelines](./CONTRIBUTING.md).

## 🙏 Credits

- [Plane](https://github.com/makeplane/plane): for giving us content for the contributions templates (contribution
  guidelines).
- [Coolify](https://github.com/coollabsio/coolify) and [Dokploy](https://github.com/dokploy/dokploy) which we used inspired ourselves from a lot.
