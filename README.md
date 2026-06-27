# Home Assistant Pyscript Scripts for Home 

## Deployment

### One-command deploy (from your Mac)

Requires the `ha` SSH host alias and a key installed on HA (see **SSH setup** below).

```bash
./scripts/deploy.sh       # push current branch, then HA pulls + syncs + reloads
./scripts/dev-deploy.sh   # fast: rsync local working tree (incl. uncommitted) + reload, no git
```

`deploy.sh` is the source-of-truth path (goes through git). `dev-deploy.sh` is for
tight iteration — it can make HA drift from git, so commit + `deploy.sh` when done.
Both connect over SSH as `assen` and use passwordless `sudo` for the root-owned writes.

### SSH setup (one time)

The Advanced SSH & Web Terminal add-on only allows user `assen` (not root) and reads
authorized keys from `/etc/ssh/authorized_keys` (the add-on config field and `~/.ssh`
were ineffective/ephemeral here). To enable key auth:

1. Generate a key on the Mac: `ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519`
2. Add this `~/.ssh/config` block:
   ```
   Host ha
       HostName homeassistant.local   # use the Tailscale name when off-LAN
       User assen
       IdentityFile ~/.ssh/id_ed25519
   ```
3. In the HA web terminal, append the public key to the global keys file:
   ```bash
   echo "<contents of id_ed25519.pub>" >> /etc/ssh/authorized_keys
   ```

`homeassistant.local` (mDNS) only resolves on the LAN. Off-LAN, reach HA via Tailscale.

### Manual deploy (fallback, in HA web terminal as root)

```bash
cd homeassistant/ha
./update_ha.sh
```

where 
```bash

cat update_ha.sh                  
#! /bin/bash
git pull
rsync -av --delete pyscript/ /homeassistant/pyscript/
~/homeassistant/reload-python.sh


cat ~/homeassistant/reload-python.sh            
#!/bin/bash

curl -X POST http://localhost:8123/api/services/pyscript/reload \
  -H "Authorization: Bearer ..." \
  -H "Content-Type: application/json"
```

For development use the `develop_hass` Jupyter notebook. 
If changing utils.py, update the notebook.


Running Victoria metrics


docker run -d \
  --name vmagent \
  --restart unless-stopped \
  -p 8429:8429 \
  --entrypoint /bin/sh \
  victoriametrics/vmagent \
  -c "echo '
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: \"homeassistant\"
    metrics_path: /api/prometheus
    scheme: http
    static_configs:
      - targets: [\"192.168.2.39:8123\"]
    authorization:
      type: Bearer
      credentials: ...
' > /tmp/config.yml && exec /vmagent-prod -promscrape.config=/tmp/config.yml -remoteWrite.url=http://192.168.2.39:8428/api/v1/write"

docker run -d \
  --name victoriametrics \
  --restart unless-stopped \
  -p 8428:8428 \
  victoriametrics/victoria-metrics


