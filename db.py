import sqlite3

### CLASES ###

class DBManager:
    def __init__(self, db_path="BaseDeDatos.db"):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def ejecutar(self, query, params=()):
        self.cursor.execute(query, params)

    def confirmar(self):
        self.conn.commit()

    def revertir(self):
        self.conn.rollback()

    def iniciar(self):
        self.cursor.execute("BEGIN TRANSACTION")

    def obtener_uno(self, query, params=()):
        self.cursor.execute(query, params)
        return self.cursor.fetchone()

    def obtener_todos(self, query, params=()):
        self.cursor.execute(query, params)
        return self.cursor.fetchall()

    def cerrar(self):
        self.conn.close()

db = DBManager()