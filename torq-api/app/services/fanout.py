import asyncpg

MI_TO_M = 1609.344


async def fan_out(
    conn: asyncpg.Connection, request_id: int, lat: float, lng: float, search_radius_mi: int
) -> int:
    result = await conn.execute(
        """
        insert into public.request_notifications (request_id, shop_id)
        select $1, s.id
        from public.shops s
        where s.is_online
          and extensions.st_dwithin(
                s.location,
                extensions.st_setsrid(extensions.st_makepoint($3, $2), 4326)::extensions.geography,
                $4::float8 * $5::float8)
          and extensions.st_dwithin(
                s.location,
                extensions.st_setsrid(extensions.st_makepoint($3, $2), 4326)::extensions.geography,
                s.alert_radius_mi::float8 * $5::float8)
        """,
        request_id,
        lat,
        lng,
        float(search_radius_mi),
        MI_TO_M,
    )
    return int(result.split(" ")[-1])  # "INSERT 0 <n>"
