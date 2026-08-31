-- quotes: one per shop per request
create table public.quotes (
  id bigint generated always as identity primary key,
  request_id bigint not null references public.requests (id) on delete cascade,
  shop_id bigint not null references public.shops (id) on delete cascade,
  price_min_cents int not null check (price_min_cents >= 0),
  price_max_cents int not null check (price_max_cents >= price_min_cents),
  eta_minutes int not null check (eta_minutes > 0),
  message text not null,
  status public.quote_status not null default 'pending',
  created_at timestamptz not null default now(),
  unique (request_id, shop_id)
);

create index quotes_shop_id_idx on public.quotes (shop_id);

alter table public.quotes enable row level security;

-- circular FK deferred from the requests migration; set null so deleting a
-- quote (e.g. shop cascade) never blocks or deletes the request
alter table public.requests
  add column accepted_quote_id bigint references public.quotes (id) on delete set null;

create index requests_accepted_quote_id_idx on public.requests (accepted_quote_id);

-- request_notifications: fan-out snapshot written at request creation = shop inbox
create table public.request_notifications (
  request_id bigint not null references public.requests (id) on delete cascade,
  shop_id bigint not null references public.shops (id) on delete cascade,
  seen_at timestamptz,
  created_at timestamptz not null default now(),
  primary key (request_id, shop_id)
);

-- shop inbox: newest first for one shop
create index request_notifications_shop_inbox_idx
  on public.request_notifications (shop_id, created_at desc);

alter table public.request_notifications enable row level security;
