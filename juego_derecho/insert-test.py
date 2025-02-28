import sqlite3
import json
from werkzeug.security import generate_password_hash

# Conectar a la base de datos local
db_path = 'C:/Users/lelopez/Desktop/juego_derecho/casos.db'  # Ajusta la ruta si es c:/Users/lelopez/Documents/derecho2/juego_derecho/casos.db
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Insertar usuario
cursor.execute("""
    INSERT INTO usuarios (username, password, email, real_name, points)
    VALUES (?, ?, ?, ?, ?)
""", (
    "lelopez2",
    "pbkdf2:sha256:1000000$Cd6VcKuugt98kUR0$142de01314dc3703c28c533c05cc13e6989e2ada65d546356b07c26d7d0f3070",  # Usa el hash exacto de tu salida
    "lelopezcruz@gmail.com",
    "Leandro López Cruz",
    -20
))

# Insertar casos en casos_penales (primeros 5 casos de tu salida)
cursor.execute("""
    INSERT INTO casos_penales (titulo, hechos, pruebas, testigos, defensa, ley, procedimiento, dificultad)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", (
    "El Caso del Mango Robado",
    "Juan acusa a María de robarle un mango de su árbol el 5 de febrero en Villa Mella. María sostiene que el mango cayó solo y ella lo recogió para consumirlo.",
    '{"Huellas en el patio": 8, "Foto borrosa de María cerca del árbol": 3}',
    '{"Vecino Juan (vio a María trepada)": 6, "Vecino Pedro (el árbol estaba podrido)": 4}',
    "María sostiene que no hubo hurto porque el mango ya estaba en el suelo.",
    "Código Penal RD, Art. 379 (Hurto): Pena de 3 meses a 1 año o multa.",
    "Código Procesal Penal RD, Art. 169: La admisibilidad de las pruebas debe ser demostrada por el Fiscal.",
    4
))
# Repite para los otros 4 casos en casos_penales, y para casos_civil, casos_tierras, etc., usando los datos de tu salida.

# Insertar juicios y alegatos (puedes hacerlo manualmente o con un script más complejo basado en tu salida)
# Ejemplo para un juicio
cursor.execute("""
    INSERT INTO juicios (tabla, caso_id, fiscal_id, defensor_id, fiscal_alegato, defensor_alegato, estado, fiscal_puntos, defensor_puntos, ganador_id, fecha, resultado)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    "casos_penales", 1, 1, 1, "Perdiste", "No se", "completado", 0, 0, 1, "2025-02-25 19:05:07", None
))

conn.commit()
conn.close()
print("Datos iniciales insertados en casos.db")