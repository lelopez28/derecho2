import os
import json
import random
import string
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename, quote
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__, template_folder='templates')
app.secret_key = os.environ.get('SECRET_KEY', 'una_clave_muy_segura_y_larga')  # Usar variable de entorno para seguridad
DB_PATH = os.path.join('/data', 'casos.db')  # Cambiado a la ruta del Persistent Disk
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Configuración de email (ajusta estas variables en Render como variables de entorno)
EMAIL_USER = os.environ.get('EMAIL_USER', 'tu_email@gmail.com')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', 'tu_contraseña_de_app')

# Función para conectar o crear la base de datos
def connect_db():
    db_path = os.path.join('/data', 'casos.db')
    print(f"Verificando base de datos en: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Verificar si las tablas existen y si están vacías
    tablas = ['usuarios', 'juicios', 'alegatos', 'casos_penales', 'casos_civil', 'casos_tierras', 
              'casos_administrativo', 'casos_familia', 'casos_ninos']
    crear_tablas = False
    
    for tabla in tablas:
        cursor.execute(f"SELECT count(name) FROM sqlite_master WHERE type='table' AND name='{tabla}'")
        if cursor.fetchone()[0] == 0:
            crear_tablas = True
            break
    
    if crear_tablas:
        print(f"Alguna tabla no existe, creando todas las tablas en: {db_path}")
        # Crear todas las tablas si alguna falta
        cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            email TEXT NOT NULL,
            real_name TEXT NOT NULL,
            points INTEGER DEFAULT 0
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS juicios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tabla TEXT NOT NULL,
            caso_id INTEGER NOT NULL,
            fiscal_id INTEGER,
            defensor_id INTEGER,
            fiscal_alegato TEXT,
            defensor_alegato TEXT,
            estado TEXT DEFAULT 'pendiente',
            fiscal_puntos INTEGER,
            defensor_puntos INTEGER,
            ganador_id INTEGER,
            resultado TEXT
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS alegatos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tabla TEXT NOT NULL,
            caso_id INTEGER NOT NULL,
            rol TEXT NOT NULL,
            alegato TEXT NOT NULL,
            puntos INTEGER NOT NULL,
            fecha DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS casos_penales (
            id INTEGER PRIMARY KEY,
            titulo TEXT NOT NULL,
            hechos TEXT NOT NULL,
            pruebas TEXT,
            testigos TEXT,
            defensa TEXT,
            ley TEXT NOT NULL,
            procedimiento TEXT,
            dificultad INTEGER
        )''')
        # ... (continúa con las otras tablas como en tu código original)
    else:
        print(f"Tablas existentes en: {db_path}, verificando datos...")
        # Verificar si hay datos en las tablas clave
        cursor.execute("SELECT COUNT(*) FROM usuarios")
        usuarios_count = cursor.fetchone()[0]
        print(f"Usuarios en la base de datos: {usuarios_count}")
        cursor.execute("SELECT COUNT(*) FROM casos_penales")
        casos_penales_count = cursor.fetchone()[0]
        print(f"Casos en casos_penales: {casos_penales_count}")
        # Opcional: Inspeccionar más tablas si es necesario
        cursor.execute("SELECT COUNT(*) FROM casos_civil")
        print(f"Casos en casos_civil: {cursor.fetchone()[0]}")
        cursor.execute("SELECT COUNT(*) FROM juicios")
        print(f"Juicios en la base de datos: {cursor.fetchone()[0]}")
    
    conn.close()
    return sqlite3.connect(db_path)

# Funciones auxiliares
def generate_recovery_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def get_user_info(user_id):
    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT real_name, points FROM usuarios WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()
        if user:
            points = user[1] if user[1] else 0
            if points < 50:
                rank = "Abogado Novato"
            elif points < 150:
                rank = "Abogado Junior"
            elif points < 300:
                rank = "Abogado Senior"
            elif points < 500:
                rank = "Fiscal Experto"
            else:
                rank = "Maestro del Derecho"
            return {"real_name": user[0], "points": points, "rank": rank}  # Eliminado photo_path
        print(f"No se encontró usuario con id {user_id}")
        return None
    except sqlite3.Error as e:
        flash(f"Error en la base de datos: {e}")
        return None

def login_required(f):
    def wrap(*args, **kwargs):
        if 'user_id' not in session:
            flash("Por favor, inicia sesión primero.")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

def evaluar_alegato(alegato, caso):
    puntos = 0
    retroalimentacion = []
    alegato = alegato.lower().strip()

    ley = caso['ley'].lower()
    if ley in alegato:
        puntos += 25
        retroalimentacion.append("+25 puntos: Mencionaste la ley aplicable correctamente.")
    else:
        retroalimentacion.append("0 puntos: No mencionaste la ley aplicable (" + caso['ley'] + ").")

    pruebas = caso['pruebas']
    pruebas_mencionadas = sum(1 for prueba in pruebas.keys() if prueba.lower() in alegato)
    puntos_pruebas = min(pruebas_mencionadas * 5, 20)
    puntos += puntos_pruebas
    if pruebas_mencionadas > 0:
        retroalimentacion.append(f"+{puntos_pruebas} puntos: Mencionaste {pruebas_mencionadas} de {len(pruebas)} pruebas.")
    else:
        retroalimentacion.append("0 puntos: No mencionaste ninguna prueba.")

    testigos = caso['testigos']
    testigos_mencionados = sum(1 for testigo in testigos.keys() if testigo.lower() in alegato)
    puntos_testigos = min(testigos_mencionados * 5, 20)
    puntos += puntos_testigos
    if testigos_mencionados > 0:
        retroalimentacion.append(f"+{puntos_testigos} puntos: Mencionaste {testigos_mencionados} de {len(testigos)} testigos.")
    else:
        retroalimentacion.append("0 puntos: No mencionaste ningún testigo.")

    palabras_solicitud = ["solicito", "pido", "requiero", "sentencia", "fallo"]
    if any(palabra in alegato for palabra in palabras_solicitud):
        puntos += 15
        retroalimentacion.append("+15 puntos: Incluiste una solicitud clara.")
    else:
        retroalimentacion.append("0 puntos: No hiciste una solicitud clara.")

    roles_validos = ["fiscal", "defensor", "abogado", "demandante", "demandado", "recurrente", "administración", "ministerio", "público"]
    if any(rol in alegato for rol in roles_validos):
        puntos += 20
        retroalimentacion.append("+20 puntos: Mencionaste tu rol.")
    else:
        retroalimentacion.append("0 puntos: No mencionaste tu rol.")

    if len(alegato.split()) < 20:
        puntos -= 10
        retroalimentacion.append("-10 puntos: Alegato demasiado corto (< 20 palabras).")
    else:
        retroalimentacion.append("+0 puntos: Longitud adecuada (>= 20 palabras).")

    puntos = max(0, min(puntos, 100))
    resultado = f"Puntuación total: {puntos}/100\n\nDetalles:\n" + "\n".join(retroalimentacion)
    return puntos, resultado

# Rutas de autenticación
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM usuarios WHERE username = ?", (username,))
            user = cursor.fetchone()
            conn.close()
            if user and check_password_hash(user[2], password):
                session['user_id'] = user[0]
                session['real_name'] = user[4]
                return redirect(url_for('inicio'))
            else:
                flash("Usuario o contraseña incorrectos")
        except sqlite3.Error as e:
            print(f"Error en la base de datos: {e}")
            flash(f"Error en la base de datos: {e}")
        except Exception as e:
            print(f"Error inesperado: {e}")
            flash(f"Error inesperado: {e}")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('real_name', None)
    flash("Has cerrado sesión")
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')
        real_name = request.form.get('real_name')
        if not all([username, password, email, real_name]):
            flash("Faltan datos")
            return render_template('register.html'), 400
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM usuarios WHERE username = ? OR email = ?", (username, email))
            if cursor.fetchone():
                conn.close()
                flash("El usuario o correo ya están registrados")
                return render_template('register.html'), 400
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            cursor.execute("INSERT INTO usuarios (username, password, email, real_name, points) VALUES (?, ?, ?, ?, 0)", 
                           (username, hashed_password, email, real_name))
            conn.commit()
            conn.close()
            flash("Registro exitoso, ahora puedes iniciar sesión")
            return redirect(url_for('login'))
        except sqlite3.Error as e:
            flash(f"Error en la base de datos: {e}")
            return render_template('register.html'), 500
    return render_template('register.html')

@app.route('/recover', methods=['GET', 'POST'])
def recover():
    reset = False
    if request.method == 'POST':
        if 'email' in request.form:
            email = request.form['email']
            try:
                conn = connect_db()
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM usuarios WHERE email = ?", (email,))
                user = cursor.fetchone()
                conn.close()
                if user:
                    code = generate_recovery_code()
                    session['recovery_code'] = code
                    session['recovery_email'] = email
                    msg = MIMEText(f'Tu código de recuperación es: {code}')
                    msg['Subject'] = 'Recuperación de contraseña'
                    msg['From'] = EMAIL_USER
                    msg['To'] = email
                    try:
                        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
                        server.login(EMAIL_USER, EMAIL_PASSWORD)
                        server.sendmail(EMAIL_USER, email, msg.as_string())
                        server.quit()
                        flash("Código de recuperación enviado a tu correo.")
                        reset = True
                    except Exception as e:
                        flash(f"Error enviando el correo: {e}")
                else:
                    flash("Correo no encontrado.")
            except sqlite3.Error as e:
                flash(f"Error en la base de datos: {e}")
        elif 'code' in request.form and 'new_password' in request.form:
            code = request.form['code']
            new_password = request.form['new_password']
            if code == session.get('recovery_code'):
                email = session.get('recovery_email')
                hashed_password = generate_password_hash(new_password, method='pbkdf2:sha256')
                try:
                    conn = connect_db()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE usuarios SET password = ? WHERE email = ?", (hashed_password, email))
                    conn.commit()
                    conn.close()
                    flash("Contraseña cambiada correctamente.")
                    return redirect(url_for('login'))
                except sqlite3.Error as e:
                    flash(f"Error en la base de datos: {e}")
            else:
                flash("Código incorrecto.")
                reset = True
    return render_template('recover.html', reset=reset)

# Ruta principal del juego
@app.route('/inicio')
@login_required
def inicio():
    user_info = get_user_info(session['user_id'])
    if not user_info:
        return redirect(url_for('logout'))
    return render_template('inicio.html', user_info=user_info)

# Rutas para listar casos por materia
@app.route('/penal')
@login_required
def penal():
    return lista_casos('casos_penales', 'penal.html')

@app.route('/civil')
@login_required
def civil():
    return lista_casos('casos_civil', 'civil.html')

@app.route('/tierras')
@login_required
def tierras():
    return lista_casos('casos_tierras', 'tierras.html')

@app.route('/administrativo')
@login_required
def administrativo():
    return lista_casos('casos_administrativo', 'administrativo.html')

@app.route('/familia')
@login_required
def familia():
    return lista_casos('casos_familia', 'familia.html')

@app.route('/ninos')
@login_required
def ninos():
    return lista_casos('casos_ninos', 'ninos.html')

def lista_casos(tabla, template_name):
    user_info = get_user_info(session['user_id'])
    if not user_info:
        return redirect(url_for('login'))
    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute(f"SELECT id, titulo, hechos, pruebas, testigos, defensa, ley, procedimiento, dificultad FROM {tabla}")
        casos_data = cursor.fetchall()
        casos = [dict(id=row[0], titulo=row[1], hechos=row[2], pruebas=json.loads(row[3]) if row[3] else {},
                      testigos=json.loads(row[4]) if row[4] else {}, defensa=row[5], ley=row[6], procedimiento=row[7],
                      dificultad=row[8] if row[8] is not None else 0)
                 for row in casos_data]
        conn.close()
        if not casos_data:
            flash(f"No se encontraron casos en {tabla}")
        return render_template(template_name, casos=casos, user_info=user_info)
    except sqlite3.Error as e:
        flash(f"Error en la base de datos: {e}")
        return redirect(url_for('inicio'))

# Ruta para resolver un caso (modo solitario)
@app.route('/caso/<tabla>/<int:caso_id>', methods=['GET', 'POST'])
@login_required
def caso(tabla, caso_id):
    user_info = get_user_info(session['user_id'])
    if not user_info:
        return redirect(url_for('login'))

    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute(f"SELECT id, titulo, hechos, pruebas, testigos, defensa, ley, procedimiento FROM {tabla} WHERE id = ?", (caso_id,))
        caso_data = cursor.fetchone()
        if not caso_data:
            conn.close()
            flash("Caso no encontrado")
            return redirect(url_for('inicio'))

        caso = {
            'id': caso_data[0],
            'titulo': caso_data[1],
            'hechos': caso_data[2],
            'pruebas': json.loads(caso_data[3]) if caso_data[3] else {},
            'testigos': json.loads(caso_data[4]) if caso_data[4] else {},
            'defensa': caso_data[5],
            'ley': caso_data[6],
            'procedimiento': caso_data[7]
        }
        
        resultado = None
        if request.method == 'POST':
            rol = request.form.get('rol')
            alegato = request.form.get('argumento')
            if rol and alegato:
                puntos, evaluacion = evaluar_alegato(alegato, caso)
                nuevos_puntos = user_info['points'] + puntos
                cursor.execute("UPDATE usuarios SET points = ? WHERE id = ?", (nuevos_puntos, session['user_id']))
                cursor.execute("INSERT INTO alegatos (user_id, tabla, caso_id, rol, alegato, puntos) VALUES (?, ?, ?, ?, ?, ?)",
                               (session['user_id'], tabla, caso_id, rol, alegato, puntos))
                conn.commit()
                resultado = evaluacion
            else:
                flash("Faltan datos en el formulario")

        conn.close()
        endpoint_map = {
            'casos_penales': 'penal',
            'casos_civil': 'civil',
            'casos_tierras': 'tierras',
            'casos_administrativo': 'administrativo',
            'casos_familia': 'familia',
            'casos_ninos': 'ninos'
        }
        endpoint = endpoint_map.get(tabla, 'inicio')
        return render_template('casos.html', caso=caso, user_info=user_info, resultado=resultado, tabla=tabla, endpoint=endpoint)
    except sqlite3.Error as e:
        flash(f"Error en la base de datos: {e}")
        return redirect(url_for('inicio'))

# Ruta para resolver un caso en modo multijugador
@app.route('/caso/<tabla>/<int:caso_id>/multi', methods=['GET', 'POST'])
@login_required
def caso_multi(tabla, caso_id):
    user_info = get_user_info(session['user_id'])
    if not user_info:
        return redirect(url_for('login'))

    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute(f"SELECT id, titulo, hechos, pruebas, testigos, defensa, ley, procedimiento FROM {tabla} WHERE id = ?", (caso_id,))
        caso_data = cursor.fetchone()
        if not caso_data:
            conn.close()
            flash("Caso no encontrado")
            return redirect(url_for('inicio'))

        caso = {
            'id': caso_data[0],
            'titulo': caso_data[1],
            'hechos': caso_data[2],
            'pruebas': json.loads(caso_data[3]) if caso_data[3] else {},
            'testigos': json.loads(caso_data[4]) if caso_data[4] else {},
            'defensa': caso_data[5],
            'ley': caso_data[6],
            'procedimiento': caso_data[7]
        }

        endpoint_map = {
            'casos_penales': 'penal',
            'casos_civil': 'civil',
            'casos_tierras': 'tierras',
            'casos_administrativo': 'administrativo',
            'casos_familia': 'familia',
            'casos_ninos': 'ninos'
        }
        endpoint = endpoint_map.get(tabla, 'inicio')

        roles_map = {
            'casos_penales': ('Fiscal', 'Abogado Defensor'),
            'casos_civil': ('Demandante', 'Demandado'),
            'casos_tierras': ('Demandante', 'Demandado'),
            'casos_administrativo': ('Recurrente', 'Administración'),
            'casos_familia': ('Demandante', 'Demandado'),
            'casos_ninos': ('Ministerio Público', 'Abogado Defensor')
        }
        rol1, rol2 = roles_map.get(tabla, ('Jugador 1', 'Jugador 2'))

        cursor.execute("SELECT id, fiscal_id, defensor_id, fiscal_alegato, defensor_alegato, estado, fiscal_puntos, defensor_puntos, ganador_id, resultado FROM juicios WHERE tabla = ? AND caso_id = ? ORDER BY id DESC LIMIT 1", (tabla, caso_id))
        juicio = cursor.fetchone()

        if request.method == 'GET':
            if not juicio or juicio[5] == 'completado':
                cursor.execute("INSERT INTO juicios (tabla, caso_id) VALUES (?, ?)", (tabla, caso_id))
                juicio_id = cursor.lastrowid
                conn.commit()
                juicio = (juicio_id, None, None, None, None, 'pendiente', None, None, None, None)
            else:
                juicio_id = juicio[0]

            if juicio[5] == 'completado' and juicio[9]:
                resultado = juicio[9].replace('Oponente', get_user_info(juicio[1])['real_name'] if session['user_id'] == juicio[2] else get_user_info(juicio[2])['real_name'] if session['user_id'] == juicio[1] else 'Oponente')
                return render_template('casos_multi.html', caso=caso, user_info=user_info, resultado=resultado, juicio_id=juicio_id, fiscal_id=juicio[1], defensor_id=juicio[2], endpoint=endpoint, rol1=rol1, rol2=rol2)

            return render_template('casos_multi.html', caso=caso, user_info=user_info, juicio_id=juicio_id, fiscal_id=juicio[1], defensor_id=juicio[2], endpoint=endpoint, rol1=rol1, rol2=rol2)

        if request.method == 'POST':
            rol = request.form.get('rol')
            alegato = request.form.get('argumento')
            juicio_id = request.form.get('juicio_id')

            if not rol or not alegato or not juicio_id:
                flash("Faltan datos en el formulario")
                return render_template('casos_multi.html', caso=caso, user_info=user_info, juicio_id=juicio_id, fiscal_id=juicio[1] if juicio else None, defensor_id=juicio[2] if juicio else None, endpoint=endpoint, rol1=rol1, rol2=rol2)

            cursor.execute("SELECT fiscal_id, defensor_id, fiscal_alegato, defensor_alegato, estado FROM juicios WHERE id = ?", (juicio_id,))
            juicio = cursor.fetchone()
            if not juicio or juicio[4] != 'pendiente':
                flash("El juicio no está disponible o ya fue completado")
                return redirect(url_for(endpoint))

            fiscal_id, defensor_id, fiscal_alegato, defensor_alegato = juicio[0], juicio[1], juicio[2], juicio[3]

            if rol == rol1 and not fiscal_id:
                cursor.execute("UPDATE juicios SET fiscal_id = ?, fiscal_alegato = ? WHERE id = ?", (session['user_id'], alegato, juicio_id))
            elif rol == rol2 and not defensor_id:
                cursor.execute("UPDATE juicios SET defensor_id = ?, defensor_alegato = ? WHERE id = ?", (session['user_id'], alegato, juicio_id))
            else:
                flash("El rol seleccionado ya está ocupado o no es válido")
                return render_template('casos_multi.html', caso=caso, user_info=user_info, juicio_id=juicio_id, fiscal_id=fiscal_id, defensor_id=defensor_id, endpoint=endpoint, rol1=rol1, rol2=rol2)

            conn.commit()

            cursor.execute("SELECT fiscal_id, defensor_id, fiscal_alegato, defensor_alegato FROM juicios WHERE id = ?", (juicio_id,))
            juicio_actualizado = cursor.fetchone()
            if juicio_actualizado[2] and juicio_actualizado[3]:
                fiscal_puntos, fiscal_eval = evaluar_alegato(juicio_actualizado[2], caso)
                defensor_puntos, defensor_eval = evaluar_alegato(juicio_actualizado[3], caso)
                ganador_id = juicio_actualizado[0] if fiscal_puntos > defensor_puntos else juicio_actualizado[1]
                resultado = f"Juicio Completado\n{rol1} ({get_user_info(juicio_actualizado[0])['real_name'] if juicio_actualizado[0] else 'Oponente'}): {fiscal_puntos}/100\n{fiscal_eval}\n\n{rol2} ({get_user_info(juicio_actualizado[1])['real_name'] if juicio_actualizado[1] else 'Oponente'}): {defensor_puntos}/100\n{defensor_eval}\n\nGanador: {rol1 if fiscal_puntos > defensor_puntos else rol2}"
                cursor.execute("UPDATE juicios SET fiscal_puntos = ?, defensor_puntos = ?, estado = 'completado', ganador_id = ?, resultado = ? WHERE id = ?",
                               (fiscal_puntos, defensor_puntos, ganador_id, resultado, juicio_id))
                cursor.execute("UPDATE usuarios SET points = points + ? WHERE id = ?", (fiscal_puntos, juicio_actualizado[0]))
                cursor.execute("UPDATE usuarios SET points = points + ? WHERE id = ?", (defensor_puntos, juicio_actualizado[1]))
                cursor.execute("INSERT INTO alegatos (user_id, tabla, caso_id, rol, alegato, puntos) VALUES (?, ?, ?, ?, ?, ?)",
                               (juicio_actualizado[0], tabla, caso_id, rol1, juicio_actualizado[2], fiscal_puntos))
                cursor.execute("INSERT INTO alegatos (user_id, tabla, caso_id, rol, alegato, puntos) VALUES (?, ?, ?, ?, ?, ?)",
                               (juicio_actualizado[1], tabla, caso_id, rol2, juicio_actualizado[3], defensor_puntos))
                conn.commit()
            else:
                resultado = "Esperando al oponente para completar el juicio..."

            conn.close()
            return render_template('casos_multi.html', caso=caso, user_info=user_info, resultado=resultado, juicio_id=juicio_id, fiscal_id=juicio_actualizado[0], defensor_id=juicio_actualizado[1], endpoint=endpoint, rol1=rol1, rol2=rol2)

    except sqlite3.Error as e:
        flash(f"Error en la base de datos: {e}")
        return redirect(url_for('inicio'))

# Ruta para el perfil
@app.route('/perfil')
@login_required
def perfil():
    user_info = get_user_info(session['user_id'])
    if not user_info:
        return redirect(url_for('login'))

    try:
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*), AVG(puntos) FROM alegatos WHERE user_id = ?", (session['user_id'],))
        total_casos, promedio_puntos = cursor.fetchone()
        total_casos = total_casos or 0
        promedio_puntos = round(promedio_puntos or 0, 2)

        cursor.execute("""
            SELECT a.tabla, a.caso_id, c.titulo, a.rol, a.puntos, a.fecha
            FROM alegatos a
            LEFT JOIN (
                SELECT id, titulo, 'casos_penales' AS tabla FROM casos_penales UNION
                SELECT id, titulo, 'casos_civil' FROM casos_civil UNION
                SELECT id, titulo, 'casos_tierras' FROM casos_tierras UNION
                SELECT id, titulo, 'casos_administrativo' FROM casos_administrativo UNION
                SELECT id, titulo, 'casos_familia' FROM casos_familia UNION
                SELECT id, titulo, 'casos_ninos' FROM casos_ninos
            ) c ON a.tabla = c.tabla AND a.caso_id = c.id
            WHERE a.user_id = ?
            ORDER BY a.fecha DESC
        """, (session['user_id'],))
        casos_resueltos = cursor.fetchall()
        casos_resueltos = [dict(tabla=row[0], caso_id=row[1], titulo=row[2], rol=row[3], puntos=row[4], fecha=row[5]) for row in casos_resueltos]

        cursor.execute("SELECT id, real_name, points FROM usuarios ORDER BY points DESC LIMIT 5")
        ranking = cursor.fetchall()
        ranking = [dict(id=row[0], real_name=row[1], points=row[2]) for row in ranking]

        conn.close()

        return render_template('perfil.html', user_info=user_info, total_casos=total_casos, promedio_puntos=promedio_puntos, casos_resueltos=casos_resueltos, ranking=ranking)

    except sqlite3.Error as e:
        flash(f"Error en la base de datos: {e}")
        return redirect(url_for('inicio'))

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    print(f"Usando base de datos en: {DB_PATH}")
    port = int(os.environ.get('PORT', 5003))  # Puerto dinámico para Render
    app.run(host='0.0.0.0', port=port, debug=True)
