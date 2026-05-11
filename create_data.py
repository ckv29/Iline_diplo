import random
from mimesis.enums import Gender
from mimesis.locales import Locale
from mimesis import Datetime, Numeric, Person
from database import personal, db
from app import app  # импортируем app для контекста



dt = Datetime()
num = Numeric()
person = Person(Locale.RU)

position_level = {
    "CEO": 1,
    "Manager": 2,
    "Team Lead": 3,
    "Senior Developer": 4,
    "Developer": 5
}

def createPersonalData(count, job, salaryS, salaryE, managerS, managerE):
    data = []
    for _ in range(count):
        user = {
            'name': person.full_name(gender=Gender.MALE),
            'job_title': job,
            'date_of_employment': dt.date(start=2018, end=2025),
            'salary': round(num.integer_number(salaryS, salaryE), -2),
            'manager_id': random.randint(managerS, managerE)
        }
        data.append(user)
    return data

def main():
    # Создаём данные
    res = createPersonalData(1, "CEO", 1200000, 1600000, 1, 1)
    res.extend(createPersonalData(200, "Manager", 450000, 750000, 1, 1))
    res.extend(createPersonalData(2000, "Team Lead", 350000, 600000, 2, 201))
    res.extend(createPersonalData(8000, "Senior Developer", 250000, 420000, 202, 2201))
    res.extend(createPersonalData(40000, "Developer", 80000, 280000, 2002, 10201))

    # Используем Flask-контекст
    with app.app_context():
        for record in res:
            emp = personal(
                name=record['name'],
                job_title=record['job_title'],
                date_of_employment=record['date_of_employment'],
                salary=record['salary'],
                manager_id=record['manager_id']
            )
            db.session.add(emp)

        try:
            db.session.commit()
            print(f"✅ Успешно добавлено {len(res)} записей.")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Ошибка при вставке: {e}")

if __name__ == "__main__":
    main()