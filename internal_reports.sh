#!/bin/bash

# Скрипт для генерации внутренних отчетов из базы данных
#
# Использование:
#   ./internal_reports.sh
#
# Требует переменные окружения:
#   DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
#
# Или можно передать параметры:
#   ./internal_reports.sh -h host -p port -d database -U user -W password
#
# Отчеты:
#   1. Статистика пользователей
#      1.1. Общая статистика (всего, не заблокированных)
#      1.2. Прирост пользователей (за сегодня и вчера)
#      1.3. Прирост по источникам (лендинг / директ→бот / органика)
#   2. Полная воронка конверсий (регистрация → гадание → пейволл → покупка)
#      2.1. Общая воронка (все время) — включено
#      2.2. По периодам (до/после 02.02.26) — пока отключено
#      2.3. По источникам траффика — пока отключено
#   3. Статистика оплат (succeeded и pending)
#   4. Проверка балансов гаданий (пользователи с нулевым балансом)
#   5. Анализ источников пейволла
#   6. Список пользователей, которые не заблокировали бота
#   7. Количество гаданий за последние 3 дня (с разбивкой по источникам)
#
# Все отчеты исключают пользователей: 3260473, 129045679 - я, 200748988 - тех акк Димы
# Таблицы: max_users, max_conversions, max_payments, max_user_balances, max_divinations

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ID пользователей "мы" для исключения (Max-бот)
EXCLUDE_USERS="(3260473, 129045679, 200748988)"

# Функция для вывода заголовка
print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# Функция для вывода ошибки
print_error() {
    echo -e "${RED}❌ Ошибка: $1${NC}"
}

# Функция для вывода успеха
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Проверка наличия psql
if ! command -v psql &> /dev/null; then
    print_error "psql не найден. Установите PostgreSQL client."
    exit 1
fi

# Парсинг аргументов командной строки
DB_HOST="${DB_HOST:-35.234.89.2}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-tg_bot_db}"
DB_USER="${DB_USER:-tg_bot_user}"
DB_PASSWORD="${DB_PASSWORD:-16Dima12}"

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--host)
            DB_HOST="$2"
            shift 2
            ;;
        -p|--port)
            DB_PORT="$2"
            shift 2
            ;;
        -d|--database)
            DB_NAME="$2"
            shift 2
            ;;
        -U|--user)
            DB_USER="$2"
            shift 2
            ;;
        -W|--password)
            DB_PASSWORD="$2"
            shift 2
            ;;
        *)
            echo "Неизвестный параметр: $1"
            echo "Использование: $0 [-h host] [-p port] [-d database] [-U user] [-W password]"
            exit 1
            ;;
    esac
done

# Если пароль не указан, запрашиваем его
if [ -z "$DB_PASSWORD" ]; then
    echo -n "Введите пароль для пользователя $DB_USER: "
    read -s DB_PASSWORD
    echo ""
fi

# Экспорт пароля для psql
export PGPASSWORD="$DB_PASSWORD"

# Проверка подключения к БД
print_header "Проверка подключения к базе данных"
if psql -h "$DB_HOST" -p "$DB_PORT" -d "$DB_NAME" -U "$DB_USER" -c "SELECT 1;" > /dev/null 2>&1; then
    print_success "Подключение к БД установлено"
else
    print_error "Не удалось подключиться к базе данных"
    echo "Проверьте параметры подключения:"
    echo "  Host: $DB_HOST"
    echo "  Port: $DB_PORT"
    echo "  Database: $DB_NAME"
    echo "  User: $DB_USER"
    exit 1
fi

# Функция для выполнения SQL запроса
execute_query() {
    local query="$1"
    local description="$2"
    
    print_header "$description"
    
    # Отключаем пейджер и используем красивый табличный формат
    PAGER=cat psql -h "$DB_HOST" -p "$DB_PORT" -d "$DB_NAME" -U "$DB_USER" \
        -c "$query" \
        --pset=border=2 \
        --pset=format=aligned \
        --pset=tuples_only=off \
        2>&1
    
    if [ $? -eq 0 ]; then
        print_success "Запрос выполнен успешно"
    else
        print_error "Ошибка при выполнении запроса"
    fi
}

