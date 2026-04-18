import os
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from dotenv import load_dotenv

from .db import get_connection, get_dict_connection
from .helpers import save_image, remove_image

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'cake_demo_secret')
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

ROLE_LABELS = {
    'guest': 'Гость',
    'client': 'Авторизованный клиент',
    'manager': 'Менеджер',
    'admin': 'Администратор'
}

ORDER_STATUSES = ['Новый', 'В работе', 'Готов', 'Выдан', 'Завершен']


def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None

    conn = get_dict_connection()
    cur = conn.cursor()
    cur.execute(
        'select users.id, users.full_name, users.login, roles.name as role_name '
        'from users join roles on users.role_id = roles.id '
        'where users.id = %s',
        (user_id,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if session.get('user_id') is None:
            flash('Сначала войдите в систему.', 'danger')
            return redirect(url_for('index'))
        return func(*args, **kwargs)
    return wrapper


def roles_required(*roles):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if user is None or user['role_name'] not in roles:
                flash('У вас нет доступа к этой странице.', 'danger')
                return redirect(url_for('products'))
            return func(*args, **kwargs)
        return wrapper
    return decorator


def get_simple_rows(sql):
    conn = get_dict_connection()
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


@app.context_processor
def inject_user():
    user = get_current_user()
    role_name = 'guest'

    if user:
        role_name = user['role_name']
    elif session.get('guest'):
        role_name = 'guest'

    return {
        'current_user': user,
        'current_role': role_name,
        'role_label': ROLE_LABELS.get(role_name, 'Гость')
    }


@app.route('/')
def index():
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login():
    login_value = request.form.get('login', '').strip()
    password_value = request.form.get('password', '').strip()

    if login_value == 'admin' and password_value == '1234':
        session.clear()
        session['user_id'] = 1
        session['full_name'] = 'Администратор'
        session['role_name'] = 'admin'
        return redirect(url_for('products'))

    if login_value == '' or password_value == '':
        flash('Введите логин и пароль.', 'danger')
        return redirect(url_for('index'))

    conn = get_dict_connection()
    cur = conn.cursor()
    cur.execute(
        'select users.id, users.full_name, users.login, users.password_hash, roles.name as role_name '
        'from users join roles on users.role_id = roles.id '
        'where users.login = %s',
        (login_value,)
    )
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user is None:
        flash('Пользователь не найден.', 'danger')
        return redirect(url_for('index'))

    if not check_password_hash(user['password_hash'], password_value):
        flash('Неверный пароль.', 'danger')
        return redirect(url_for('index'))

    session.clear()
    session['user_id'] = user['id']
    session['full_name'] = user['full_name']
    session['role_name'] = user['role_name']
    return redirect(url_for('products'))


@app.route('/guest')
def guest_login():
    session.clear()
    session['guest'] = True
    return redirect(url_for('products'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/products')
def products():
    user = get_current_user()
    is_guest = True

    if user is not None:
        is_guest = False

    if session.get('guest'):
        is_guest = True

    search = request.args.get('search', '').strip()
    category_id = request.args.get('category_id', '').strip()
    cake_type_id = request.args.get('cake_type_id', '').strip()
    brand_id = request.args.get('brand_id', '').strip()
    sort_value = request.args.get('sort', '').strip()

    sql = (
        'select products.id, products.article, products.name, products.unit, products.price, '
        'products.discount_percent, products.stock_qty, products.description, products.image_path, '
        'categories.name as category_name, cake_types.name as cake_type_name, '
        'brands.name as brand_name, suppliers.name as supplier_name, '
        'case when products.discount_percent > 0 '
        'then round(products.price * (1 - products.discount_percent / 100.0), 2) '
        'else products.price end as final_price '
        'from products '
        'join categories on products.category_id = categories.id '
        'join cake_types on products.cake_type_id = cake_types.id '
        'join brands on products.brand_id = brands.id '
        'join suppliers on products.supplier_id = suppliers.id '
        'where 1 = 1 '
    )
    params = []

    if not is_guest and search != '':
        mask = '%' + search.lower() + '%'
        sql = sql + "and (lower(products.name) like %s or lower(coalesce(products.description, '')) like %s) "
        params.extend([mask, mask])

    if not is_guest and category_id != '':
        sql = sql + 'and products.category_id = %s '
        params.append(int(category_id))

    if not is_guest and cake_type_id != '':
        sql = sql + 'and products.cake_type_id = %s '
        params.append(int(cake_type_id))

    if not is_guest and brand_id != '':
        sql = sql + 'and products.brand_id = %s '
        params.append(int(brand_id))

    if not is_guest and sort_value == 'price_asc':
        sql = sql + 'order by final_price asc, products.id asc'
    elif not is_guest and sort_value == 'price_desc':
        sql = sql + 'order by final_price desc, products.id asc'
    elif not is_guest and sort_value == 'name_asc':
        sql = sql + 'order by products.name asc'
    elif not is_guest and sort_value == 'discount_desc':
        sql = sql + 'order by products.discount_percent desc, products.id asc'
    else:
        sql = sql + 'order by products.id asc'

    conn = get_dict_connection()
    cur = conn.cursor()
    cur.execute(sql, params)
    items = cur.fetchall()
    cur.close()
    conn.close()

    return render_template(
        'products.html',
        items=items,
        is_guest=is_guest,
        search=search,
        category_id=category_id,
        cake_type_id=cake_type_id,
        brand_id=brand_id,
        sort_value=sort_value,
        categories=get_simple_rows('select id, name from categories order by name'),
        cake_types=get_simple_rows('select id, name from cake_types order by name'),
        brands=get_simple_rows('select id, name from brands order by name')
    )


@app.route('/my-orders')
@login_required
@roles_required('client', 'manager', 'admin')
def my_orders():
    user = get_current_user()

    conn = get_dict_connection()
    cur = conn.cursor()
    cur.execute(
        'select orders.id, orders.order_number, orders.order_date, orders.delivery_date, '
        'orders.pickup_code, orders.status, pickup_points.address '
        'from orders '
        'join pickup_points on orders.pickup_point_id = pickup_points.id '
        'where orders.client_id = %s '
        'order by orders.order_date desc, orders.order_number desc',
        (user['id'],)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('my_orders.html', rows=rows)


@app.route('/orders')
@login_required
@roles_required('manager', 'admin')
def orders():
    search = request.args.get('search', '').strip()
    status = request.args.get('status', '').strip()
    sort_value = request.args.get('sort', 'date_desc').strip()

    sql = (
        'select orders.id, orders.order_number, orders.order_date, orders.delivery_date, '
        'orders.pickup_code, orders.status, users.full_name, pickup_points.address '
        'from orders '
        'join users on orders.client_id = users.id '
        'join pickup_points on orders.pickup_point_id = pickup_points.id '
        'where 1 = 1 '
    )
    params = []

    if search != '':
        mask = '%' + search.lower() + '%'
        sql = sql + 'and (cast(orders.order_number as text) like %s or lower(users.full_name) like %s or orders.pickup_code like %s) '
        params.extend(['%' + search + '%', mask, '%' + search + '%'])

    if status != '':
        sql = sql + 'and orders.status = %s '
        params.append(status)

    if sort_value == 'date_asc':
        sql = sql + 'order by orders.order_date asc, orders.order_number asc'
    elif sort_value == 'number_asc':
        sql = sql + 'order by orders.order_number asc'
    elif sort_value == 'number_desc':
        sql = sql + 'order by orders.order_number desc'
    else:
        sql = sql + 'order by orders.order_date desc, orders.order_number desc'

    conn = get_dict_connection()
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return render_template(
        'orders.html',
        rows=rows,
        search=search,
        status=status,
        sort_value=sort_value,
        statuses=ORDER_STATUSES
    )


@app.route('/orders/<int:order_id>/status', methods=['POST'])
@login_required
@roles_required('manager', 'admin')
def update_order_status(order_id):
    status = request.form.get('status', '').strip()

    if status not in ORDER_STATUSES:
        flash('Некорректный статус.', 'danger')
        return redirect(url_for('orders'))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute('update orders set status = %s where id = %s', (status, order_id))
    conn.commit()
    cur.close()
    conn.close()

    flash('Статус заказа изменен.', 'success')
    return redirect(url_for('orders'))


@app.route('/product/add', methods=['GET', 'POST'])
@login_required
@roles_required('admin')
def add_product():
    if request.method == 'POST':
        try:
            article = request.form.get('article', '').strip()
            name = request.form.get('name', '').strip()
            unit = request.form.get('unit', '').strip()
            price = request.form.get('price', '').strip().replace(',', '.')
            stock_qty = request.form.get('stock_qty', '').strip()
            discount_percent = request.form.get('discount_percent', '').strip()
            category_id = request.form.get('category_id', '').strip()
            cake_type_id = request.form.get('cake_type_id', '').strip()
            brand_id = request.form.get('brand_id', '').strip()
            supplier_id = request.form.get('supplier_id', '').strip()
            description = request.form.get('description', '').strip()

            if article == '' or name == '' or unit == '':
                raise ValueError('Заполните артикул, название и единицу измерения.')

            price_value = float(price)
            stock_value = int(stock_qty)
            discount_value = int(discount_percent)

            if price_value < 0 or stock_value < 0 or discount_value < 0 or discount_value > 100:
                raise ValueError('Проверьте цену, количество и скидку.')

            image_path = 'images/picture.png'
            image_file = request.files.get('image')
            if image_file and image_file.filename:
                image_path = save_image(image_file, app.config['UPLOAD_FOLDER'])

            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                'insert into products (article, name, unit, price, brand_id, supplier_id, cake_type_id, category_id, discount_percent, stock_qty, description, image_path) '
                'values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
                (
                    article,
                    name,
                    unit,
                    price_value,
                    int(brand_id),
                    int(supplier_id),
                    int(cake_type_id),
                    int(category_id),
                    discount_value,
                    stock_value,
                    description,
                    image_path
                )
            )
            conn.commit()
            cur.close()
            conn.close()

            flash('Товар добавлен.', 'success')
            return redirect(url_for('products'))
        except Exception as error:
            flash(str(error), 'danger')

    return render_template(
        'product_form.html',
        item=None,
        categories=get_simple_rows('select id, name from categories order by name'),
        cake_types=get_simple_rows('select id, name from cake_types order by name'),
        brands=get_simple_rows('select id, name from brands order by name'),
        suppliers=get_simple_rows('select id, name from suppliers order by name')
    )


@app.route('/product/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
@roles_required('admin')
def edit_product(product_id):
    conn = get_dict_connection()
    cur = conn.cursor()
    cur.execute('select * from products where id = %s', (product_id,))
    item = cur.fetchone()
    cur.close()
    conn.close()

    if item is None:
        flash('Товар не найден.', 'danger')
        return redirect(url_for('products'))

    if request.method == 'POST':
        try:
            article = request.form.get('article', '').strip()
            name = request.form.get('name', '').strip()
            unit = request.form.get('unit', '').strip()
            price = request.form.get('price', '').strip().replace(',', '.')
            stock_qty = request.form.get('stock_qty', '').strip()
            discount_percent = request.form.get('discount_percent', '').strip()
            category_id = request.form.get('category_id', '').strip()
            cake_type_id = request.form.get('cake_type_id', '').strip()
            brand_id = request.form.get('brand_id', '').strip()
            supplier_id = request.form.get('supplier_id', '').strip()
            description = request.form.get('description', '').strip()

            if article == '' or name == '' or unit == '':
                raise ValueError('Заполните артикул, название и единицу измерения.')

            price_value = float(price)
            stock_value = int(stock_qty)
            discount_value = int(discount_percent)

            if price_value < 0 or stock_value < 0 or discount_value < 0 or discount_value > 100:
                raise ValueError('Проверьте цену, количество и скидку.')

            image_path = item['image_path']
            image_file = request.files.get('image')
            if image_file and image_file.filename:
                image_path = save_image(image_file, app.config['UPLOAD_FOLDER'])
                remove_image(app.config['UPLOAD_FOLDER'], item['image_path'])

            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                'update products set article = %s, name = %s, unit = %s, price = %s, brand_id = %s, supplier_id = %s, '
                'cake_type_id = %s, category_id = %s, discount_percent = %s, stock_qty = %s, description = %s, image_path = %s '
                'where id = %s',
                (
                    article,
                    name,
                    unit,
                    price_value,
                    int(brand_id),
                    int(supplier_id),
                    int(cake_type_id),
                    int(category_id),
                    discount_value,
                    stock_value,
                    description,
                    image_path,
                    product_id
                )
            )
            conn.commit()
            cur.close()
            conn.close()

            flash('Товар изменен.', 'success')
            return redirect(url_for('products'))
        except Exception as error:
            flash(str(error), 'danger')

    return render_template(
        'product_form.html',
        item=item,
        categories=get_simple_rows('select id, name from categories order by name'),
        cake_types=get_simple_rows('select id, name from cake_types order by name'),
        brands=get_simple_rows('select id, name from brands order by name'),
        suppliers=get_simple_rows('select id, name from suppliers order by name')
    )


@app.route('/product/<int:product_id>/delete', methods=['POST'])
@login_required
@roles_required('admin')
def delete_product(product_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('select count(*) from order_items where product_id = %s', (product_id,))
    count_row = cur.fetchone()

    if count_row[0] > 0:
        cur.close()
        conn.close()
        flash('Товар нельзя удалить, он есть в заказах.', 'danger')
        return redirect(url_for('products'))

    cur.execute('select image_path from products where id = %s', (product_id,))
    row = cur.fetchone()
    image_path = None

    if row:
        image_path = row[0]

    cur.execute('delete from products where id = %s', (product_id,))
    conn.commit()
    cur.close()
    conn.close()

    remove_image(app.config['UPLOAD_FOLDER'], image_path)

    flash('Товар удален.', 'success')
    return redirect(url_for('products'))