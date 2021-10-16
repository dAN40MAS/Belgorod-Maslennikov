from flask import abort, Blueprint, Flask, jsonify, redirect, render_template, request, make_response, session
from flask_login import current_user, LoginManager, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import PasswordField, StringField, SubmitField, BooleanField, DecimalField
from wtforms.fields.html5 import EmailField, SearchField
from wtforms.validators import DataRequired
from data import db_session
from data.user import User
from data.product import Product
import datetime
import os
import random
import re
from string import ascii_letters, digits

app = Flask(__name__)
app.config['SECRET_KEY'] = '421b1f57d3e228b7'
app.config['UPLOAD_FOLDER'] = '/static/uploads'
app.permanent_session_lifetime = datetime.timedelta(days=10)  # 10 дней будут храниться данные сессии

blueprint = Blueprint('products_api', __name__, template_folder='templates')

login_manager = LoginManager()
login_manager.init_app(app)


class RegisterForm(FlaskForm):
    email = EmailField('Адрес электронной почты', validators=[DataRequired()])
    username = StringField('Имя пользователя', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    password_again = PasswordField('Повторите пароль', validators=[DataRequired()])
    submit = SubmitField('Зарегистрироваться')


class LoginForm(FlaskForm):
    email = EmailField('Адрес электронной почты', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    remember_me = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')


class AddProductForm(FlaskForm):
    name = StringField('Название', validators=[DataRequired()])
    price = DecimalField('Цена', validators=[DataRequired()])
    photo = FileField('Фото', validators=[FileRequired(), FileAllowed(['jpg', 'png'])])
    submit = SubmitField('Добавить')


class EditProductForm(FlaskForm):
    name = StringField('Название', validators=[DataRequired()])
    price = DecimalField('Цена', validators=[DataRequired()])
    submit = SubmitField('Изменить')


class SearchForm(FlaskForm):
    search = SearchField('Поиск', validators=[DataRequired()])
    submit = SubmitField('Искать')


@login_manager.user_loader
def load_user(user_id):
    db_sess = db_session.create_session()
    return db_sess.query(User).get(user_id)


@app.errorhandler(403)
def forbidden(error):
    params = {
        'title': 'Запрещено',
        'error': 'Запрещено',
        'description': 'У Вас недостаточно прав для просмотра этой страницы'
    }
    return make_response(render_template('error.html', **params), 403)


@app.errorhandler(404)
def not_found(error):
    params = {
        'title': 'Страница не найдена',
        'error': 'Страница не найдена',
        'description': 'Возможно, вы допустили опечатку в адресе'
    }
    return make_response(render_template('error.html', **params), 404)


@app.route('/visits-counter/')
def visits():
    if 'visits' in session:
        session['visits'] = session.get('visits') + 1  # чтение и обновление данных сессии
    else:
        session['visits'] = 1  # настройка данных сессии
    return "Total visits: {}".format(session.get('visits'))


@app.route('/delete-visits/')
def delete_visits():
    session.pop('visits', None)  # удаление данных о посещениях
    return 'Visits deleted'


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if form.password.data != form.password_again.data:
            params = {
                'title': 'Регистрация',
                'form': form,
                'message': 'Пароли не совпадают'
            }
            return render_template('register.html', **params)
        db_sess = db_session.create_session()
        if db_sess.query(User).filter(User.email == form.email.data).first(): # <---------
            params = {
                'title': 'Регистрация',
                'form': form,
                'message': 'Пользователь с такой почтой уже существует'
            }
            return render_template('register.html', **params)
        user = User()
        user.username = form.username.data
        user.email = form.email.data
        user.set_password(form.password.data)

        db_sess.add(user)
        db_sess.commit()

        login_user(user, remember=True)
        return redirect('/')

    params = {
        'title': 'Регистрация',
        'form': form,
    }
    return render_template('register.html', **params)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        db_sess = db_session.create_session()
        user = db_sess.query(User).filter(User.email == form.email.data).first() # <---------
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            session['user'] = session.get('user')
            return redirect('/')
        params = {
            'title': 'Авторизация',
            'form': form,
            'message': 'Неправильный логин или пароль'
        }
        return render_template('login.html', **params)

    params = {
        'title': 'Авторизация',
        'form': form
    }
    return render_template('login.html', **params)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/')


@app.route('/profile')
@login_required
def profile():
    db_sess = db_session.create_session()
    products = db_sess.query(Product).filter(Product.user_id == current_user.id).all() # <---------

    notifications = current_user.notifications
    if notifications.startswith('-1'):
        notifications = []
    else:
        notifications = re.split(r'(?<!\\);', notifications)

        db_sess.query(User).get(current_user.id).notifications = '-1'
        db_sess.commit()

    params = {
        'title': 'Личный кабинет',
        'notifications': notifications,
        'products': products
    }
    return render_template('profile.html', **params)


@app.route('/user/<int:user_id>')
def get_user(user_id):
    db_sess = db_session.create_session()
    user = db_sess.query(User).get(user_id)
    if not user:
        abort(404)
    products = db_sess.query(Product).filter(Product.user_id == user.id).all() # <---------

    params = {
        'title': user.username,
        'user': user,
        'products': products
    }
    return render_template('user.html', **params)


@app.route('/product/<int:product_id>')
def get_product(product_id):
    db_sess = db_session.create_session()
    product = db_sess.query(Product).get(product_id)
    if not product:
        abort(404)

    params = {
        'title': product.name,
        'product': product
    }
    return render_template('product.html', **params)


@app.route('/shopcart')
@login_required
def get_shopcart():
    db_sess = db_session.create_session()

    shopcart = [int(_) for _ in current_user.shopcart.split() if int(_) > -1]
    products = [db_sess.query(Product).get(_) for _ in shopcart]

    params = {
        'title': 'Корзина',
        'products': products
    }
    return render_template('shopcart.html', **params)


@app.route('/add_to_shopcart/<int:product_id>')
@login_required
def add_to_shopcart(product_id):
    db_sess = db_session.create_session()
    product = db_sess.query(Product).get(product_id)
    user = db_sess.query(User).get(current_user.id)
    if not product:
        abort(404)
    elif current_user.id == product.user_id:
        abort(400)
    shopcart = current_user.shopcart.split()
    if str(product_id) in shopcart:
        abort(400)
    shopcart.append(product_id)
    shopcart = sorted(shopcart, key=lambda x: int(x))
    shopcart = ' '.join(str(_) for _ in shopcart)
    user.shopcart = shopcart
    db_sess.commit()

    return redirect(f'../product/{product_id}')


@app.route('/delete_from_shopcart1/<int:product_id>')
@login_required
def delete_from_shopcart1(product_id):
    db_sess = db_session.create_session()
    product = db_sess.query(Product).get(product_id)
    user = db_sess.query(User).get(current_user.id)
    if not product:
        abort(404)
    shopcart: list = current_user.shopcart.split()
    if str(product_id) not in shopcart:
        abort(400)
    del shopcart[shopcart.index(str(product_id))]
    shopcart: str = ' '.join(str(_) for _ in shopcart)
    user.shopcart = shopcart
    db_sess.commit()

    return redirect(f'../product/{product_id}')


@app.route('/delete_from_shopcart2/<int:product_id>')
@login_required
def delete_from_shopcart2(product_id):
    db_sess = db_session.create_session()
    product = db_sess.query(Product).get(product_id)
    user = db_sess.query(User).get(current_user.id)
    if not product:
        abort(404)
    shopcart: list = current_user.shopcart.split()
    if str(product_id) not in shopcart:
        abort(400)
    del shopcart[shopcart.index(str(product_id))]
    shopcart: str = ' '.join(str(_) for _ in shopcart)
    user.shopcart = shopcart
    db_sess.commit()

    return redirect('/shopcart')


@app.route('/buy')
@login_required
def buy():
    db_sess = db_session.create_session()

    shopcart = [int(_) for _ in current_user.shopcart.split() if int(_) > -1]
    products = [db_sess.query(Product).get(_) for _ in shopcart]
    user = db_sess.query(User).get(current_user.id)

    for product in products:
        seller = db_sess.query(User).filter(User.id == product.user_id).first() # <---------
        notifications = re.split(r'(?<!\\);', seller.notifications)
        if notifications[0] == '-1':
            notifications = []
        notifications.append(product.name.replace(';', '\\;'))
        notifications = ';'.join(notifications)
        seller.notifications = notifications
        db_sess.commit()

        try:
            os.remove(f'static/uploads/{product.photo}')
        except FileNotFoundError:
            pass
        db_sess.delete(product)

    user.shopcart = '-1'
    db_sess.commit()

    return redirect('/')


@app.route('/feedback')
@login_required
def feedback():

    db_sess = db_session.create_session()

    shopcart = [int(_) for _ in current_user.shopcart.split() if int(_) > -1]
    products = [db_sess.query(Product).get(_) for _ in shopcart]
    user = db_sess.query(User).get(current_user.id)

    return render_template('/feedback')


@app.route('/add_product', methods=['GET', 'POST'])
@login_required
def add_product():
    form = AddProductForm()
    if form.validate_on_submit():
        db_sess = db_session.create_session()
        product = Product()
        if form.name.data == '-1':
            product.name = '- 1'
        else:
            product.name = form.name.data
        product.price = form.price.data
        product.user_id = current_user.id

        file = form.photo.data
        filetype = file.filename.split('.')[-1]
        while True:
            filename = ''.join(random.choices(ascii_letters + digits, k=25)) + f'.{filetype}'
            if not os.path.exists(f'static/uploads/{filename}'):
                break
        product.photo = filename
        file.save(f'static/uploads/{filename}')

        db_sess.add(product)
        db_sess.commit()

        return redirect('/')

    params = {
        'title': 'Добавление товара',
        'form': form
    }
    return render_template('add_product_form.html', **params)


@app.route('/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    form = EditProductForm()
    if request.method == 'GET':
        db_sess = db_session.create_session()
        product = db_sess.query(Product).get(product_id)
        if not product:
            abort(404)
        elif product.user_id != current_user.id:
            abort(403)
        else:
            form.name.data = product.name
            form.price.data = product.price
    if form.validate_on_submit():
        db_sess = db_session.create_session()
        product = db_sess.query(Product).get(product_id)
        if not product:
            abort(404)
        elif product.user_id != current_user.id:
            abort(403)
        else:
            if form.name.data == '-1':
                product.name = '- 1'
            else:
                product.name = form.name.data
            product.price = form.price.data

            db_sess.commit()
            return redirect('/profile')
    params = {
        'title': 'Изменение товара',
        'form': form
    }
    return render_template('edit_product_form.html', **params)


@app.route('/delete/<int:product_id>', methods=['GET', 'POST'])
@login_required
def delete_product(product_id):
    db_sess = db_session.create_session()
    product = db_sess.query(Product).get(product_id)
    if not product:
        abort(404)
    if product.user_id != current_user.id:
        abort(403)
    else:
        try:
            os.remove(f'static/uploads/{product.photo}')
        except FileNotFoundError:
            pass
        db_sess.delete(product)
        db_sess.commit()
    return redirect('/profile')


@app.route('/search', methods=['GET', 'POST'])
def search():
    form = SearchForm()
    if form.validate_on_submit():
        text = form.search.data
        return redirect(f'search/{text}')

    params = {
        'title': 'Поиск',
        'form': form
    }
    return render_template('search_.html', **params)


@app.route('/search/<text>')
def search_results(text):
    text = text.lower()

    db_sess = db_session.create_session()

    users = db_sess.query(User).all()
    users_search_result = []
    for user in users:
        if text in user.username.lower():
            users_search_result.append(user)
    users_search_result = sorted(users_search_result, key=lambda x: x.username)

    products = db_sess.query(Product).all()
    products_search_result = []
    for product in products:
        if text in product.name.lower():
            products_search_result.append(product)

    params = {
        'title': 'Поиск',
        'users': users_search_result,
        'products': products_search_result
    }
    return render_template('search_results.html', **params)


@app.route('/')
def index():
    db_sess = db_session.create_session()
    products = db_sess.query(Product).all()
    if 'user' in session:
        params = {
            'title': 'Онлайн-магазин',
            'products': products
        }
        return render_template('index.html', **params)
    else:
        return render_template('error404.html')




@blueprint.route('/api/products')
def api_get_products():
    db_sess = db_session.create_session()
    products = db_sess.query(Product).all()
    return jsonify(
        {
            'products': [product.to_dict(only=('id', 'name', 'price', 'user_id'))
                         for product in products]
        }
    )


@blueprint.route('/api/product/<int:product_id>', methods=['GET'])
def api_get_one_product(product_id):
    db_sess = db_session.create_session()
    product = db_sess.query(Product).get(product_id)
    if not product:
        return jsonify({'error': 'Not found'})

    return jsonify(
        {
            'product': product.to_dict(only=('id', 'name', 'price', 'user_id'))
        }
    )


@blueprint.route('/api/user/<int:user_id>', methods=['GET'])
def api_get_products_of_user(user_id):
    db_sess = db_session.create_session()
    products = db_sess.query(Product).filter(Product.user_id == user_id) # <---------
    if not products:
        return jsonify({'error': 'Not found'})

    return jsonify(
        {
            'products': [product.to_dict(only=('id', 'name', 'price')) for product in products]
        }
    )


def main():
    db_session.global_init('db/db.sqlite')
    app.register_blueprint(blueprint)

    app.run()


if __name__ == '__main__':
    main()
