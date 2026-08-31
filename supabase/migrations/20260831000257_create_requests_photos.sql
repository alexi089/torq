-- requests: driver_id/vehicle_id nullable so rows survive driver account
-- deletion anonymized (2026-08-30 ruling); RLS/RPC enforce driver_id at insert.
-- expires_at nullable: create_request RPC sets a TTL for roadside, planned stays null.
-- accepted_quote_id FK added in the quotes migration (circular dependency).
create table public.requests (
  id bigint generated always as identity primary key,
  driver_id uuid references public.profiles (id) on delete set null,
  vehicle_id bigint references public.vehicles (id) on delete set null,
  mode public.request_mode not null,
  issue public.request_issue not null,
  notes text,
  location_hint text,
  location extensions.geography(point, 4326) not null,
  search_radius_mi int not null check (search_radius_mi between 2 and 25),
  status public.request_status not null default 'open',
  created_at timestamptz not null default now(),
  expires_at timestamptz
);

create index requests_driver_id_idx on public.requests (driver_id);
create index requests_vehicle_id_idx on public.requests (vehicle_id);

alter table public.requests enable row level security;

-- request_photos: hard-cascades with the request (per ERD)
create table public.request_photos (
  id bigint generated always as identity primary key,
  request_id bigint not null references public.requests (id) on delete cascade,
  storage_path text not null,
  slot public.photo_slot not null
);

create index request_photos_request_id_idx on public.request_photos (request_id);

alter table public.request_photos enable row level security;
