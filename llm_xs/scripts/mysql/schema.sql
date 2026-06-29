-- 小博士 MySQL 预留表结构（幂等，可重复执行）
-- 字符集 utf8mb4，支持中文与 emoji

CREATE TABLE IF NOT EXISTS kids_user_profiles (
    user_id      VARCHAR(128)  NOT NULL PRIMARY KEY COMMENT '派生后的 user_id',
    name         VARCHAR(64)   NOT NULL DEFAULT '' COMMENT '姓名',
    grade        VARCHAR(32)   NOT NULL DEFAULT '' COMMENT '年级',
    extra_json   JSON          NULL COMMENT '扩展字段',
    created_at   DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at   DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    INDEX idx_updated (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS kids_chat_logs (
    id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id      VARCHAR(128)  NOT NULL,
    thread_id    VARCHAR(128)  NOT NULL DEFAULT '',
    question     TEXT          NOT NULL,
    answer       TEXT          NOT NULL,
    mode         VARCHAR(16)   NOT NULL DEFAULT 'offline' COMMENT 'online | offline',
    request_id   VARCHAR(64)   NULL,
    created_at   DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    INDEX idx_user_time (user_id, created_at),
    INDEX idx_thread (thread_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS kids_quiz_records (
    id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id      VARCHAR(128)  NOT NULL,
    grade        VARCHAR(32)   NOT NULL,
    subject      VARCHAR(32)   NOT NULL,
    total        INT UNSIGNED  NOT NULL DEFAULT 0,
    correct      INT UNSIGNED  NOT NULL DEFAULT 0,
    score        INT UNSIGNED  NOT NULL DEFAULT 0 COMMENT '百分制',
    detail_json  JSON          NULL COMMENT '逐题明细（可选）',
    created_at   DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    INDEX idx_user_time (user_id, created_at),
    INDEX idx_subject (subject, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS kids_quiz_sessions (
    session_id   VARCHAR(128)  NOT NULL PRIMARY KEY COMMENT '出题会话 ID',
    principal    VARCHAR(256)  NOT NULL COMMENT '鉴权 principal（防 IDOR）',
    quiz_json    JSON          NOT NULL COMMENT '完整题目含答案',
    expires_at   DATETIME(6)   NOT NULL COMMENT '过期时间',
    consumed_at  DATETIME(6)   NULL COMMENT '判分消耗时间，NULL=未消费',
    created_at   DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    INDEX idx_expires (expires_at),
    INDEX idx_principal (principal),
    INDEX idx_consumed (consumed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS kids_parent_consent (
    user_id          VARCHAR(128)  NOT NULL PRIMARY KEY COMMENT '派生后的 user_id',
    parent_name      VARCHAR(64)   NOT NULL DEFAULT '' COMMENT '家长/监护人姓名',
    parent_email     VARCHAR(128)  NULL COMMENT '联系邮箱（可选）',
    consent_version  VARCHAR(32)   NOT NULL COMMENT '同意的政策版本',
    granted_at       DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    ip_address       VARCHAR(64)   NULL,
    revoked_at       DATETIME(6)   NULL COMMENT '撤销同意时间',
    INDEX idx_granted (granted_at),
    INDEX idx_version (consent_version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
