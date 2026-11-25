-- Explorador · base de datos compartida (pegar entera en Supabase → SQL Editor → Run)

-- Valoraciones: una por persona (móvil) y sitio
create table if not exists public.ratings (
  id bigint generated always as identity primary key,
  poi_id text not null,
  cat text,
  device_id text not null,
  user_name text,
  stars int not null check (stars between 1 and 5),
  tags text[] default '{}',
  comment text check (char_length(comment) <= 140),
  photo_url text,
  created_at timestamptz default now(),
  unique (poi_id, device_id)
);
alter table public.ratings enable row level security;
create policy "todos pueden leer" on public.ratings for select using (true);
create policy "todos pueden valorar" on public.ratings for insert with check (true);
create policy "cambiar su valoración" on public.ratings for update using (true) with check (true);

-- Media de estrellas por sitio
create or replace view public.poi_stats with (security_invoker = on) as
  select poi_id, count(*)::int as n, round(avg(stars)::numeric, 2)::float8 as avg
  from public.ratings group by poi_id;

-- Sitios que añade la gente
create table if not exists public.places (
  id text primary key,
  cat text not null,
  lat float8 not null,
  lng float8 not null,
  name text,
  device_id text,
  user_name text,
  created_at timestamptz default now()
);
alter table public.places enable row level security;
create policy "todos pueden leer" on public.places for select using (true);
create policy "todos pueden añadir" on public.places for insert with check (true);

-- Avisos de sitios cerrados
create table if not exists public.reports (
  id bigint generated always as identity primary key,
  poi_id text not null,
  device_id text,
  created_at timestamptz default now()
);
alter table public.reports enable row level security;
create policy "todos pueden avisar" on public.reports for insert with check (true);

-- Permisos para la app
grant select, insert, update on public.ratings to anon;
grant select on public.poi_stats to anon;
grant select, insert on public.places to anon;
grant insert on public.reports to anon;

-- Fotos (carpeta pública "fotos")
insert into storage.buckets (id, name, public) values ('fotos', 'fotos', true) on conflict (id) do nothing;
create policy "subir fotos" on storage.objects for insert to anon with check (bucket_id = 'fotos');
create policy "ver fotos" on storage.objects for select using (bucket_id = 'fotos');

-- ===== Añadido para Patea: confirmaciones y planes =====

-- «¿Sigue aquí?»
create table if not exists public.confirms (
  id bigint generated always as identity primary key,
  poi_id text not null,
  device_id text,
  created_at timestamptz default now()
);
alter table public.confirms enable row level security;
create policy "todos pueden confirmar" on public.confirms for insert with check (true);
grant insert on public.confirms to anon;

-- Planes que monta la gente (fiestas, quedadas…)
create table if not exists public.plans (
  id text primary key,
  kind text not null,
  title text not null check (char_length(title) between 3 and 60),
  descr text check (char_length(descr) <= 280),
  place_name text check (char_length(place_name) <= 60),
  lat float8 not null,
  lng float8 not null,
  starts_at timestamptz not null,
  ends_at timestamptz not null,
  max_people int check (max_people is null or max_people between 2 and 500),
  adult_only boolean default false,
  device_id text not null,
  user_name text,
  cancelled boolean default false,
  created_at timestamptz default now(),
  check (ends_at > starts_at and ends_at <= starts_at + interval '24 hours')
);
alter table public.plans enable row level security;
create policy "todos pueden ver planes" on public.plans for select using (true);
create policy "todos pueden montar planes" on public.plans for insert with check (true);
create policy "cancelar planes" on public.plans for update using (true) with check (true);

-- Quién se apunta
create table if not exists public.plan_joins (
  plan_id text not null references public.plans(id) on delete cascade,
  device_id text not null,
  user_name text,
  created_at timestamptz default now(),
  primary key (plan_id, device_id)
);
alter table public.plan_joins enable row level security;
create policy "ver apuntados" on public.plan_joins for select using (true);
create policy "apuntarse" on public.plan_joins for insert with check (true);
create policy "desapuntarse" on public.plan_joins for delete using (true);

-- Denuncias de planes (con 3 denuncias el plan deja de salir)
create table if not exists public.plan_reports (
  id bigint generated always as identity primary key,
  plan_id text not null references public.plans(id) on delete cascade,
  device_id text,
  created_at timestamptz default now()
);
alter table public.plan_reports enable row level security;
create policy "denunciar" on public.plan_reports for insert with check (true);

-- Lo que ve la app: planes vivos con su número de apuntados
create or replace view public.plans_public as
  select p.id, p.kind, p.title, p.descr, p.place_name, p.lat, p.lng, p.starts_at, p.ends_at,
         p.max_people, p.adult_only, p.user_name, p.cancelled,
         (select count(*) from public.plan_joins j where j.plan_id = p.id)::int as n
  from public.plans p
  where not p.cancelled
    and (select count(*) from public.plan_reports r where r.plan_id = p.id) < 3;

grant select, insert, update on public.plans to anon;
grant select, insert, delete on public.plan_joins to anon;
grant insert on public.plan_reports to anon;
grant select on public.plans_public to anon;
