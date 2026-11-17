#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Native Ubuntu 22.04 Installer for LiveKit Server + LiveKit SIP (Zero Docker)
# Target: AWS EC2 g5.xlarge (eu-west-1 Dublin)
# ==============================================================================

echo "=============================================================================="
echo " [1/6] Installing System Dependencies & Redis on Ubuntu..."
echo "=============================================================================="
sudo apt-get update -y
sudo apt-get install -y \
    redis-server \
    curl \
    wget \
    git \
    build-essential \
    pkg-config \
    libopus-dev \
    libopusfile-dev \
    libsoxr-dev \
    jq \
    openssl

sudo systemctl enable redis-server
sudo systemctl restart redis-server

echo "=============================================================================="
echo " [2/6] Installing Native LiveKit Server & LiveKit CLI (lk)..."
echo "=============================================================================="
if ! command -v livekit-server >/dev/null 2>&1; then
    curl -sSL https://get.livekit.io | bash
else
    echo "  ✓ livekit-server already installed: $(command -v livekit-server)"
fi

if ! command -v lk >/dev/null 2>&1; then
    curl -sSL https://get.livekit.io/cli | bash
else
    echo "  ✓ lk CLI already installed: $(command -v lk)"
fi

echo "=============================================================================="
echo " [3/6] Installing Native LiveKit SIP Service (livekit-sip)..."
echo "=============================================================================="
if ! command -v livekit-sip >/dev/null 2>&1; then
    # Install Go 1.23+ if not present to compile native livekit-sip linked against Ubuntu's libopus/libsoxr
    if ! command -v go >/dev/null 2>&1 || [[ "$(go version | awk '{print $3}')" < "go1.22" ]]; then
        echo "  -> Installing Go 1.23.4 for native livekit-sip build..."
        wget -q https://go.dev/dl/go1.23.4.linux-amd64.tar.gz -O /tmp/go.tar.gz
        sudo rm -rf /usr/local/go
        sudo tar -C /usr/local -xzf /tmp/go.tar.gz
        export PATH="/usr/local/go/bin:$PATH"
    fi
    export PATH="/usr/local/go/bin:$HOME/go/bin:$PATH"
    echo "  -> Building native livekit-sip binary..."
    TMP_SIP_DIR=$(mktemp -d)
    git clone --depth 1 https://github.com/livekit/sip.git "$TMP_SIP_DIR"
    pushd "$TMP_SIP_DIR" >/dev/null
    go build -o /tmp/livekit-sip ./cmd/livekit-sip
    sudo mv /tmp/livekit-sip /usr/local/bin/livekit-sip
    sudo chmod +x /usr/local/bin/livekit-sip
    popd >/dev/null
    rm -rf "$TMP_SIP_DIR"
else
    echo "  ✓ livekit-sip already installed: $(command -v livekit-sip)"
fi

echo "=============================================================================="
echo " [4/6] Generating /etc/livekit Configuration & Credentials..."
echo "=============================================================================="
sudo mkdir -p /etc/livekit

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_DIR/.env"
touch "$ENV_FILE"

# Load or generate API Key and Secret
EXISTING_KEY=$(grep -E '^LIVEKIT_API_KEY=' "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' | tr -d "'" || true)
EXISTING_SECRET=$(grep -E '^LIVEKIT_API_SECRET=' "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' | tr -d "'" || true)

LIVEKIT_API_KEY="${EXISTING_KEY:-APIClinicDeirdre}"
LIVEKIT_API_SECRET="${EXISTING_SECRET:-$(openssl rand -hex 24)}"
EC2_PUBLIC_IP=$(curl -s --max-time 3 http://checkip.amazonaws.com || curl -s --max-time 3 https://ifconfig.me || echo "127.0.0.1")

sudo tee /etc/livekit/livekit.yaml >/dev/null <<EOF
port: 7880
bind_addresses:
  - ""
rtc:
  tcp_port: 7881
  port_range_start: 50000
  port_range_end: 60000
  use_external_ip: true
redis:
  address: 127.0.0.1:6379
keys:
  ${LIVEKIT_API_KEY}: ${LIVEKIT_API_SECRET}
webhook:
  api_key: ${LIVEKIT_API_KEY}
  urls:
    - http://127.0.0.1:8998/livekit/webhook
logging:
  level: info
EOF

sudo tee /etc/livekit/sip.yaml >/dev/null <<EOF
api_key: ${LIVEKIT_API_KEY}
api_secret: ${LIVEKIT_API_SECRET}
ws_url: ws://127.0.0.1:7880
redis:
  address: 127.0.0.1:6379
sip_port: 5060
rtp_port: 10000-20000
use_external_ip: true
logging:
  level: info
EOF

# Update .env in project directory
grep -q '^LIVEKIT_URL=' "$ENV_FILE" || echo 'LIVEKIT_URL="ws://127.0.0.1:7880"' >> "$ENV_FILE"
if ! grep -q '^LIVEKIT_API_KEY=' "$ENV_FILE"; then
    echo "LIVEKIT_API_KEY=\"${LIVEKIT_API_KEY}\"" >> "$ENV_FILE"
fi
if ! grep -q '^LIVEKIT_API_SECRET=' "$ENV_FILE"; then
    echo "LIVEKIT_API_SECRET=\"${LIVEKIT_API_SECRET}\"" >> "$ENV_FILE"
fi

echo "=============================================================================="
echo " [5/6] Creating & Starting systemd Services (livekit-server & livekit-sip)..."
echo "=============================================================================="
sudo tee /etc/systemd/system/livekit-server.service >/dev/null <<EOF
[Unit]
Description=LiveKit WebRTC Server
After=network.target redis-server.service
Requires=redis-server.service

[Service]
Type=simple
ExecStart=/usr/local/bin/livekit-server --config /etc/livekit/livekit.yaml
Restart=always
RestartSec=3
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/livekit-sip.service >/dev/null <<EOF
[Unit]
Description=LiveKit SIP Gateway (VoIPLine.ie Bridge)
After=network.target redis-server.service livekit-server.service
Requires=livekit-server.service

[Service]
Type=simple
ExecStart=/usr/local/bin/livekit-sip --config /etc/livekit/sip.yaml
Restart=always
RestartSec=3
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable livekit-server livekit-sip
sudo systemctl restart livekit-server
sleep 2
sudo systemctl restart livekit-sip

echo "=============================================================================="
echo " [6/6] Installing Python LiveKit SDKs into Active Environment..."
echo "=============================================================================="
pip install --upgrade livekit livekit-api python-dotenv

echo ""
echo "=============================================================================="
echo " ✅ LIVEKIT + LIVEKIT SIP RUNNING NATIVELY ON UBUNTU!"
echo "=============================================================================="
echo " • EC2 Public SIP Endpoint:  sip:${EC2_PUBLIC_IP}:5060"
echo " • Local LiveKit WebSocket:  ws://127.0.0.1:7880"
echo " • Credentials saved to:     ${ENV_FILE}"
echo ""
echo " NEXT STEP: Register your VoIPLine.ie phone number:"
echo "   python livekit_setup/setup_sip_trunk.py --phone +3531XXXXXXX"
echo "=============================================================================="