# 1. Кол-во пользователей уникальных всего и не заблокированных, прирост за вчера
print_header "1. Статистика пользователей (кроме нас)"
QUERY1="
SELECT 
    COUNT(DISTINCT user_id) as \"Всего уникальных пользователей\",
    COUNT(DISTINCT CASE WHEN is_blocked = FALSE THEN user_id END) as \"Не заблокированных\",
    COUNT(DISTINCT CASE WHEN is_blocked = TRUE THEN user_id END) as \"Заблокированных\"
FROM max_users
WHERE user_id NOT IN $EXCLUDE_USERS;
"

QUERY1_GROWTH="
WITH today_users AS (
    SELECT COUNT(DISTINCT user_id) as count
    FROM max_users
    WHERE user_id NOT IN $EXCLUDE_USERS
        AND DATE(created_at) <= CURRENT_DATE
),
yesterday_users AS (
    SELECT COUNT(DISTINCT user_id) as count
    FROM max_users
    WHERE user_id NOT IN $EXCLUDE_USERS
        AND DATE(created_at) <= CURRENT_DATE - INTERVAL '1 day'
),
day_before_users AS (
    SELECT COUNT(DISTINCT user_id) as count
    FROM max_users
    WHERE user_id NOT IN $EXCLUDE_USERS
        AND DATE(created_at) <= CURRENT_DATE - INTERVAL '2 days'
)
SELECT 
    t.count as \"Всего на сегодня\",
    y.count as \"Всего на вчера\",
    d.count as \"Всего на позавчера\",
    (t.count - y.count) as \"Прирост за сегодня\",
    (y.count - d.count) as \"Прирост за вчера\"
FROM today_users t, yesterday_users y, day_before_users d;
"

QUERY1_CLIENT_ID="
WITH registrations AS (
    SELECT 
        c.user_id,
        CASE 
            WHEN u.yclid IS NOT NULL AND u.yclid != '' THEN 'Директ → бот (yclid)'
            WHEN u.client_id IS NOT NULL AND u.client_id != '' THEN 'Лендинг (client_id)' 
            ELSE 'Органика' 
        END as client_type,
        DATE(c.conversion_datetime) as reg_date
    FROM max_conversions c
    LEFT JOIN max_users u ON c.user_id = u.user_id
    WHERE c.conversion_type = 'registration'
        AND c.user_id NOT IN $EXCLUDE_USERS
)
SELECT 
    client_type as \"Источник\",
    COUNT(DISTINCT CASE WHEN reg_date = CURRENT_DATE THEN user_id END) as \"Прирост за сегодня\",
    COUNT(DISTINCT CASE WHEN reg_date = CURRENT_DATE - INTERVAL '1 day' THEN user_id END) as \"Прирост за вчера\",
    COUNT(DISTINCT user_id) as \"Всего\"
FROM registrations
GROUP BY client_type
ORDER BY client_type;
"

QUERY1_LAST_REGISTRATIONS="
SELECT 
    u.user_id as \"User ID\",
    COALESCE(NULLIF(trim(u.full_name), ''), u.first_name) as \"Имя\",
    COALESCE(u.email, '—') as \"Email\",
    TO_CHAR(u.created_at, 'DD.MM.YY HH24:MI') as \"Регистрация\",
    CASE 
        WHEN u.yclid IS NOT NULL AND u.yclid != '' THEN 'директ→бот'
        WHEN u.client_id IS NOT NULL AND u.client_id != '' THEN 'лендинг'
        WHEN u.utm_source IS NOT NULL AND u.utm_source != '' THEN u.utm_source
        ELSE 'органика'
    END as \"Источник\",
    COALESCE(u.utm_campaign, '—') as \"Кампания\",
    CASE WHEN u.client_id IS NOT NULL AND u.client_id != '' THEN '✓' ELSE '' END as \"cid\",
    CASE WHEN u.yclid IS NOT NULL AND u.yclid != '' THEN '✓' ELSE '' END as \"yclid\",
    u.is_blocked as \"Блок\"
