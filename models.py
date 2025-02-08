from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Variant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gene = db.Column(db.String(50), nullable=False)
    hgvs_cdna = db.Column(db.String(100), nullable=False, unique=True)
    classification = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return f"<Variant {self.hgvs_cdna}>"
