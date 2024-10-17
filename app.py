from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
from flask_bcrypt import Bcrypt
from functools import wraps
import os
import base64
from datetime import datetime,  timedelta

app = Flask(__name__)
app.secret_key = 'mi_secreto'  # Cambia esto a algo seguro
bcrypt = Bcrypt(app)

# Conexión a la base de datos
def get_db_connection():
    conn = sqlite3.connect('TaskLink.db')
    conn.row_factory = sqlite3.Row  # Para acceder a las columnas por nombre
    return conn

def login_requerido(f):
    @wraps(f)
    def decorador(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))  # Redirige a la página de inicio de sesión
        return f(*args, **kwargs)
    return decorador


@app.template_filter('format_date')
def format_date(value):
    if value:
        # Convertir la cadena a datetime (suponiendo que la fecha está en UTC)
        utc_time = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        
        # Ajustar la hora para la zona horaria local (ejemplo: -5 horas para Colombia)
        local_time = utc_time + timedelta(hours=-5)  # Ajusta según tu zona horaria

        return local_time.strftime('%d-%m-%Y %I:%M %p')  # Formato 12 horas
    return value


@app.route('/')
@login_requerido
def index():
    conn = get_db_connection()
    
    # Obtener el tipo de orden desde la consulta
    order_by = request.args.get('order_by', 'Fecha_creacion')  # Valor por defecto
    sort_order = request.args.get('sort_order', 'asc')  # Valor por defecto: ascendente
    
    # Validar el orden
    if sort_order not in ['asc', 'desc']:
        sort_order = 'asc'
    
    # Consulta SQL con ordenamiento
    tareas = conn.execute(f'''
        SELECT T.ID_tarea, T.Descripcion, T.Fecha_creacion, T.Fecha_limite, E.Nombre_estado
        FROM Tareas T
        JOIN Estados_Tareas E ON T.ID_estado = E.ID_estado
        ORDER BY {order_by} {sort_order}
    ''').fetchall()
    
    conn.close()
    return render_template('index.html', tareas=tareas, order_by=order_by, sort_order=sort_order)


@app.route('/perfil')
@login_requerido
def perfil():
    conn = get_db_connection()
    usuario = conn.execute('''
        SELECT U.*, T.Descripcion AS Tipo_Usuario, E.Descripcion AS Estado_Usuario
        FROM Usuarios U
        JOIN Tipos_Usuario T ON U.ID_tipo_cliente = T.ID_tipo_usuario 
        JOIN Estados_Usuarios E ON U.Estado = E.ID_estado_usuario
        WHERE U.ID_usuario = ?
    ''', (session['user_id'],)).fetchone()
    conn.close()

    # Convertir la imagen a base64 si existe
    imagen_base64 = None
    if usuario['Foto']:
        imagen_base64 = base64.b64encode(usuario['Foto']).decode('utf-8')

    return render_template('perfil.html', usuario=usuario, imagen_base64=imagen_base64)

@app.route('/postulaciones')
@login_requerido
def postulaciones():
    return render_template('postulaciones.html')

@app.route('/solicitudes')
@login_requerido
def solicitudes():
    conn = get_db_connection()
    
    # Obtener el tipo de orden desde la consulta
    order_by = request.args.get('order_by', 'Fecha_creacion')  # Valor por defecto
    sort_order = request.args.get('sort_order', 'asc')  # Valor por defecto: ascendente
    
    # Validar el orden
    if sort_order not in ['asc', 'desc']:
        sort_order = 'asc'
    
    # Obtener todas las solicitudes creadas por el usuario, con el nombre del estado
    solicitudes = conn.execute(f'''
        SELECT T.ID_tarea, T.Descripcion, T.Fecha_creacion, E.Nombre_estado
        FROM Tareas T
        JOIN Estados_Tareas E ON T.ID_estado = E.ID_estado
        WHERE T.ID_creador = ?
        ORDER BY {order_by} {sort_order}
    ''', (session['user_id'],)).fetchall()
    
    conn.close()

    # Renderiza la plantilla y pasa las solicitudes
    return render_template('solicitudes.html', solicitudes=solicitudes, order_by=order_by, sort_order=sort_order)

@app.route('/agregar_solicitud', methods=['GET', 'POST'])
@login_requerido
def agregar_solicitud():
    if request.method == 'POST':
        descripcion = request.form['descripcion']
        fecha_limite = request.form['fecha_limite']
        estado = 1  
        
        fecha_creacion = datetime.now().strftime('%d/%m/%Y %H:%M')
        fecha_limite_obj = datetime.strptime(fecha_limite, '%Y-%m-%dT%H:%M')
        fecha_limite_formateada = fecha_limite_obj.strftime('%d/%m/%Y %H:%M')
        
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO Tareas (ID_creador, Descripcion, Fecha_creacion, ID_estado, Fecha_limite)
            VALUES (?, ?, ?, ?, ?)
        ''', (session['user_id'], descripcion, fecha_creacion, estado, fecha_limite_formateada))
        conn.commit()
        conn.close()
        
        return redirect(url_for('solicitudes'))
    
    return render_template('agregar_solicitud.html')




@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nombre = request.form['nombre']
        apellido = request.form['apellido']
        correo = request.form['correo']
        celular = request.form['telefono']  # Cambiar 'telefono' a 'celular'
        cedula = request.form['cedula']
        contrasena = request.form['contrasena']
        tipo_cliente = 1  # Tipo cliente predeterminado
        estado = 1  # Estado predeterminado
        ciudad = request.form['ciudad']
        
        # Procesar la imagen subida
        imagen = request.files['imagen'].read()  # Lee la imagen como BLOB
        
        # Hash de la contraseña
        contrasena_hash = bcrypt.generate_password_hash(contrasena).decode('utf-8')

        # Inserta el nuevo usuario en la base de datos
        try:
            conn = get_db_connection()
            conn.execute('''
                INSERT INTO Usuarios (Nombre, Apellido, Correo, Celular, Cedula, Contrasena, ID_tipo_cliente, Estado, Ciudad, Foto) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (nombre, apellido, correo, celular, cedula, contrasena_hash, tipo_cliente, estado, ciudad, imagen))
            conn.commit()
            conn.close()
            flash('Registro exitoso. Puedes iniciar sesión.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            conn.rollback()
            conn.close()
            flash('Error al registrarse: ' + str(e), 'danger')

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form['correo']
        contrasena = request.form['contrasena']

        conn = get_db_connection()
        usuario = conn.execute('SELECT * FROM usuarios WHERE correo = ?', (correo,)).fetchone()
        conn.close()

        if usuario and bcrypt.check_password_hash(usuario['contrasena'], contrasena):  # Verifica la contraseña
            session['user_id'] = usuario['ID_usuario']
            return redirect(url_for('index'))
        else:
            flash('Correo o contraseña incorrectos.', 'danger')  # Mensaje de error

    return render_template('login.html')


@app.route('/logout', methods=['GET', 'POST'])
@login_requerido
def logout():
    session.pop('ID_usuario', None)  # Elimina la variable de sesión
    flash('Has cerrado sesión exitosamente.', 'success')
    return redirect(url_for('login'))  # Redirige a la página de inicio de sesión

if __name__ == '__main__':
    # Solo ejecutar si el archivo de la base de datos no existe
    if not os.path.exists('TaskLink.db'):
        # Aquí podrías crear la base de datos y las tablas si fuera necesario
        pass
    
    app.run(debug=True)
