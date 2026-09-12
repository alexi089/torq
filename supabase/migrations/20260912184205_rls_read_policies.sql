-- Read contract for clients (spec 2026-09-12 §3). API connects as postgres
-- (bypassrls) and is unaffected. Writes stay deny-all: no INSERT/UPDATE/DELETE
-- policies exist on any public table.

create function public.current_shop_id()
returns bigint
language sql
stable
security invoker
set search_path = ''
as $$
  select id from public.shops where owner_id = (select auth.uid())
$$;

-- own row, or the driver of a request my shop was notified on
create policy profiles_read on public.profiles
for select to authenticated
using (
  id = (select auth.uid())
  or exists (
    select 1
    from public.requests r
    join public.request_notifications rn on rn.request_id = r.id
    where r.driver_id = public.profiles.id
      and rn.shop_id = (select public.current_shop_id())
  )
);

-- own rows, or the vehicle on a request my shop was notified on
create policy vehicles_read on public.vehicles
for select to authenticated
using (
  owner_id = (select auth.uid())
  or exists (
    select 1
    from public.requests r
    join public.request_notifications rn on rn.request_id = r.id
    where r.vehicle_id = public.vehicles.id
      and rn.shop_id = (select public.current_shop_id())
  )
);

-- directory: all shops visible (phone/address are meant to be shown)
create policy shops_read on public.shops
for select to authenticated
using (true);

-- own requests, or requests my shop was notified on
create policy requests_read on public.requests
for select to authenticated
using (
  driver_id = (select auth.uid())
  or exists (
    select 1 from public.request_notifications rn
    where rn.request_id = public.requests.id
      and rn.shop_id = (select public.current_shop_id())
  )
);

-- same visibility as the parent request
create policy request_photos_read on public.request_photos
for select to authenticated
using (
  exists (
    select 1 from public.requests r
    where r.id = public.request_photos.request_id
      and (
        r.driver_id = (select auth.uid())
        or exists (
          select 1 from public.request_notifications rn
          where rn.request_id = r.id
            and rn.shop_id = (select public.current_shop_id())
        )
      )
  )
);

-- my shop's quotes, or quotes on my own requests
create policy quotes_read on public.quotes
for select to authenticated
using (
  shop_id = (select public.current_shop_id())
  or exists (
    select 1 from public.requests r
    where r.id = public.quotes.request_id
      and r.driver_id = (select auth.uid())
  )
);

-- my shop's inbox only
create policy request_notifications_read on public.request_notifications
for select to authenticated
using (shop_id = (select public.current_shop_id()));

-- public
create policy reviews_read on public.reviews
for select to authenticated
using (true);