FROM max_users u
WHERE u.user_id NOT IN $EXCLUDE_USERS
ORDER BY u.created_at DESC
LIMIT 15;
"

QUERY1_DAILY_GROWTH="
SELECT 
    TO_CHAR(DATE(created_at), 'DD.MM.YY') as \"Дата\",
    COUNT(*) as \"Новых\",
    COUNT(CASE WHEN client_id IS NOT NULL AND client_id != '' THEN 1 END) as \"Лендинг\",
    COUNT(CASE WHEN yclid IS NOT NULL AND yclid != '' THEN 1 END) as \"Директ→бот\",
    COUNT(CASE WHEN (client_id IS NULL OR client_id = '') AND (yclid IS NULL OR yclid = '') THEN 1 END) as \"Органика\"
FROM max_users
WHERE user_id NOT IN $EXCLUDE_USERS
    AND created_at >= CURRENT_DATE - INTERVAL '14 days'
GROUP BY DATE(created_at)
ORDER BY DATE(created_at) DESC;
"

execute_query "$QUERY1" "1.1. Общая статистика пользователей"
execute_query "$QUERY1_GROWTH" "1.2. Прирост пользователей"
execute_query "$QUERY1_CLIENT_ID" "1.3. Прирост по источникам (лендинг / директ→бот / органика)"
execute_query "$QUERY1_LAST_REGISTRATIONS" "1.4. Последние 15 регистраций (диагностика)"
execute_query "$QUERY1_DAILY_GROWTH" "1.5. Прирост по дням за последние 14 дней"

# 2. Полная воронка: сколько зашло, погадало, дошло до пейволла, заплатило
print_header "2. Полная воронка конверсий (кроме нас)"

# 2.1 Общая воронка
QUERY2_1="
WITH funnel AS (
    SELECT 
        COUNT(DISTINCT CASE WHEN conversion_type = 'registration' AND user_id NOT IN $EXCLUDE_USERS THEN user_id END) as registered_users,
        COUNT(DISTINCT CASE WHEN conversion_type = 'service_usage' AND user_id NOT IN $EXCLUDE_USERS THEN user_id END) as divination_users,
        COUNT(DISTINCT CASE WHEN conversion_type = 'paywall_reached' AND user_id NOT IN $EXCLUDE_USERS THEN user_id END) as paywall_users
    FROM max_conversions
),
purchases AS (
    SELECT COUNT(DISTINCT user_id) as purchase_users
    FROM max_payments
    WHERE user_id NOT IN $EXCLUDE_USERS
        AND status = 'succeeded'
)
SELECT 
    f.registered_users as \"Зашло в бот\",
    f.divination_users as \"Погадало\",
    f.paywall_users as \"Дошло до пейволла\",
    p.purchase_users as \"Заплатило\",
    ROUND(f.divination_users::numeric / NULLIF(f.registered_users, 0) * 100, 2) as \"Конв. Рег→Гад (%)\",
    ROUND(f.paywall_users::numeric / NULLIF(f.divination_users, 0) * 100, 2) as \"Конв. Гад→Пейв (%)\",
    ROUND(p.purchase_users::numeric / NULLIF(f.paywall_users, 0) * 100, 2) as \"Конв. Пейв→Покуп (%)\",
    ROUND(p.purchase_users::numeric / NULLIF(f.registered_users, 0) * 100, 2) as \"Общ. конв. Рег→Покуп (%)\"
FROM funnel f, purchases p;
"

