from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
from flask_bcrypt import Bcrypt
from functools import wraps
import os
import base64

app = Flask(__name__)
app.secret_key = 'mi_secreto'  # Cambia esto a algo seguro
bcrypt = Bcrypt(app)

def get_image_data(usuario):
    if usuario['imagen']:
        return base64.b64encode(usuario['imagen']).decode('utf-8')
    return None

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

@app.route('/')
@login_requerido
def index():
    conn = get_db_connection()
    usuario = conn.execute('SELECT * FROM usuarios WHERE usuarioId = ?', (session['user_id'],)).fetchone()
    conn.close()
    return render_template('index.html', usuario=usuario)

@app.route('/perfil')
@login_requerido
def perfil():
    conn = get_db_connection()
    usuario = conn.execute('SELECT * FROM usuarios WHERE usuarioId = ?', (session['user_id'],)).fetchone()
    conn.close()
    imagen_data = get_image_data(usuario)  # Convertir la imagen a base64
    return render_template('perfil.html', usuario=usuario, imagen_data=imagen_data)

@app.route('/postulaciones')
@login_requerido
def postulaciones():
    return render_template('postulaciones.html')

@app.route('/solicitudes')
@login_requerido
def solicitudes():
    return render_template('solicitudes.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nombre = request.form['nombre']
        apellido = request.form['apellido']
        correo = request.form['correo']
        telefono = request.form['telefono']
        cedula = request.form['cedula']
        contrasena = request.form['contrasena']
        ciudad = request.form['ciudad']
        
        # Hash de la contraseña
        contrasena_hash = bcrypt.generate_password_hash(contrasena).decode('utf-8')

        # Procesar la imagen
        imagen = request.files.get('imagen')  # Cambié a get para evitar el KeyError
        if imagen:
            imagen_data = imagen.read()  # Leer la imagen como binario
        else:
            imagen_data = None  # Manejar el caso donde no se proporciona imagen

        # Inserta el nuevo usuario en la base de datos
        try:
            conn = get_db_connection()
            conn.execute('INSERT INTO usuarios (nombre, apellido, correo, telefono, cedula, contrasena, ciudad, imagen) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', 
                         (nombre, apellido, correo, telefono, cedula, contrasena_hash, ciudad, imagen_data))
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

        if usuario:  # Verificar la contraseña (debes implementar esta verificación)
            session['user_id'] = usuario['usuarioId']
            return redirect(url_for('index'))

    return render_template('login.html')

@app.route('/logout', methods=['GET', 'POST'])
@login_requerido
def logout():
    session.pop('usuarioId', None)  # Elimina la variable de sesión
    flash('Has cerrado sesión exitosamente.', 'success')
    return redirect(url_for('login'))  # Redirige a la página de inicio de sesión

if __name__ == '__main__':
    # Solo ejecutar si el archivo de la base de datos no existe
    if not os.path.exists('TaskLink.db'):
        # Aquí podrías crear la base de datos y las tablas si fuera necesario
        pass
    
    app.run(debug=True)
