#!/bin/bash
set -e

echo "=================================================="
echo "🚀 BingX Telegram Bot - GCP 자동 설치 & 배포 스크립트"
echo "=================================================="

# 1. 시스템 패키지 설치
echo "📦 시스템 패키지 업데이트 및 필수 패키지 설치 중..."
sudo apt update -y
sudo apt install -y python3 python3-pip python3-venv git

CURRENT_USER=$(whoami)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

cd "$SCRIPT_DIR"

# 2. Python 가상환경 구성
echo "🐍 Python 가상환경(.venv) 설정 중..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 3. .env 환경설정 확인
if [ ! -f ".env" ]; then
    echo "⚠️ .env 파일이 없습니다. .env.example을 복사하여 생성합니다."
    cp .env.example .env
    echo "❗ .env 파일에 실제 API 키와 텔레그램 토큰을 입력해야 합니다."
    echo "   'nano .env' 명령어로 입력해주세요."
fi

# 4. systemd 서비스 등록 (24시간 무중단 & 재부팅 시 자동 시작)
echo "⚙️ systemd 서비스 등록 중..."
SERVICE_FILE="/etc/systemd/system/bingx-bot.service"

sudo bash -c "cat <<EOF > $SERVICE_FILE
[Unit]
Description=BingX Telegram Trading Bot
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=$SCRIPT_DIR/.venv/bin/python $SCRIPT_DIR/telegram_bot.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF"

sudo systemctl daemon-reload
sudo systemctl enable bingx-bot
sudo systemctl restart bingx-bot

echo "=================================================="
echo "🎉 배포 완료! 봇이 백그라운드에서 24시간 실행됩니다."
echo "=================================================="
echo "💡 상태 확인 명령어: sudo systemctl status bingx-bot"
echo "💡 실시간 로그 확인: journalctl -u bingx-bot -f"
echo "💡 봇 재시작 명령어: sudo systemctl restart bingx-bot"
echo "💡 봇 중지 명령어:   sudo systemctl stop bingx-bot"
echo "=================================================="