# 2.2 Воронка разбитая по периодам: до 02/02/26 включительно и после
# Пользователи группируются по дате РЕГИСТРАЦИИ, затем считаем их прохождение по воронке
QUERY2_2="
WITH user_periods AS (
    -- Определяем период регистрации каждого пользователя
    SELECT 
        user_id,
        CASE 
            WHEN DATE(conversion_datetime) <= '2026-02-02' THEN 'До 02.02.26 (вкл.)'
            ELSE 'После 02.02.26'
        END as period
    FROM max_conversions
    WHERE conversion_type = 'registration'
        AND user_id NOT IN $EXCLUDE_USERS
),
funnel AS (
    SELECT 
        up.period,
        COUNT(DISTINCT up.user_id) as registered_users,
        COUNT(DISTINCT CASE WHEN c.conversion_type = 'service_usage' THEN c.user_id END) as divination_users,
        COUNT(DISTINCT CASE WHEN c.conversion_type = 'paywall_reached' THEN c.user_id END) as paywall_users
    FROM user_periods up
    LEFT JOIN max_conversions c ON up.user_id = c.user_id
    GROUP BY up.period
),
purchases_by_period AS (
    SELECT 
        up.period,
        COUNT(DISTINCT p.user_id) as purchase_users
    FROM user_periods up
    INNER JOIN max_payments p ON up.user_id = p.user_id AND p.status = 'succeeded'
    GROUP BY up.period
)
SELECT 
    f.period as \"Период регистрации\",
    f.registered_users as \"Зашло в бот\",
    f.divination_users as \"Погадало\",
    f.paywall_users as \"Дошло до пейволла\",
    COALESCE(pbp.purchase_users, 0) as \"Заплатило\",
    ROUND(f.divination_users::numeric / NULLIF(f.registered_users, 0) * 100, 2) as \"Рег→Гад (%)\",
    ROUND(f.paywall_users::numeric / NULLIF(f.divination_users, 0) * 100, 2) as \"Гад→Пейв (%)\",
    ROUND(COALESCE(pbp.purchase_users, 0)::numeric / NULLIF(f.paywall_users, 0) * 100, 2) as \"Пейв→Покуп (%)\",
    ROUND(COALESCE(pbp.purchase_users, 0)::numeric / NULLIF(f.registered_users, 0) * 100, 2) as \"Рег→Покуп (%)\"
FROM funnel f
LEFT JOIN purchases_by_period pbp ON f.period = pbp.period
ORDER BY f.period;
"

# 2.3 Воронка по источникам (только пользователи, зарегистрированные после 02/02/26)
# Пользователи группируются по наличию client_id / yclid
QUERY2_3="
WITH user_sources AS (
    -- Определяем источник регистрации каждого пользователя (после 02.02.26)
    SELECT 
        c.user_id,
        CASE 
            WHEN u.yclid IS NOT NULL AND u.yclid != '' THEN 'Директ → бот (yclid)'
            WHEN u.client_id IS NOT NULL AND u.client_id != '' THEN 'Лендинг (client_id)' 
            ELSE 'Органика' 
        END as source_type
    FROM max_conversions c
    LEFT JOIN max_users u ON c.user_id = u.user_id
    WHERE c.conversion_type = 'registration'
        AND c.user_id NOT IN $EXCLUDE_USERS
        AND DATE(c.conversion_datetime) > '2026-02-02'
),
funnel AS (
    SELECT 
        us.source_type,
        COUNT(DISTINCT us.user_id) as registered_users,
        COUNT(DISTINCT CASE WHEN c.conversion_type = 'service_usage' THEN c.user_id END) as divination_users,
        COUNT(DISTINCT CASE WHEN c.conversion_type = 'paywall_reached' THEN c.user_id END) as paywall_users
    FROM user_sources us
    LEFT JOIN max_conversions c ON us.user_id = c.user_id
    GROUP BY us.source_type
),
purchases_by_source AS (
    SELECT 
        us.source_type,
        COUNT(DISTINCT p.user_id) as purchase_users
    FROM user_sources us
    INNER JOIN max_payments p ON us.user_id = p.user_id AND p.status = 'succeeded'
    GROUP BY us.source_type
)
SELECT 
    f.source_type as \"Источник траффика\",
    f.registered_users as \"Зашло в бот\",
    f.divination_users as \"Погадало\",
    f.paywall_users as \"Дошло до пейволла\",
    COALESCE(pbs.purchase_users, 0) as \"Заплатило\",
    ROUND(f.divination_users::numeric / NULLIF(f.registered_users, 0) * 100, 2) as \"Рег→Гад (%)\",
    ROUND(f.paywall_users::numeric / NULLIF(f.divination_users, 0) * 100, 2) as \"Гад→Пейв (%)\",
    ROUND(COALESCE(pbs.purchase_users, 0)::numeric / NULLIF(f.paywall_users, 0) * 100, 2) as \"Пейв→Покуп (%)\",
    ROUND(COALESCE(pbs.purchase_users, 0)::numeric / NULLIF(f.registered_users, 0) * 100, 2) as \"Рег→Покуп (%)\"
