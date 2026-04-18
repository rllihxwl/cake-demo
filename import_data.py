
import os
import shutil
import pandas as pd
from werkzeug.security import generate_password_hash
from app.db import get_connection

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMPORT_DIR = os.path.join(BASE_DIR, 'import')
STATIC_DIR = os.path.join(BASE_DIR, 'app', 'static')
IMAGES_DIR = os.path.join(STATIC_DIR, 'images')
UPLOADS_DIR = os.path.join(STATIC_DIR, 'uploads')

ROLE_MAP = {
    'Администратор': 'admin',
    'Менеджер': 'manager',
    'Авторизированный клиент': 'client',
    'Авторизованный клиент': 'client',
    'Клиент': 'client',
    'client': 'client',
    'manager': 'manager',
    'admin': 'admin'
}

def get_file_path(key_word):
    files = os.listdir(IMPORT_DIR)
    for file_name in files:
        lower_name = file_name.lower()
        if key_word in lower_name and lower_name.endswith('.xlsx'):
            return os.path.join(IMPORT_DIR, file_name)
    return None

def copy_images():
    if not os.path.exists(IMAGES_DIR):
        os.makedirs(IMAGES_DIR)

    if not os.path.exists(UPLOADS_DIR):
        os.makedirs(UPLOADS_DIR)

    files = os.listdir(IMPORT_DIR)

    for file_name in files:
        lower_name = file_name.lower()
        source_path = os.path.join(IMPORT_DIR, file_name)

        if not os.path.isfile(source_path):
            continue

        if lower_name.endswith('.jpg') or lower_name.endswith('.jpeg') or lower_name.endswith('.png') or lower_name.endswith('.ico'):
            target_path = os.path.join(IMAGES_DIR, file_name)
            shutil.copy2(source_path, target_path)

def run_schema(conn):
    path = os.path.join(BASE_DIR, 'db', 'schema.sql')
    file = open(path, 'r', encoding='utf-8')
    sql = file.read()
    file.close()

    cur = conn.cursor()
    parts = sql.split(';')
    for part in parts:
        text = part.strip()
        if text != '':
            cur.execute(text)
    conn.commit()
    cur.close()

def insert_roles(conn):
    cur = conn.cursor()
    cur.execute("insert into roles (name) values ('admin')")
    cur.execute("insert into roles (name) values ('manager')")
    cur.execute("insert into roles (name) values ('client')")
    conn.commit()
    cur.close()

def get_role_id(conn, role_name):
    cur = conn.cursor()
    cur.execute('select id from roles where name = %s', (role_name,))
    row = cur.fetchone()
    cur.close()
    return row[0]

def get_or_create_id(conn, table_name, value):
    cur = conn.cursor()
    cur.execute('select id from ' + table_name + ' where name = %s', (value,))
    row = cur.fetchone()
    if row:
        cur.close()
        return row[0]

    cur.execute('insert into ' + table_name + ' (name) values (%s) returning id', (value,))
    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    return new_id

def get_or_create_pickup_point_id(conn, address):
    cur = conn.cursor()
    cur.execute('select id from pickup_points where address = %s', (address,))
    row = cur.fetchone()
    if row:
        cur.close()
        return row[0]

    cur.execute('insert into pickup_points (address) values (%s) returning id', (address,))
    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    return new_id

def find_column(columns, variants):
    for name in columns:
        lower_name = str(name).strip().lower()
        for variant in variants:
            if variant in lower_name:
                return name
    return None

def import_users(conn):
    file_path = get_file_path('user')
    if file_path is None:
        return

    df = pd.read_excel(file_path)
    columns = list(df.columns)

    full_name_col = find_column(columns, ['фио'])
    login_col = find_column(columns, ['логин'])
    password_col = find_column(columns, ['пароль'])
    role_col = find_column(columns, ['роль'])

    cur = conn.cursor()

    for _, row in df.iterrows():
        full_name = str(row[full_name_col]).strip()
        login = str(row[login_col]).strip()
        password = str(row[password_col]).strip()
        role_value = str(row[role_col]).strip()

        if full_name == '' or login == '' or password == '':
            continue

        role_name = ROLE_MAP.get(role_value, 'client')
        role_id = get_role_id(conn, role_name)
        password_hash = generate_password_hash(password)

        cur.execute('select id from users where login = %s', (login,))
        exists = cur.fetchone()
        if exists:
            continue

        cur.execute(
            'insert into users (full_name, login, password_hash, role_id) values (%s, %s, %s, %s)',
            (full_name, login, password_hash, role_id)
        )

    conn.commit()
    cur.close()

