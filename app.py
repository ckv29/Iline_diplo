
import os
from typing import cast

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from database import db, personal

# Загрузка переменных окружения
load_dotenv()

# Константы
VALID_FIELDS = {"id", "name", "job_title", "date_of_employment", "salary", "manager_id"}
VALID_ORDERS = {"asc", "desc"}
DEFAULT_FIELD = "name"
DEFAULT_ORDER = "asc"
DEFAULT_PER_PAGE = 40
MIN_PER_PAGE = 1
MAX_PER_PAGE = 100

# Настройки приложения
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    print("⚠️  WARNING: SECRET_KEY not set in environment variables!")

DATABASE_URI = (
    f"postgresql+psycopg2://"
    f"{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/"
    f"{os.getenv('DB_NAME')}"
)

# Инициализация Flask
app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

engine = create_engine(DATABASE_URI, echo=False)


def test_connection() -> None:
    """Проверка подключения к БД (для отладки)."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            print(f"✅ PostgreSQL: {result.fetchone()[0]}")
    except Exception as e:
        print(f"❌ DB connection error: {e}")


# Эндроинты
@app.route("/")
def index() -> str:
    """Главная страница — перенаправляет на список с дефолтной сортировкой."""
    return sorted_employees()


@app.route("/sort_by/")
def sorted_employees() -> str:
    """Список сотрудников с сортировкой, фильтрами и пагинацией."""
    # Параметры сортировки и пагинации
    field = request.args.get("field", DEFAULT_FIELD)
    order = request.args.get("order", DEFAULT_ORDER).lower().strip()
    page = max(1, request.args.get("page", 1, type=int))
    per_page = max(
        MIN_PER_PAGE,
        min(request.args.get("per_page", DEFAULT_PER_PAGE, type=int), MAX_PER_PAGE),
    )

    # Валидация
    if field not in VALID_FIELDS or not hasattr(personal, field):
        field = DEFAULT_FIELD
    if order not in VALID_ORDERS:
        order = DEFAULT_ORDER

    # Параметры фильтров
    name = request.args.get("name", "").strip()
    job_title = request.args.get("job_title", "").strip()
    manager_name = request.args.get("manager_name", "").strip()
    salary_from = request.args.get("salary_from", type=float)
    salary_to = request.args.get("salary_to", type=float)
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    # Авто-свап, если пользователь перепутал «от» и «до»
    if salary_from is not None and salary_to is not None and salary_from > salary_to:
        salary_from, salary_to = salary_to, salary_from

    #  Сборка запроса
    query = personal.query.options(joinedload(personal.manager))

    # Сортировка + стабильный вторичный ключ (id) для корректной пагинации
    sort_col = cast(any, getattr(personal, field))
    query = query.order_by(
        sort_col.desc() if order == "desc" else sort_col,
        personal.id,
    )

    # Фильтры
    if name:
        query = query.filter(personal.name.ilike(f"%{name}%"))
    if job_title:
        query = query.filter(personal.job_title.ilike(f"%{job_title}%"))
    if manager_name:
        query = query.filter(personal.manager.has(personal.name.ilike(f"%{manager_name}%")))
    if salary_from is not None:
        query = query.filter(personal.salary >= salary_from)
    if salary_to is not None:
        query = query.filter(personal.salary <= salary_to)
    if date_from:
        query = query.filter(personal.date_of_employment >= date_from)
    if date_to:
        query = query.filter(personal.date_of_employment <= date_to)

    #  Пагинация
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    #  Контекст для шаблона
    filters = {
        k: v
        for k, v in {
            "name": name,
            "job_title": job_title,
            "manager_name": manager_name,
            "salary_from": salary_from,
            "salary_to": salary_to,
            "date_from": date_from,
            "date_to": date_to,
        }.items()
        if v is not None and v != ""
    }

    return render_template(
        "all_employees.html",
        employees=pagination.items,
        pagination=pagination,
        filters=filters,
        field=field,
        order=order,
        per_page=per_page,
    )


@app.route("/find/<value>")
def find_employees(value: str) -> str:
    """Поиск сотрудников по имени (частичное совпадение)."""
    query = personal.query.options(joinedload(personal.manager))
    if value:
        query = query.filter(personal.name.ilike(f"%{value}%"))
    employees = query.order_by(personal.name).limit(50).all()
    return render_template("all_employees.html", employees=employees)


@app.route("/update_manager", methods=["POST"])
def update_manager() -> str:
    """Обновление руководителя у сотрудника."""
    employee_id = request.form.get("employee_id")
    new_manager_id = request.form.get("new_manager_id", "").strip()

    if not employee_id:
        flash("Не указан ID сотрудника", "error")
        return redirect(url_for("index"))

    try:
        employee_id = int(employee_id)
    except ValueError:
        flash("Некорректный ID сотрудника", "error")
        return redirect(url_for("index"))

    employee = personal.query.get_or_404(employee_id)

    # Обработка нового руководителя
    if new_manager_id == "":
        employee.manager_id = None
    else:
        try:
            new_manager_id = int(new_manager_id)
        except ValueError:
            flash("Неверно задан ID руководителя", "error")
            return redirect(url_for("index"))

        if new_manager_id == employee_id and employee.job_title != "SEO":
            flash("Сотрудник не может быть своим руководителем (кроме SEO)", "error")
            return redirect(url_for("index"))

        # get_or_404 уже гарантирует наличие или 404, проверка if not manager избыточна
        manager = personal.query.get_or_404(new_manager_id)
        employee.manager_id = new_manager_id

    try:
        db.session.commit()
        flash(f"Руководитель сотрудника '{employee.name}' обновлён!", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Ошибка: нарушение целостности данных", "error")
    except Exception as e:
        db.session.rollback()
        flash(f"Ошибка при сохранении: {e}", "error")

    return redirect(url_for("index"))


# Старт
if __name__ == "__main__":
    test_connection()
    app.run(debug=True)