-- Torq enums (per torq-erd-v3; issue list confirmed from TORQ v3 Pro mock ISSUES array)
create type public.request_mode as enum ('roadside', 'planned');

create type public.request_issue as enum (
  'wont_start',
  'flat_tire',
  'battery',
  'brakes',
  'overheating',
  'other'
);

create type public.request_status as enum (
  'open',
  'accepted',
  'completed',
  'cancelled',
  'expired'
);

create type public.quote_status as enum ('pending', 'accepted', 'rejected');

create type public.photo_slot as enum ('engine_bay', 'dashboard', 'wide');
