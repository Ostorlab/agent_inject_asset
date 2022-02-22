
<h1 align="center">Agent Inject Asset</h1>

<p align="center">
<img src="https://img.shields.io/badge/License-Apache_2.0-brightgreen.svg">
<img src="https://img.shields.io/github/languages/top/ostorlab/agent_inject_asset">
<img src="https://img.shields.io/github/stars/ostorlab/agent_inject_asset">
<img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg">
</p>

_Inject Asset is responsible for injecting an asset into the bus from the runtime._

---

<p align="center">
<img src="https://raw.githubusercontent.com/Ostorlab/agent_inject_asset/main/images/logo.png" alt="agent_inject_asset" />
</p>

This repository is an implementation of the default inject asset agent.Inject Asset is a default agent needed to run a scan using the local runtime.

## Usage

Agent Inject Asset can be installed directly from the ostorlab agent store or built from this repository.

 ### Install directly from ostorlab agent store

 ```shell
 ostorlab agent install agent/ostorlab/inject_asset
 ```
The agent will be automatically installed and updated by simply passing `--install` flag:

```shell
ostorlab scan run --install --agents agent/ostorlab/tsunami ip 8.8.8.8
```

## License
[Apache](./LICENSE)
