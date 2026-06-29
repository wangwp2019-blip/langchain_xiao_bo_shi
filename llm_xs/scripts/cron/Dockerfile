FROM alpine:3.20

RUN apk add --no-cache bash curl dcron postgresql16-client mysql-client

WORKDIR /app

COPY scripts/cron/crontab /etc/cron.d/kid-backup
COPY scripts/cron/docker-entrypoint.sh /entrypoint.sh
RUN chmod 0644 /etc/cron.d/kid-backup && chmod +x /entrypoint.sh

ENV BACKUP_MODE=network \
    BACKUP_DIR=/app/backups

ENTRYPOINT ["/entrypoint.sh"]
