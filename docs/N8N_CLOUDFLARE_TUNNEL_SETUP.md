# n8n with Cloudflare Tunnel Setup

This guide documents how to run n8n with a Cloudflare Tunnel for secure webhook access.

---

## Prerequisites

1. **Cloudflare Account** (free tier works)
2. **Domain on Cloudflare** (DNS managed by Cloudflare)
3. **Docker** installed
4. **cloudflared** CLI installed

---

## Step 1: Install cloudflared

### macOS
```bash
brew install cloudflared
```

### Linux (Debian/Ubuntu)
```bash
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb
```

### Windows
Download from: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/

### Verify Installation
```bash
cloudflared --version
```

---

## Step 2: Authenticate with Cloudflare

```bash
cloudflared tunnel login
```

This opens a browser to authenticate. Select the domain you want to use for tunnels.

A certificate is saved to `~/.cloudflared/cert.pem`.

---

## Step 3: Create a Tunnel

```bash
cloudflared tunnel create n8n-tunnel
```

This creates:
- A tunnel with UUID (e.g., `a1b2c3d4-e5f6-...`)
- Credentials file at `~/.cloudflared/<TUNNEL_UUID>.json`

**Note the tunnel UUID** - you'll need it.

---

## Step 4: Configure DNS Route

Route a subdomain to your tunnel:

```bash
cloudflared tunnel route dns n8n-tunnel n8n.yourdomain.com
```

Replace `yourdomain.com` with your actual domain.

---

## Step 5: Create Tunnel Config (Optional)

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: <TUNNEL_UUID>
credentials-file: /Users/<username>/.cloudflared/<TUNNEL_UUID>.json

ingress:
  - hostname: n8n.yourdomain.com
    service: http://localhost:5678
  - service: http_status:404
```

---

## Step 6: Run Everything

### Option A: Use the Script (Recommended)

```bash
./scripts/start-n8n-with-tunnel.sh
```

The script will:
1. Stop/remove existing n8n container
2. Start the Cloudflare tunnel
3. Start n8n Docker with correct WEBHOOK_URL

### Option B: Manual Commands

**Terminal 1 - Start Tunnel:**
```bash
cloudflared tunnel run n8n-tunnel
```

**Terminal 2 - Start n8n:**
```bash
docker run -d --name n8n \
  --restart unless-stopped \
  -p 5678:5678 \
  -e WEBHOOK_URL="https://n8n.yourdomain.com" \
  -e N8N_HOST="0.0.0.0" \
  -e N8N_PORT=5678 \
  -e N8N_SECURE_COOKIE=false \
  -v n8n_n8n_data:/home/node/.n8n \
  n8nio/n8n
```

---

## Quick Start Commands

```bash
# One-time setup
cloudflared tunnel login
cloudflared tunnel create n8n-tunnel
cloudflared tunnel route dns n8n-tunnel n8n.yourdomain.com

# Daily usage
./scripts/start-n8n-with-tunnel.sh
```

---

## Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `WEBHOOK_URL` | Public URL for webhooks | Required |
| `N8N_HOST` | Host to bind to | `0.0.0.0` |
| `N8N_PORT` | Port to listen on | `5678` |
| `N8N_SECURE_COOKIE` | Require HTTPS for cookies | `false` |

---

## Troubleshooting

### Tunnel won't start
```bash
# Check tunnel status
cloudflared tunnel list

# Check tunnel info
cloudflared tunnel info n8n-tunnel
```

### Webhooks not working
1. Verify WEBHOOK_URL matches your tunnel hostname
2. Check tunnel is running: `cloudflared tunnel run n8n-tunnel`
3. Test the URL: `curl https://n8n.yourdomain.com`

### Container issues
```bash
# View logs
docker logs n8n

# Restart container
docker restart n8n
```

---

## Security Notes

- Cloudflare Tunnel encrypts traffic end-to-end
- No ports need to be opened on your firewall
- Tunnel credentials are stored locally
- Consider enabling Cloudflare Access for additional authentication

---

## Related Files

- Script: [start-n8n-with-tunnel.sh](../scripts/start-n8n-with-tunnel.sh)
- n8n Workflows: [n8n/workflows/](../n8n/workflows/)
