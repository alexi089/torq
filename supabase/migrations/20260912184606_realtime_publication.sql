-- Clients subscribe to quote arrivals and shop-inbox items; Realtime applies
-- the SELECT policies from the rls_read_policies migration.
alter publication supabase_realtime add table public.quotes, public.request_notifications;
