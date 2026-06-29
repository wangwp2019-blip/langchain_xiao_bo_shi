#!/bin/sh
# backup-cron 容器入口
set -eu
mkdir -p /var/log
touch /var/log/kid-backup.log
crontab /etc/cron.d/kid-backup
echo "Cron 备份已启动，日志: /var/log/kid-backup.log"
exec crond -f -l 2
