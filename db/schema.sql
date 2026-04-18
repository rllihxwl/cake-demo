drop table if exists order_items cascade;
drop table if exists orders cascade;
drop table if exists products cascade;
drop table if exists pickup_points cascade;
drop table if exists users cascade;
drop table if exists roles cascade;
drop table if exists brands cascade;
drop table if exists suppliers cascade;
drop table if exists cake_types cascade;
drop table if exists categories cascade;

create table roles (
    id serial primary key,
    name varchar(50) not null unique
);

create table users (
    id serial primary key,
    full_name varchar(255) not null,
    login varchar(255) not null unique,
    password_hash varchar(255) not null,
    role_id integer not null references roles(id)
);

create table brands (
    id serial primary key,
    name varchar(255) not null unique
);

create table suppliers (
    id serial primary key,
    name varchar(255) not null unique
);

create table cake_types (
    id serial primary key,
    name varchar(255) not null unique
);

create table categories (
    id serial primary key,
    name varchar(255) not null unique
);

create table pickup_points (
    id serial primary key,
    address varchar(255) not null unique
);

create table products (
    id serial primary key,
    article varchar(50) not null unique,
    name varchar(255) not null,
    unit varchar(50) not null,
    price numeric(10, 2) not null check (price >= 0),
    brand_id integer not null references brands(id),
    supplier_id integer not null references suppliers(id),
    cake_type_id integer not null references cake_types(id),
    category_id integer not null references categories(id),
    discount_percent integer not null default 0 check (discount_percent >= 0 and discount_percent <= 100),
    stock_qty integer not null default 0 check (stock_qty >= 0),
    description text,
    image_path varchar(255) not null default 'images/picture.png'
);

create table orders (
    id serial primary key,
    order_number integer not null unique,
    order_date date not null,
    delivery_date date not null,
    pickup_point_id integer not null references pickup_points(id),
    client_id integer not null references users(id),
    pickup_code varchar(20) not null,
    status varchar(100) not null
);

create table order_items (
    id serial primary key,
    order_id integer not null references orders(id) on delete cascade,
    product_id integer not null references products(id),
    quantity integer not null check (quantity > 0)
);