def import_products(conn):
    file_path = get_file_path('tovar')
    if file_path is None:
        return

    df = pd.read_excel(file_path)
    columns = list(df.columns)

    article_col = find_column(columns, ['артикул'])
    name_col = find_column(columns, ['наименование'])
    unit_col = find_column(columns, ['единица'])
    price_col = find_column(columns, ['цена'])
    brand_col = find_column(columns, ['бренд'])
    cake_type_col = find_column(columns, ['тип торта'])
    category_col = find_column(columns, ['категория'])
    discount_col = find_column(columns, ['скид'])
    stock_col = find_column(columns, ['складе'])
    description_col = find_column(columns, ['описание'])
    image_col = find_column(columns, ['фото'])

    cur = conn.cursor()

    for _, row in df.iterrows():
        article = str(row[article_col]).strip()
        name = str(row[name_col]).strip()
        unit = str(row[unit_col]).strip()
        description = str(row[description_col]).strip()

        if article == '' or name == '':
            continue

        try:
            price = float(str(row[price_col]).replace(',', '.'))
        except:
            price = 0

        try:
            discount_percent = int(float(str(row[discount_col]).replace(',', '.')))
        except:
            discount_percent = 0

        try:
            stock_qty = int(float(str(row[stock_col]).replace(',', '.')))
        except:
            stock_qty = 0

        brand_name = str(row[brand_col]).strip()
        supplier_name = brand_name
        cake_type_name = str(row[cake_type_col]).strip()
        category_name = str(row[category_col]).strip()

        brand_id = get_or_create_id(conn, 'brands', brand_name)
        supplier_id = get_or_create_id(conn, 'suppliers', supplier_name)
        cake_type_id = get_or_create_id(conn, 'cake_types', cake_type_name)
        category_id = get_or_create_id(conn, 'categories', category_name)

        image_path = 'images/picture.png'
        image_name = str(row[image_col]).strip()
        if image_name != '' and image_name.lower() != 'nan':
            image_path = 'images/' + image_name

        cur.execute('select id from products where article = %s', (article,))
        exists = cur.fetchone()
        if exists:
            continue

        cur.execute(
            'insert into products (article, name, unit, price, brand_id, supplier_id, cake_type_id, category_id, discount_percent, stock_qty, description, image_path) '
            'values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
            (
                article,
                name,
                unit,
                price,
                brand_id,
                supplier_id,
                cake_type_id,
                category_id,
                discount_percent,
                stock_qty,
                description,
                image_path
            )
        )

    conn.commit()
    cur.close()

def get_user_id_by_full_name(conn, full_name):
    cur = conn.cursor()
    cur.execute('select id from users where full_name = %s', (full_name,))
    row = cur.fetchone()
    cur.close()
    if row:
        return row[0]
    return None

def get_product_id_by_article(conn, article):
    cur = conn.cursor()
    cur.execute('select id from products where article = %s', (article,))
    row = cur.fetchone()
    cur.close()
    if row:
        return row[0]
    return None

def load_point_map():
    data = {}
    file_path = get_file_path('points')
    if file_path is None:
        return data

    df = pd.read_excel(file_path)
    first = df.columns[0]
    values = [str(first).strip()]
    for _, row in df.iterrows():
        values.append(str(row.iloc[0]).strip())

    index = 1
    for value in values:
        if value != '' and value.lower() != 'nan':
            data[index] = value
            index = index + 1
    return data

def import_orders(conn):
    file_path = get_file_path('zakaz')
    if file_path is None:
        return

    point_map = load_point_map()
    df = pd.read_excel(file_path)
    columns = list(df.columns)

    order_number_col = find_column(columns, ['номер заказа'])
    article_col = find_column(columns, ['артикул заказа'])
    order_date_col = find_column(columns, ['дата заказа'])
    delivery_date_col = find_column(columns, ['дата доставки'])
    pickup_address_col = find_column(columns, ['адрес пункта'])
    client_name_col = find_column(columns, ['фио'])
    pickup_code_col = find_column(columns, ['код'])
    status_col = find_column(columns, ['статус'])

    cur = conn.cursor()

    for _, row in df.iterrows():
        try:
            order_number = int(row[order_number_col])
        except:
            continue

        client_name = str(row[client_name_col]).strip()
        client_id = get_user_id_by_full_name(conn, client_name)
        if client_id is None:
            continue

        point_value = row[pickup_address_col]
        address = str(point_value).strip()
        if str(point_value).isdigit():
            address = point_map.get(int(point_value), address)
        else:
            try:
                address = point_map.get(int(point_value), address)
            except:
                pass

        pickup_point_id = get_or_create_pickup_point_id(conn, address)
        pickup_code = str(row[pickup_code_col]).strip()
        status = str(row[status_col]).strip()
        order_date = row[order_date_col]
        delivery_date = row[delivery_date_col]

        cur.execute('select id from orders where order_number = %s', (order_number,))
        exists_order = cur.fetchone()

        if exists_order:
            order_id = exists_order[0]
        else:
            cur.execute(
                'insert into orders (order_number, order_date, delivery_date, pickup_point_id, client_id, pickup_code, status) '
                'values (%s, %s, %s, %s, %s, %s, %s) returning id',
                (
                    order_number,
                    order_date,
                    delivery_date,
                    pickup_point_id,
                    client_id,
                    pickup_code,
                    status
                )
            )
            order_id = cur.fetchone()[0]

        items = str(row[article_col]).split(',')
        i = 0
        while i + 1 < len(items):
            article = items[i].strip()
            qty_text = items[i + 1].strip()
            product_id = get_product_id_by_article(conn, article)
            if product_id is not None:
                try:
                    quantity = int(qty_text)
                except:
                    quantity = 1
                cur.execute(
                    'insert into order_items (order_id, product_id, quantity) values (%s, %s, %s)',
                    (order_id, product_id, quantity)
                )
            i = i + 2

    conn.commit()
    cur.close()

def main():
    copy_images()
    conn = get_connection()
    try:
        run_schema(conn)
        insert_roles(conn)
        import_users(conn)
        import_products(conn)
        import_orders(conn)
        print('Импорт завершен')
    finally:
        conn.close()

if __name__ == '__main__':
    main()