FROM funnel f
LEFT JOIN purchases_by_source pbs ON f.source_type = pbs.source_type
ORDER BY f.source_type;
"

execute_query "$QUERY2_1" "2.1. Полная воронка конверсий (общая)"
# execute_query "$QUERY2_2" "2.2. Воронка по периоду регистрации (до/после 02.02.26)"
# execute_query "$QUERY2_3" "2.3. Воронка по источникам (зарегистрированные после 02.02.26)"

# 3. Оплаты - succeeded и pending
print_header "3. Статистика оплат (succeeded и pending, кроме нас)"
QUERY3="
SELECT 
    status as \"Статус\",
    COUNT(*) as \"Количество платежей\",
    COUNT(DISTINCT user_id) as \"Уникальных пользователей\",
    SUM(amount_rub) as \"Сумма (руб)\",
    ROUND(AVG(amount_rub), 2) as \"Средний чек (руб)\"
FROM max_payments
WHERE user_id NOT IN $EXCLUDE_USERS
    AND status IN ('succeeded', 'pending')
GROUP BY status
ORDER BY status;
"

QUERY3_DETAIL="
SELECT 
    DATE(p.created_at) as \"Дата\",
    p.status as \"Статус\",
    p.user_id as \"User ID\",
    COALESCE(NULLIF(trim(u.full_name), ''), u.first_name) as \"Имя\",
    COALESCE(u.email, '—') as \"Email\",
    TO_CHAR(u.created_at, 'DD.MM.YY') as \"Дата регистрации\",
    p.amount_rub as \"Сумма (руб)\"
FROM max_payments p
LEFT JOIN max_users u ON p.user_id = u.user_id
WHERE p.user_id NOT IN $EXCLUDE_USERS
    AND p.status IN ('succeeded', 'pending')
ORDER BY DATE(p.created_at) DESC, p.status, p.user_id;
"

execute_query "$QUERY3" "3.1. Общая статистика оплат"
execute_query "$QUERY3_DETAIL" "3.2. Детализация по датам (все платежи)"

