import sqlite3

class DBManager:
    def __init__(self, db_path="BaseDeDatos.db"):
        self._path = db_path
        self._conn = None
        self.abrir_conexion() # Abre la conexión al inicializar

    def abrir_conexion(self):
        """Intenta abrir la conexión, configurando los parámetros."""
        if self._conn is None:
            try:
                self._conn = sqlite3.connect(self._path)
                self._conn.execute("PRAGMA foreign_keys = ON")
                self._conn.row_factory = sqlite3.Row
            except sqlite3.Error as e:
                print(f"❌ Error al conectar a la base de datos: {e}")
                raise # Propaga el error para que el programa sepa que no puede continuar
    
    # ---------------------------------------------
    # 🛑 Cambios clave: Todos los métodos de consulta usan un nuevo cursor 
    # y manejan la conexión implícitamente o con el Context Manager.
    # ---------------------------------------------

    def ejecutar(self, query, params=()):
        """Ejecuta una sentencia de modificación (INSERT/UPDATE/DELETE)."""
        if self._conn is None: self.abrir_conexion()
        with self._conn: # Usa el context manager para COMMIT/ROLLBACK automáticos
            self._conn.execute(query, params)

    # Nota: Los métodos 'confirmar', 'revertir' e 'iniciar' ya no son necesarios
    # si se usa el context manager de la conexión.
    
    def obtener_uno(self, query, params=()):
        # Ejecuta una consulta y devuelve un único resultado como diccionario (dict).
        if self._conn is None: self.abrir_conexion()
        cursor = self._conn.cursor() # Crea un nuevo cursor por consulta
        cursor.execute(query, params)
        fila = cursor.fetchone()
        if fila:
            return dict(fila)
        else:
            return None

    def obtener_todos(self, query, params=()):
        # Ejecuta una consulta y devuelve todos los resultados como lista de diccionarios
        if self._conn is None: self.abrir_conexion()
        cursor = self._conn.cursor() # Crea un nuevo cursor por consulta
        cursor.execute(query, params)
        filas = cursor.fetchall()
        return [dict(fila) for fila in filas]
    
    def cerrar(self):
        """Cierra la conexión si está abierta."""
        if self._conn:
            self._conn.close()
            self._conn = None
            print("Conexión cerrada.")

db = DBManager() # Ahora la inicialización es más segura.