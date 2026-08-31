-- security-definer functions are internal (trigger machinery); they must not be
-- callable through PostgREST RPC by anon/authenticated (advisor lints 0028/0029).
-- Triggers fire regardless of the caller's EXECUTE privilege, so this breaks nothing.
revoke execute on function public.handle_new_user() from public, anon, authenticated;
revoke execute on function public.handle_review_change() from public, anon, authenticated;
revoke execute on function public.refresh_shop_rating(bigint) from public, anon, authenticated;