# 4. Проверка балансов гаданий - всех у кого 0 и платных, и бесплатных
print_header "4. Проверка балансов гаданий (кроме нас)"
QUERY4="
SELECT 
    COUNT(CASE WHEN ub.free_divinations_remaining = 0 AND ub.paid_divinations_remaining = 0 AND (ub.unlimited_until IS NULL OR ub.unlimited_until < NOW()) THEN 1 END) as \"Нулевой баланс\",
    COUNT(CASE WHEN ub.free_divinations_remaining = 0 AND ub.paid_divinations_remaining = 0 AND (ub.unlimited_until IS NULL OR ub.unlimited_until < NOW()) AND u.is_blocked = TRUE THEN 1 END) as \"из них блок\",
    COUNT(CASE WHEN ub.free_divinations_remaining = 0 AND ub.paid_divinations_remaining > 0 THEN 1 END) as \"Только платные\",
    COUNT(CASE WHEN ub.free_divinations_remaining = 0 AND ub.paid_divinations_remaining > 0 AND u.is_blocked = TRUE THEN 1 END) as \"из них блок \",
    COUNT(CASE WHEN ub.free_divinations_remaining > 0 AND ub.paid_divinations_remaining = 0 THEN 1 END) as \"Только бесплатные\",
    COUNT(CASE WHEN ub.free_divinations_remaining > 0 AND ub.paid_divinations_remaining = 0 AND u.is_blocked = TRUE THEN 1 END) as \"из них блок  \",
    COUNT(CASE WHEN ub.unlimited_until IS NOT NULL AND ub.unlimited_until > NOW() THEN 1 END) as \"Безлимит\",
    COUNT(CASE WHEN ub.unlimited_until IS NOT NULL AND ub.unlimited_until > NOW() AND u.is_blocked = TRUE THEN 1 END) as \"из них блок   \",
    COUNT(CASE WHEN ub.free_divinations_remaining = 1 THEN 1 END) as \"1 бесп.\",
    COUNT(CASE WHEN ub.free_divinations_remaining = 1 AND u.is_blocked = TRUE THEN 1 END) as \"из них блок    \",
    COUNT(CASE WHEN ub.free_divinations_remaining = 2 THEN 1 END) as \"2 бесп.\",
    COUNT(CASE WHEN ub.free_divinations_remaining = 2 AND u.is_blocked = TRUE THEN 1 END) as \"из них блок     \",
    COUNT(CASE WHEN ub.free_divinations_remaining = 3 THEN 1 END) as \"3 бесп.\",
    COUNT(CASE WHEN ub.free_divinations_remaining = 3 AND u.is_blocked = TRUE THEN 1 END) as \"из них блок      \"
FROM max_user_balances ub
JOIN max_users u ON ub.user_id = u.user_id
WHERE u.user_id NOT IN $EXCLUDE_USERS;
"

QUERY4_ZERO="
SELECT string_agg(ub.user_id::text, ' ' ORDER BY ub.total_divinations_used DESC) as user_ids
FROM max_user_balances ub
JOIN max_users u ON ub.user_id = u.user_id
WHERE u.user_id NOT IN $EXCLUDE_USERS
    AND u.is_blocked = FALSE
    AND ub.free_divinations_remaining = 0
    AND ub.paid_divinations_remaining = 0
    AND (ub.unlimited_until IS NULL OR ub.unlimited_until < NOW());
"

execute_query "$QUERY4" "4.1. Общая статистика балансов"
print_header "4.2. Не заблокировавшие пользователи с нулевым балансом (все, отсортировано по использованию)"
# Выводим в одну строку без табличного формата
PAGER=cat psql -h "$DB_HOST" -p "$DB_PORT" -d "$DB_NAME" -U "$DB_USER" \
    -c "$QUERY4_ZERO" \
    --pset=tuples_only=on \
    --pset=format=unaligned \
    2>&1
if [ $? -eq 0 ]; then
    print_success "Запрос выполнен успешно"
else
    print_error "Ошибка при выполнении запроса"
fi

# 5. Анализ источников пейволла
print_header "5. Анализ источников пейволла (кроме нас)"
QUERY5="
SELECT 
    COALESCE(metadata->>'paywall_source', 'unknown') as \"Источник пейволла\",
    COUNT(*) as \"Количество событий\",
    COUNT(DISTINCT user_id) as \"Уникальных пользователей\"
FROM max_conversions
WHERE conversion_type = 'paywall_reached'
    AND user_id NOT IN $EXCLUDE_USERS
GROUP BY metadata->>'paywall_source'
ORDER BY COUNT(*) DESC;
"

QUERY5_CONVERSION="
SELECT 
    COALESCE(c1.metadata->>'paywall_source', 'unknown') as \"Источник пейволла\",
    COUNT(DISTINCT c1.user_id) as \"Дошло до пейволла\",
    COUNT(DISTINCT CASE WHEN p.status = 'succeeded' THEN p.user_id END) as \"Купило после пейволла\",
    ROUND(
        COUNT(DISTINCT CASE WHEN p.status = 'succeeded' THEN p.user_id END)::numeric / 
        NULLIF(COUNT(DISTINCT c1.user_id), 0) * 100, 
        2
    ) as \"Конверсия пейволл → покупка (%)\"
