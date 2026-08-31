-- profiles: 1:1 with auth.users (cascade on account deletion per 2026-08-30 ruling;
-- downstream requests/reviews anonymize via set null instead)
create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  full_name text,
  phone text,
  created_at timestamptz not null default now()
);

-- deny-all until policies are designed (pairing session)
alter table public.profiles enable row level security;

-- auto-create profile on signup (confirmed 2026-08-30)
create function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id, full_name, phone)
  values (new.id, new.raw_user_meta_data ->> 'full_name', new.phone);
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();
