#!/usr/bin/env bash
# EC2 の中で root として実行される（GitHub Actions -> SSM Run Command 経由）。
# 何度実行しても同じ結果になるように書いてある。新品のインスタンスでもそのまま動く。
#
#   使い方: remote_deploy.sh <リリースID（コミットSHA）>
#   前提:   /opt/haruki-playlist/releases/<リリースID>/ に成果物が展開済み
set -euo pipefail

RELEASE_ID="${1:?リリースIDを指定してください}"
APP_DIR=/opt/haruki-playlist
RELEASE_DIR="$APP_DIR/releases/$RELEASE_ID"
ENV_DIR=/etc/haruki-playlist
SERVICE=haruki-playlist
PORT=8080
KEEP_RELEASES=3

log() { echo "==> $*"; }

health_ok() {
  # 起動直後は応答しないことがあるので、最大30秒待つ
  for _ in $(seq 1 30); do
    body="$(curl -fsS "http://127.0.0.1:$PORT/api/health" 2>/dev/null || true)"
    if grep -q "\"version\":\"$1\"" <<< "$body"; then
      return 0
    fi
    sleep 1
  done
  return 1
}

log "OS パッケージ"
if ! command -v python3.11 >/dev/null; then
  dnf install -y -q python3.11 python3.11-pip
fi
id -u haruki >/dev/null 2>&1 || useradd --system --no-create-home --shell /sbin/nologin haruki

log "Python 依存パッケージ"
python3.11 -m venv "$RELEASE_DIR/.venv"
"$RELEASE_DIR/.venv/bin/pip" install --quiet --disable-pip-version-check -r "$RELEASE_DIR/backend/requirements.txt"

log "設定ファイル"
install -d -m 750 -o root -g haruki "$ENV_DIR"
# APIキーが未登録でもデプロイは通す（その場合はルールベースだけで動く）
API_KEY="$(aws ssm get-parameter --name /haruki-playlist/anthropic-api-key --with-decryption \
  --query Parameter.Value --output text 2>/dev/null || true)"
umask 027
{
  echo "HARUKI_VERSION=$RELEASE_ID"
  if [ -n "$API_KEY" ]; then echo "ANTHROPIC_API_KEY=$API_KEY"; fi
} > "$ENV_DIR/env.new"
chown root:haruki "$ENV_DIR/env.new"
mv "$ENV_DIR/env.new" "$ENV_DIR/env"

cat > /etc/systemd/system/$SERVICE.service <<UNIT
[Unit]
Description=Haruki Murakami Playlist
After=network-online.target
Wants=network-online.target

[Service]
User=haruki
WorkingDirectory=$APP_DIR/current/backend
EnvironmentFile=$ENV_DIR/env
# レート制限などをプロセス内メモリで持つため、ワーカーは1つ
ExecStart=$APP_DIR/current/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
Restart=always
RestartSec=2
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --quiet $SERVICE

log "切り替え"
PREVIOUS="$(readlink -f "$APP_DIR/current" 2>/dev/null || true)"
ln -sfn "$RELEASE_DIR" "$APP_DIR/current"
systemctl restart $SERVICE

if health_ok "$RELEASE_ID"; then
  log "起動を確認しました: $RELEASE_ID"
else
  log "新しいリリースが起動しません。直前のログ:"
  journalctl -u $SERVICE -n 40 --no-pager || true
  if [ -n "$PREVIOUS" ] && [ -d "$PREVIOUS" ] && [ "$PREVIOUS" != "$RELEASE_DIR" ]; then
    log "前のリリースに戻します: $(basename "$PREVIOUS")"
    sed -i "s/^HARUKI_VERSION=.*/HARUKI_VERSION=$(basename "$PREVIOUS")/" "$ENV_DIR/env"
    ln -sfn "$PREVIOUS" "$APP_DIR/current"
    systemctl restart $SERVICE
  fi
  exit 1
fi

log "古いリリースの掃除"
cd "$APP_DIR/releases"
ls -1t | tail -n +$((KEEP_RELEASES + 1)) | while read -r old; do
  [ "$APP_DIR/releases/$old" = "$RELEASE_DIR" ] || rm -rf -- "$old"
done
log "完了"
