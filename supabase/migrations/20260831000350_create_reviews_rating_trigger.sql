-- reviews: one per request; survives driver account deletion anonymized
-- (driver_id set null), dies with its shop or request
create table public.reviews (
  id bigint generated always as identity primary key,
  request_id bigint not null unique references public.requests (id) on delete cascade,
  shop_id bigint not null references public.shops (id) on delete cascade,
  driver_id uuid references public.profiles (id) on delete set null,
  stars int not null check (stars between 1 and 5),
  tags text[] not null default '{}',
  comment text,
  created_at timestamptz not null default now()
);

create index reviews_shop_id_idx on public.reviews (shop_id);
create index reviews_driver_id_idx on public.reviews (driver_id);

alter table public.reviews enable row level security;

-- full recompute for one shop: null avg / 0 count when no reviews remain
create function public.refresh_shop_rating(target_shop bigint)
returns void
language sql
security definer
set search_path = ''
as $$
  update public.shops s
  set rating_avg = r.avg_stars,
      rating_count = r.cnt
  from (
    select avg(stars)::numeric(3, 2) as avg_stars, count(*) as cnt
    from public.reviews
    where shop_id = target_shop
  ) r
  where s.id = target_shop;
$$;

create function public.handle_review_change()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if tg_op in ('INSERT', 'UPDATE') then
    perform public.refresh_shop_rating(new.shop_id);
  end if;
  if tg_op = 'DELETE' or (tg_op = 'UPDATE' and old.shop_id is distinct from new.shop_id) then
    perform public.refresh_shop_rating(old.shop_id);
  end if;
  return null;
end;
$$;

create trigger on_review_change
  after insert or update or delete on public.reviews
  for each row execute function public.handle_review_change();
