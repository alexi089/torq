create extension if not exists pg_cron;

-- only open requests are ever scanned for expiry (spec addition, approved)
create index requests_open_expiry_idx
  on public.requests (expires_at)
  where status = 'open';

select cron.schedule(
  'expire-open-requests',
  '* * * * *',
  $$
    update public.requests
    set status = 'expired'
    where status = 'open'
      and expires_at is not null
      and expires_at < now()
  $$
);
