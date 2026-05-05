#!/bin/bash
# ============================================================
# DB 유지보수 스크립트
# 사용법: ./db_maintenance.sh [vacuum|analyze|reindex|stats]
# ============================================================
set -euo pipefail

COMMAND="${1:-stats}"
ENV="${2:-production}"
DB_HOST="${DB_HOST:-localhost}"
DB_NAME="sepang"
DB_USER="sepang"

case "$COMMAND" in
  vacuum)
    echo "🧹 VACUUM ANALYZE 실행..."
    psql "postgresql://$DB_USER@$DB_HOST/$DB_NAME" \
      -c "VACUUM ANALYZE orders, shops, users, settlements, order_photos;"
    ;;
  reindex)
    echo "🔨 PostGIS 인덱스 재구축..."
    psql "postgresql://$DB_USER@$DB_HOST/$DB_NAME" << 'SQL'
      REINDEX INDEX CONCURRENTLY idx_shops_location_gist;
      REINDEX INDEX CONCURRENTLY idx_orders_status_deadline;
      REINDEX INDEX CONCURRENTLY idx_orders_customer_ordered;
SQL
    ;;
  stats)
    echo "📊 DB 상태 조회..."
    psql "postgresql://$DB_USER@$DB_HOST/$DB_NAME" << 'SQL'
      SELECT
        schemaname,
        tablename,
        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
        n_live_tup AS live_rows,
        n_dead_tup AS dead_rows,
        last_vacuum,
        last_analyze
      FROM pg_stat_user_tables
      ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
SQL
    ;;
  sla)
    echo "🚨 SLA 위험 주문 현황..."
    psql "postgresql://$DB_USER@$DB_HOST/$DB_NAME" \
      -c "SELECT id, status, ROUND(hours_left::numeric, 1) AS hours_left, shop_name, customer_name FROM vw_sla_at_risk ORDER BY hours_left;"
    ;;
esac
