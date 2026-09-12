-- Private bucket for request photos. Object name convention: <auth.uid()>/<anything>.
-- No UPDATE/DELETE policies (orphan cleanup is a follow-on spec).

insert into storage.buckets (id, name, public)
values ('request-photos', 'request-photos', false);

-- supports the shop-side SELECT policy lookup by object name
create index request_photos_storage_path_idx
  on public.request_photos (storage_path);

create policy request_photos_upload on storage.objects
for insert to authenticated
with check (
  bucket_id = 'request-photos'
  and (storage.foldername(name))[1] = (select auth.uid())::text
);

create policy request_photos_read on storage.objects
for select to authenticated
using (
  bucket_id = 'request-photos'
  and (
    (storage.foldername(name))[1] = (select auth.uid())::text
    or exists (
      select 1
      from public.request_photos rp
      join public.request_notifications rn on rn.request_id = rp.request_id
      where rp.storage_path = storage.objects.name
        and rn.shop_id = (select public.current_shop_id())
    )
  )
);