FROM max_conversions c1
LEFT JOIN max_payments p ON c1.user_id = p.user_id 
    AND p.status = 'succeeded'
    AND p.created_at > c1.conversion_datetime
WHERE c1.conversion_type = 'paywall_reached'
    AND c1.user_id NOT IN $EXCLUDE_USERS
GROUP BY c1.metadata->>'paywall_source'
ORDER BY COUNT(DISTINCT c1.user_id) DESC;
"

execute_query "$QUERY5" "5.1. Статистика по источникам пейволла"
execute_query "$QUERY5_CONVERSION" "5.2. Конверсия от пейволла к покупке по источникам"

# 6. Список пользователей, которые не заблокировали бота
print_header "6. Пользователи, которые не заблокировали бота (кроме нас)"
QUERY6="
SELECT string_agg(u.user_id::text, ' ' ORDER BY u.created_at DESC) as user_ids
FROM max_users u
WHERE u.user_id NOT IN $EXCLUDE_USERS
    AND u.is_blocked = FALSE;
"

print_header "6.1. Список пользователей, которые не заблокировали бота (все, отсортировано по дате регистрации)"
# Выводим в одну строку без табличного формата
PAGER=cat psql -h "$DB_HOST" -p "$DB_PORT" -d "$DB_NAME" -U "$DB_USER" \
    -c "$QUERY6" \
    --pset=tuples_only=on \
    --pset=format=unaligned \
    2>&1
if [ $? -eq 0 ]; then
    print_success "Запрос выполнен успешно"
else
    print_error "Ошибка при выполнении запроса"
fi

# 7. Количество гаданий за последние 3 дня с разбивкой по источникам
print_header "7. Гадания за последние 3 дня (кроме нас)"

QUERY7_TOTAL="
SELECT 
    TO_CHAR(DATE(d.created_at), 'DD.MM.YY') as \"Дата\",
    COUNT(*) as \"Всего гаданий\",
    COUNT(DISTINCT d.user_id) as \"Уникальных пользователей\",
    ROUND(COUNT(*)::numeric / NULLIF(COUNT(DISTINCT d.user_id), 0), 2) as \"Гаданий на чел.\"
FROM max_divinations d
WHERE d.user_id NOT IN $EXCLUDE_USERS
    AND d.created_at >= CURRENT_DATE - INTERVAL '2 days'
GROUP BY DATE(d.created_at)
ORDER BY DATE(d.created_at) DESC;
"

QUERY7_BY_SOURCE="
SELECT 
    TO_CHAR(DATE(d.created_at), 'DD.MM.YY') as \"Дата\",
    CASE 
        WHEN u.yclid IS NOT NULL AND u.yclid != '' THEN 'Директ → бот'
        WHEN u.client_id IS NOT NULL AND u.client_id != '' THEN 'Лендинг'
        ELSE 'Органика'
    END as \"Источник\",
    COUNT(*) as \"Гаданий\",
    COUNT(DISTINCT d.user_id) as \"Пользователей\"
FROM max_divinations d
JOIN max_users u ON d.user_id = u.user_id
WHERE d.user_id NOT IN $EXCLUDE_USERS
    AND d.created_at >= CURRENT_DATE - INTERVAL '2 days'
GROUP BY DATE(d.created_at),
    CASE 
        WHEN u.yclid IS NOT NULL AND u.yclid != '' THEN 'Директ → бот'
        WHEN u.client_id IS NOT NULL AND u.client_id != '' THEN 'Лендинг'
        ELSE 'Органика'
    END
ORDER BY DATE(d.created_at) DESC, \"Источник\";
"

execute_query "$QUERY7_TOTAL" "7.1. Общее количество гаданий по дням (последние 3 дня)"
execute_query "$QUERY7_BY_SOURCE" "7.2. Гадания по источникам (последние 3 дня)"

# Итоговое сообщение
print_header "Отчет завершен"
print_success "Все запросы выполнены"
echo ""
echo "Дата и время выполнения: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Очистка пароля из окружения
unset PGPASSWORD

