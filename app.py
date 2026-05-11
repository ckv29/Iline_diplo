from dotenv import load_dotenv
import os
from flask import Flask
from flask import render_template, request, redirect, url_for, flash
from sqlalchemy.exc import IntegrityError
from sqlalchemy import create_engine, text
from database import personal,db
from sqlalchemy.orm import joinedload


load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"postgresql+psycopg2://"
    f"{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/"
    f"{os.getenv('DB_NAME')}"
)
db.init_app(app)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Создаём движок
engine = create_engine(app.config["SQLALCHEMY_DATABASE_URI"], echo=False)  # echo=True — для отладки SQL

# Пример использования
def test_connection():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            print(result.fetchone())
        print("✅ Подключение через SQLAlchemy успешно!")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

@app.route("/")
def all_employees():
    #поставил ограничение на 10 000 записей,чтобы выводить не долго
    employees = personal.query.options(joinedload(personal.manager)).limit(10000).all()
    return render_template("all_employees.html", employees=employees)

@app.route("/sort_by/")
def sorted_employees():
    field = request.args.get("field")
    columns = ['name','job_title','date_of_employment','salary','manager_id']
    if field not in columns:
        field = 'name'


    order_col = getattr(personal,field)

    employees = personal.query.order_by(order_col).options(joinedload(personal.manager)).limit(10000).all()
    return render_template("all_employees.html", employees=employees)

@app.route("/find/<value>")
def find_employees(value):
    query = personal.query.options(joinedload(personal.manager))
    if value:
        # Частичное совпадение (LIKE), регистронезависимо
        query = query.filter(            
                personal.name.ilike(f"%{value}%"),
                )
    employees = query.order_by(personal.name).limit(50).all()
    return render_template("all_employees.html", employees=employees)


@app.route("/update_manager", methods=["POST"])
def update_manager():
    employee_id = request.form.get("employee_id")
    new_manager_id = request.form.get("new_manager_id", "").strip()

    if not employee_id:
        flash("Не указан ID сотрудника", "error")
        return redirect(url_for("all_employees"))

    try:
        employee_id = int(employee_id)
    except ValueError:
        flash("Некорректный ID сотрудника", "error")
        return redirect(url_for("all_employees"))

    employee = personal.query.get_or_404(employee_id)

    # Обработка нового руководителя
    if new_manager_id == "":
        employee.manager_id = None
    else:
        try:
            new_manager_id = int(new_manager_id)
            if (new_manager_id == employee_id) and (employee.job_title != "SEO"):
                flash("Только может быть руководителем самого себя!", "error")
                return redirect(url_for("all_employees"))
            manager = personal.query.get_or_404(new_manager_id)
            if not manager:
                flash(f"Руководитель с ID {new_manager_id} не найден.", "error")
                return redirect(url_for("all_employees"))
            employee.manager_id = new_manager_id
        except ValueError:
            flash("Неверно задан ID руководителя.", "error")
            return redirect(url_for("all_employees"))

    try:
        db.session.commit()
        flash(f"Руководитель сотрудника '{employee.name}' обновлён!", "success")
    except Exception as e:
        db.session.rollback()
        flash("Ошибка при сохранении: " + str(e), "error")

    return redirect(url_for("all_employees"))



if __name__ == "__main__":
    test_connection()  # опционально: проверка при старте
    app.run(debug=True)

