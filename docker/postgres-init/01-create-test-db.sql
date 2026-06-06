-- 测试库（仅首次初始化 volume 时执行）
SELECT 'CREATE DATABASE docpaws_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'docpaws_test')\gexec
