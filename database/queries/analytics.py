"""Analytics aggregation queries."""
from database import pool as db


async def quick_stats() -> dict:
    users = await db.fetchval("SELECT COUNT(*) FROM users") or 0
    titles = await db.fetchval("SELECT COUNT(*) FROM titles WHERE is_active=TRUE") or 0
    opens_today = await db.fetchval(
        "SELECT total_app_opens FROM daily_analytics WHERE date=CURRENT_DATE"
    ) or 0
    clicks_today = await db.fetchval(
        "SELECT total_clicks FROM daily_analytics WHERE date=CURRENT_DATE"
    ) or 0
    pending_requests = await db.fetchval(
        "SELECT COUNT(*) FROM content_requests WHERE status='pending'"
    ) or 0
    return {
        "users": users,
        "titles": titles,
        "opens_today": opens_today,
        "clicks_today": clicks_today,
        "pending_requests": pending_requests,
    }


async def range_stats() -> dict:
    today = await db.fetchrow(
        "SELECT * FROM daily_analytics WHERE date=CURRENT_DATE"
    )
    week = await db.fetchrow(
        """SELECT COALESCE(SUM(total_app_opens),0) opens, COALESCE(SUM(total_clicks),0) clicks,
                  COALESCE(SUM(total_joins),0) joins, COALESCE(SUM(total_new_users),0) new_users
           FROM daily_analytics WHERE date > CURRENT_DATE - INTERVAL '7 days'"""
    )
    all_time = await db.fetchrow(
        """SELECT COALESCE(SUM(total_clicks),0) clicks, COALESCE(SUM(total_joins),0) joins
           FROM titles t"""
    )
    return {"today": dict(today) if today else {}, "week": dict(week), "all_time": dict(all_time)}


async def last_7_days():
    return await db.fetch(
        """SELECT date, total_app_opens, total_clicks
           FROM daily_analytics
           WHERE date > CURRENT_DATE - INTERVAL '7 days'
           ORDER BY date"""
    )


async def top_titles_week(limit=5):
    return await db.fetch(
        """SELECT t.title, COALESCE(SUM(tds.clicks),0) clicks
           FROM title_daily_stats tds JOIN titles t ON t.title_id=tds.title_id
           WHERE tds.date > CURRENT_DATE - INTERVAL '7 days'
           GROUP BY t.title ORDER BY clicks DESC LIMIT $1""",
        limit,
    )


async def add_content_request(user_id: int, title: str, category: str):
    return await db.fetchrow(
        """INSERT INTO content_requests (user_id, title_requested, category)
           VALUES ($1,$2,$3) RETURNING request_id""",
        user_id, title, category,
    )


async def pending_requests():
    return await db.fetch(
        "SELECT * FROM content_requests WHERE status='pending' ORDER BY created_at DESC LIMIT 20"
    )


async def set_request_status(request_id: int, status: str):
    await db.execute(
        "UPDATE content_requests SET status=$1 WHERE request_id=$2", status, request_id
    )


async def register_new_user_today():
    await db.execute(
        """INSERT INTO daily_analytics (date, total_new_users) VALUES (CURRENT_DATE,1)
           ON CONFLICT (date) DO UPDATE SET total_new_users=daily_analytics.total_new_users+1"""
    )


async def register_app_open_today():
    await db.execute(
        """INSERT INTO daily_analytics (date, total_app_opens) VALUES (CURRENT_DATE,1)
           ON CONFLICT (date) DO UPDATE SET total_app_opens=daily_analytics.total_app_opens+1"""
    )
