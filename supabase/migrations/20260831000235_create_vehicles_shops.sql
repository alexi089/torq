-- vehicles: driver-owned, soft-deleted via archived_at, hard-cascades with the profile
create table public.vehicles (
  id bigint generated always as identity primary key,
  owner_id uuid not null references public.profiles (id) on delete cascade,
  year int not null,
  make text not null,
  model text not null,
  engine text,
  mileage int,
  archived_at timestamptz,
  created_at timestamptz not null default now()
);

create index vehicles_owner_id_idx on public.vehicles (owner_id);

alter table public.vehicles enable row level security;

-- shops: one per owner profile; rating_avg/rating_count maintained by the
-- reviews trigger (migration 7) — null avg until the first review, never invented
create table public.shops (
  id bigint generated always as identity primary key,
  owner_id uuid not null unique references public.profiles (id) on delete cascade,
  name text not null,
  phone text not null,
  address text not null,
  location extensions.geography(point, 4326) not null,
  alert_radius_mi int not null check (alert_radius_mi between 2 and 30),
  is_online boolean not null default false,
  rating_avg numeric(3, 2),
  rating_count int not null default 0,
  created_at timestamptz not null default now()
);

create index shops_location_idx on public.shops using gist (location);

alter table public.shops enable row level security;
