---
type: setup_guide
topic: syncthing_vault_sync
tier: platinum
---

# Alternative Vault Sync: Syncthing

If you prefer **Syncthing** over Git for vault synchronization, follow this guide.

## Why Syncthing?
- Real-time sync (no commit/push cycle)
- No GitHub account needed
- Fully self-hosted and private
- Works on LAN and internet

## Setup

### 1. Install Syncthing

**Local Machine (Windows)**:
```
winget install Syncthing.Syncthing
# Or download from: https://syncthing.net/downloads/
```

**Cloud VM (Linux)**:
```bash
curl -s https://syncthing.net/release-key.gpg | sudo tee /etc/apt/keyrings/syncthing-archive-keyring.gpg > /dev/null
echo "deb [signed-by=/etc/apt/keyrings/syncthing-archive-keyring.gpg] https://apt.syncthing.net/ syncthing stable" | sudo tee /etc/apt/sources.list.d/syncthing.list
sudo apt update && sudo apt install syncthing
```

### 2. Configure Vault Sync

1. Open Syncthing Web UI: `http://localhost:8384`
2. Add Remote Device: paste Cloud VM's Device ID
3. Share Folder: select your vault path
4. Set folder type:
   - Local machine: **Send & Receive**
   - Cloud VM: **Send & Receive**

### 3. Ignore Secrets

Create `.stignore` in vault root:
```
// Never sync secrets
.env
.env.*
*.key
*.pem
credentials.json
token.json
session/
whatsapp_session/
*.pid
```

### 4. Run as Service (Cloud VM)

```bash
sudo systemctl enable syncthing@ubuntu
sudo systemctl start syncthing@ubuntu
```

## Comparison: Git vs Syncthing

| Feature | Git | Syncthing |
|---------|-----|-----------|
| Audit trail | ✅ Full commit history | ❌ No history |
| Conflict resolution | ✅ Manual merge | ⚠️ Auto (may overwrite) |
| Setup complexity | Medium | Low |
| Real-time sync | ❌ Cron-based | ✅ Yes |
| Requires GitHub | Yes | No |
| Offline support | ✅ | ✅ |

**Recommendation**: Use **Git** for full audit trail (recommended for compliance). Use **Syncthing** if you want simpler setup and real-time sync.
