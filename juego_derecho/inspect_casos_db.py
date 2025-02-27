import sqlite3
import json

# Conectar a la base de datos local
db_path = 'C:/Users/lelopez/Desktop/juego_derecho/casos.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Lista de tablas esperadas en tu base de datos
tablas = [
    'usuarios', 'juicios', 'alegatos',
    'casos_penales', 'casos_civil', 'casos_tierras',
    'casos_administrativo', 'casos_familia', 'casos_ninos'
]

print("=== Inspección de la base de datos casos.db ===")

# Verificar y listar las tablas existentes
print("\nTablas en la base de datos:")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tablas_en_db = [row[0] for row in cursor.fetchall()]
for tabla in tablas:
    if tabla in tablas_en_db:
        print(f"- {tabla} (existe)")
    else:
        print(f"- {tabla} (NO existe)")

# Inspeccionar cada tabla existente
for tabla in [t for t in tablas if t in tablas_en_db]:
    print(f"\n=== Tabla: {tabla} ===")
    
    # Mostrar la estructura (columnas) de la tabla
    cursor.execute(f"PRAGMA table_info({tabla})")
    columnas = cursor.fetchall()
    print("Columnas:")
    for columna in columnas:
        print(f"  - {columna[1]} ({columna[2]})")
    
    # Contar el número de registros
    cursor.execute(f"SELECT COUNT(*) FROM {tabla}")
    num_registros = cursor.fetchone()[0]
    print(f"Número de registros: {num_registros}")
    
    # Mostrar los primeros 5 registros (o todos si hay menos de 5)
    if num_registros > 0:
        print("Datos (primeros 5 registros):")
        cursor.execute(f"SELECT * FROM {tabla} LIMIT 5")
        filas = cursor.fetchall()
        for i, fila in enumerate(filas, 1):
            print(f"Registro {i}: {fila}")
            # Si hay JSON (pruebas o testigos), intentar deserializarlo
            if tabla in ['casos_penales', 'casos_civil', 'casos_tierras', 'casos_administrativo', 'casos_familia', 'casos_ninos']:
                if len(fila) > 3:  # Asegurarse de que hay suficientes columnas
                    try:
                        pruebas = json.loads(fila[3] if fila[3] else '{}')
                        print(f"  Pruebas: {pruebas}")
                    except json.JSONDecodeError:
                        print("  Pruebas: No es JSON válido o está vacío")
                    try:
                        testigos = json.loads(fila[4] if fila[4] else '{}')
                        print(f"  Testigos: {testigos}")
                    except json.JSONDecodeError:
                        print("  Testigos: No es JSON válido o está vacío")
    
    # Mostrar un mensaje si la tabla está vacía
    if num_registros == 0:
        print("La tabla está vacía.")

# Cerrar la conexión
conn.close()
print("\nInspección completada.")