from app.services.db.core import query_one


async def get_or_create_user(user_id: str) -> dict:
    row = await query_one(
        """
        INSERT INTO users (user_id) VALUES (%s)
        ON CONFLICT (user_id) DO UPDATE SET user_id = EXCLUDED.user_id
        RETURNING user_id, is_pro, pro_since, created_at
        """,
        (user_id,),
    )
    return row


async def set_pro(user_id: str, is_pro: bool) -> dict | None:
    return await query_one(
        """
        UPDATE users
        SET is_pro = %s,
            pro_since = CASE WHEN %s AND pro_since IS NULL THEN now()
                             WHEN NOT %s THEN NULL
                             ELSE pro_since END
        WHERE user_id = %s
        RETURNING user_id, is_pro, pro_since, created_at
        """,
        (is_pro, is_pro, is_pro, user_id),
    )
