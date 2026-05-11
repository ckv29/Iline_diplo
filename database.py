from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from sqlalchemy.orm import relationship

db = SQLAlchemy()



class personal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    job_title = db.Column(db.String, nullable=False)
    date_of_employment = db.Column(db.DateTime, nullable=True)
    salary = db.Column(db.Integer,nullable=True)
    manager_id = db.Column(db.Integer,db.ForeignKey('personal.id'),  nullable=True)

    manager = relationship('personal', remote_side=[id], backref='subordinates')
    