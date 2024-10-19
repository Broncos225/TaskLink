from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
from flask_bcrypt import Bcrypt
from functools import wraps
import os
import base64
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'mi_secreto'
bcrypt = Bcrypt(app)

def get_db_connection():
    conn = sqlite3.connect('TaskLink.db')
    conn.row_factory = sqlite3.Row
    return conn

# ======================================================= #
#                   LOGIN REQUERIDO                       #
# ======================================================= #
def login_requerido(f):
    @wraps(f)
    def decorador(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorador

# ======================================================= #
#                      FILTRO DE FECHA                    #
# ======================================================= #
@app.template_filter('format_date')
def format_date(value):
    meses = {
        '01': 'Enero', '02': 'Febrero', '03': 'Marzo', '04': 'Abril',
        '05': 'Mayo', '06': 'Junio', '07': 'Julio', '08': 'Agosto',
        '09': 'Septiembre', '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
    }
    
    if value:
        try:
            utc_time = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            try:
                utc_time = datetime.strptime(value, '%Y-%m-%dT%H:%M')
            except ValueError:
                return value 

        local_time = utc_time - timedelta(hours=5)
        
        dia = local_time.strftime('%d')
        mes = meses[local_time.strftime('%m')]
        año = local_time.strftime('%Y')
        hora = local_time.strftime('%I:%M %p')

        return f"{dia} de {mes} del {año} {hora}"
    return value


# ======================================================= #
#                      ADMINISTRADOR                      #
# ======================================================= #
@app.route('/admin')
def admin():
    conn = get_db_connection()

    imagen_base64 = None
    if 'user_id' in session:
        usuario = conn.execute('SELECT FotoPerfil FROM Usuarios WHERE ID_usuario = ?', (session['user_id'],)).fetchone()
        if usuario and usuario['FotoPerfil']:
            imagen_base64 = base64.b64encode(usuario['FotoPerfil']).decode('utf-8')
    
    is_logged_in = 'user_id' in session
    
    usuarios = conn.execute('''
        SELECT u.*, tu.nombre AS tipo_usuario, eu.Nombre AS estado_usuario
        FROM Usuarios u
        JOIN Tipos_Usuarios tu ON u.ID_tipo_usuario = tu.ID_tipo_usuario
        JOIN Estados_Usuarios eu ON u.ID_estado_usuario = eu.ID_estado_usuario
    ''').fetchall()
    conn.close()
    return render_template('admin.html', usuarios=usuarios, imagen_base64=imagen_base64, is_logged_in=is_logged_in)

# ======================================================= #
#                      INICIO                             #
# ======================================================= #
@app.route('/')
def index():
    conn = get_db_connection()
    order_by = request.args.get('order_by', 'Fecha_creacion')
    sort_order = request.args.get('sort_order', 'asc')
    
    if sort_order not in ['asc', 'desc']:
        sort_order = 'asc'

    # Verifica si 'user_id' está en la sesión
    usuarios = None
    imagen_base64 = None
    is_logged_in = False

    if 'user_id' in session:
        # Solo busca al usuario si 'user_id' está presente en la sesión
        usuarios = conn.execute('SELECT * FROM Usuarios WHERE ID_usuario = ?', (session['user_id'],)).fetchone()
        usuario = conn.execute('SELECT FotoPerfil FROM Usuarios WHERE ID_usuario = ?', (session['user_id'],)).fetchone()
        if usuario and usuario['FotoPerfil']:
            imagen_base64 = base64.b64encode(usuario['FotoPerfil']).decode('utf-8')
        is_logged_in = True  # El usuario está autenticado

    conn.close()

    return render_template('index.html', usuarios=usuarios, imagen_base64=imagen_base64, is_logged_in=is_logged_in)

# ======================================================= #
#                      CALIFICAR TAREA                     #
# ======================================================= #
@app.route('/calificar/<int:tarea_id>', methods=['POST'])
@login_requerido
def calificar_tarea(tarea_id):
    calificacion = request.form['calificacion']
    usuario_actual = session['user_id']
    conn = get_db_connection()

    # Verificar si el usuario es el creador de la tarea y si ya está calificada
    tarea = conn.execute('SELECT ID_creador, Calificacion FROM Tareas WHERE ID_tarea = ?', (tarea_id,)).fetchone()

    if tarea is None:
        conn.close()
        return jsonify({'success': False, 'error': 'La tarea no existe.'})

    if tarea['ID_creador'] != usuario_actual:
        conn.close()
        return jsonify({'success': False, 'error': 'Solo el creador de la tarea puede calificarla.'})

    if tarea['Calificacion'] is not None and tarea['Calificacion'] != 0:
        conn.close()
        return jsonify({'success': False, 'error': 'Esta tarea ya ha sido calificada.'})

    # Guardar la calificación en la base de datos
    conn.execute('UPDATE Tareas SET Calificacion = ? WHERE ID_tarea = ?', (calificacion, tarea_id))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': 'Calificación registrada exitosamente.'})



# ======================================================= #
#                      LISTA DE TAREAS                    #
# ======================================================= #
@app.route('/tareas')
@login_requerido
def tareas():
    conn = get_db_connection()
    
    categoria_filtro = int(request.args.get('categoria', '')) if request.args.get('categoria', '').isdigit() else ''
    estado_filtro = int(request.args.get('estado', '')) if request.args.get('estado', '').isdigit() else ''
    orden = request.args.get('orden', 'asc')
    
    if orden not in ['asc', 'desc']:
        orden = 'asc'

    # Consulta con JOIN para obtener las tareas y sus detalles relacionados
    query = '''
        SELECT T.*, 
               C.Nombre AS Categoria, 
               ET.Descripcion AS Estado, 
               U1.Nombre AS CreadorNombre, 
               U1.Apellido AS CreadorApellido, 
               U2.Nombre AS TrabajadorNombre, 
               U2.Apellido AS TrabajadorApellido,
               T.Calificacion  -- Añadir la columna de calificación
        FROM Tareas T
        JOIN Categorias C ON T.ID_categoria = C.ID_categoria
        JOIN Estados_Tareas ET ON T.ID_estado_tarea = ET.ID_estado_tarea
        LEFT JOIN Usuarios U1 ON T.ID_creador = U1.ID_usuario
        LEFT JOIN Usuarios U2 ON T.ID_trabajador = U2.ID_usuario
    '''
    
    conditions = []
    params = []

    if categoria_filtro:
        conditions.append('T.ID_categoria = ?')
        params.append(categoria_filtro)

    if estado_filtro:
        conditions.append('T.ID_estado_tarea = ?')
        params.append(estado_filtro)

    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)

    query += f' ORDER BY T.Titulo {orden}'

    tareas = conn.execute(query, params).fetchall()

    # Obtener el usuario actual
    usuarios = conn.execute('SELECT * FROM Usuarios WHERE ID_usuario = ?', (session['user_id'],)).fetchone()
    
    imagen_base64 = None
    if 'user_id' in session:
        usuario = conn.execute('SELECT FotoPerfil FROM Usuarios WHERE ID_usuario = ?', (session['user_id'],)).fetchone()
        if usuario and usuario['FotoPerfil']:
            imagen_base64 = base64.b64encode(usuario['FotoPerfil']).decode('utf-8')
    
    categorias = conn.execute('SELECT * FROM Categorias').fetchall()
    estados = conn.execute('SELECT * FROM Estados_Tareas').fetchall()

    is_logged_in = 'user_id' in session
    conn.close()
    
    return render_template('tareas.html', tareas=tareas, categorias=categorias, 
                           estados=estados, imagen_base64=imagen_base64, 
                           usuarios=usuarios, is_logged_in=is_logged_in, 
                           categoria_filtro=categoria_filtro, estado_filtro=estado_filtro, 
                           orden=orden)



# ======================================================= #
#                      POSTULAR A TAREA                   #
# ======================================================= #
@app.route('/postular/<int:tarea_id>', methods=['POST'])
@login_requerido
def postular(tarea_id):
    usuario_actual = session['user_id']
    conn = get_db_connection()
    
    # Obtener la tarea específica
    tarea = conn.execute('SELECT ID_estado_tarea, ID_trabajador FROM Tareas WHERE ID_tarea = ?', (tarea_id,)).fetchone()
    
    # Verificar si la tarea existe
    if tarea is None:
        return jsonify({'success': False, 'error': 'La tarea no existe.'})

    # Verificar si la tarea está disponible para postulación
    if tarea['ID_estado_tarea'] != 1:
        return jsonify({'success': False, 'error': 'La tarea no está disponible para postulación.'})

    # Verificar si el usuario actual ya está postulado
    if tarea['ID_trabajador'] is not None and tarea['ID_trabajador'] == usuario_actual:
        return jsonify({'success': False, 'error': 'Ya te postulaste para esta tarea.'})

    # Si el ID_trabajador es diferente del usuario actual o es NULL, se puede postular
    if tarea['ID_trabajador'] is None or tarea['ID_trabajador'] != usuario_actual:
        # Actualizar el ID_trabajador y el estado de la tarea a 2 (Asumiendo que 2 es "En Proceso")
        conn.execute('UPDATE Tareas SET ID_trabajador = ?, ID_estado_tarea = ? WHERE ID_tarea = ?', (usuario_actual, 2, tarea_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True})

    conn.close()
    return jsonify({'success': False, 'error': 'No puedes postularte a esta tarea.'})


# ======================================================= #
#                      FINALIZAR TAREA                    #
# ======================================================= #
@app.route('/finalizar/<int:tarea_id>', methods=['POST'])
@login_requerido
def finalizar_tarea(tarea_id):
    usuario_actual = session['user_id']
    conn = get_db_connection()
    
    # Obtener la tarea específica
    tarea = conn.execute('SELECT ID_trabajador, ID_estado_tarea FROM Tareas WHERE ID_tarea = ?', (tarea_id,)).fetchone()

    # Verificar si la tarea existe
    if tarea is None:
        return jsonify({'success': False, 'error': 'La tarea no existe.'})

    # Verificar si el usuario actual es el trabajador asignado
    if tarea['ID_trabajador'] != usuario_actual:
        return jsonify({'success': False, 'error': 'Solo el trabajador asignado puede finalizar esta tarea.'})

    # Verificar si la tarea ya está finalizada
    if tarea['ID_estado_tarea'] == 3:  # Asumiendo que el estado 3 significa "finalizada"
        return jsonify({'success': False, 'error': 'La tarea ya está finalizada.'})

    # Marcar la tarea como finalizada
    conn.execute('UPDATE Tareas SET ID_estado_tarea = 3, Fecha_finalizacion = CURRENT_TIMESTAMP WHERE ID_tarea = ?', (tarea_id,))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': 'La tarea ha sido finalizada exitosamente.'})



# ======================================================= #
#                      DETALLES DE TAREA                  #
# ======================================================= #
@app.route('/detalles/<int:tarea_id>')
@login_requerido
def detalles_tarea(tarea_id):
    conn = get_db_connection()
    tarea = conn.execute('SELECT * FROM Tareas WHERE ID_tarea = ?', (tarea_id,)).fetchone()
    usuario_actual = session['user_id']  # Obtén el ID del usuario actual

    if tarea is None:
        return jsonify({'error': 'Tarea no encontrada.'}), 404

    print(f"Usuario actual: {usuario_actual}, ID creador de la tarea: {tarea['ID_creador']}")  # Depuración
    

    # Manejar los adjuntos
    adjuntos = []
    if tarea['Adjuntos']:
        adjunto_base64 = base64.b64encode(tarea['Adjuntos']).decode('utf-8')
        adjuntos.append(f'<img src="data:image/png;base64,{adjunto_base64}" alt="Adjunto" style="max-width: 100%;">')

    # Agregar ID_estado_tarea a la respuesta
    estado_tarea = tarea['ID_estado_tarea']  # Obtener el ID del estado de la tarea

    response_data = {
        'titulo': tarea['Titulo'],
        'descripcion': tarea['Descripcion'],
        'fecha_creacion': tarea['Fecha_creacion'],
        'fecha_limite': tarea['Fecha_limite'],
        'valor': tarea['Valor'],
        'adjuntos': adjuntos,
        'id_creador': tarea['ID_creador'],  # Pasar ID del creador
        'usuario_actual': usuario_actual,    # Pasar ID del usuario actual
        'id_trabajador': tarea['ID_trabajador'],  # Pasar ID del trabajador (si aplica)
        'estado_tarea': estado_tarea  # Agregar ID_estado_tarea
    }

    return jsonify(response_data)





# ======================================================= #
#                      AGREGAR TAREA                      #
# ======================================================= #
@app.route('/agregar_solicitud', methods=['GET', 'POST'])
@login_requerido
def agregar_solicitud():
    conn = get_db_connection()
    categorias = conn.execute('SELECT ID_categoria, Nombre FROM Categorias').fetchall()
    
    usuarios = conn.execute('SELECT * FROM Usuarios WHERE ID_usuario = ?', (session['user_id'],)).fetchone()
    
    imagen_base64 = None
    if 'user_id' in session:
        usuario = conn.execute('SELECT FotoPerfil FROM Usuarios WHERE ID_usuario = ?', (session['user_id'],)).fetchone()
        if usuario and usuario['FotoPerfil']:
            imagen_base64 = base64.b64encode(usuario['FotoPerfil']).decode('utf-8')
    
    is_logged_in = 'user_id' in session
    conn.close()
    
    if request.method == 'POST':
        titulo = request.form['titulo']
        descripcion = request.form['descripcion']
        categoria = request.form['categoria']
        valor = request.form['valor']
        fecha_limite = request.form['fecha_limite']
        
        adjunto = None
        if 'adjunto' in request.files and request.files['adjunto'].filename != '':
            adjunto = request.files['adjunto'].read()
        else:
            print("No se ha cargado ningún archivo adjunto.")
        
        estado = 1
        
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO Tareas (Titulo, Descripcion, Fecha_limite, Valor, Adjuntos, ID_estado_tarea, ID_categoria, ID_creador, ID_trabajador)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (titulo, descripcion, fecha_limite, valor, adjunto, estado, categoria, session['user_id'], None))
        conn.commit()
        conn.close()
        
        return redirect(url_for('index'))
    
    return render_template('agregar_solicitud.html', usuarios=usuarios, categorias=categorias, imagen_base64=imagen_base64, is_logged_in=is_logged_in)



# ======================================================= #
#                      EDITAR PERFIL                      #
# ======================================================= #
@app.route('/editar_perfil', methods=['GET'])
@login_requerido
def editar_perfil():
    conn = get_db_connection()
    ciudades = conn.execute('SELECT ID_ciudad, Nombre FROM Ciudades').fetchall()
    conn.close()
    conn = get_db_connection()
    usuario = conn.execute('''
        SELECT U.*, C.Nombre AS Ciudad
        FROM Usuarios U
        LEFT JOIN Ciudades C ON U.ID_ciudad = C.ID_ciudad
        WHERE U.ID_usuario = ?
    ''', (session['user_id'],)).fetchone()
    conn.close()

    return render_template('editar_perfil.html', usuario=usuario, ciudades=ciudades)

@app.route('/actualizar-perfil', methods=['POST'])
@login_requerido
def actualizar_perfil():
    nombre = request.form.get('nombre')
    apellido = request.form.get('apellido')
    correo = request.form.get('correo')
    identificacion = request.form.get('identificacion')
    direccion = request.form.get('direccion')
    telefono = request.form.get('telefono')
    ciudad = request.form.get('ciudad')

    if not all([nombre, apellido, correo, identificacion, direccion, telefono, ciudad]):
        print('Por favor, completa todos los campos')
        return redirect(url_for('editar_perfil'))  
    conn = get_db_connection()
    try:
        conn.execute('''
            UPDATE Usuarios
            SET Nombre = ?, Apellido = ?, Correo = ?, Identificacion = ?, Direccion = ?, Telefono = ?, ID_ciudad = ?
            WHERE ID_usuario = ?
        ''', (nombre, apellido, correo, identificacion, direccion, telefono, ciudad, session['user_id']))
        
        conn.commit()
        print('Perfil actualizado correctamente')
    except Exception as e:
        conn.rollback()
        print(f'Error al actualizar el perfil: {str(e)}')
    finally:
        conn.close()

    return redirect(url_for('profile'))

# ======================================================= #
#                      CAMBIAR FOTO                       #
# ======================================================= #
@app.route('/cambiar-foto', methods=['POST'])
@login_requerido
def cambiarFoto():
    if 'nueva_foto' not in request.files:
        print('No seleccionaste ningún archivo')
        return redirect(url_for('profile'))

    nueva_foto = request.files['nueva_foto']
    
    if nueva_foto.filename == '':
        print('No seleccionaste ningún archivo')
        return redirect(url_for('profile'))
    
    foto_blob = nueva_foto.read()

    conn = get_db_connection()
    conn.execute('''
        UPDATE Usuarios
        SET FotoPerfil = ?
        WHERE ID_usuario = ?
    ''', (foto_blob, session['user_id']))
    conn.commit()
    conn.close()

    print('Foto de perfil actualizada exitosamente')
    return redirect(url_for('profile'))


# ======================================================= #
#                      PERFIL USUARIO                     #
# ======================================================= #
@app.route('/profile')
@login_requerido
def profile():
    conn = get_db_connection()

    usuarios = conn.execute('''
        SELECT U.*, T.Nombre AS Tipo_Usuario, E.Nombre AS Estado_Usuario, C.Nombre AS Ciudad
        FROM Usuarios U
        JOIN Tipos_Usuarios T ON U.ID_tipo_usuario = T.ID_tipo_usuario
        JOIN Estados_Usuarios E ON U.ID_estado_usuario = E.ID_estado_usuario
        JOIN Ciudades C ON U.ID_ciudad = C.ID_ciudad
        WHERE U.ID_usuario = ?
    ''', (session['user_id'],)).fetchone()

    tareas = conn.execute('''
        SELECT T.*, T.Fecha_limite, EST.Descripcion AS Estado
        FROM Tareas T
        JOIN Estados_Tareas EST ON T.ID_estado_tarea = EST.ID_estado_tarea
        WHERE T.ID_creador = ?
    ''', (session['user_id'],)).fetchall()


    conn.close()

    imagen_base64 = None
    if usuarios['FotoPerfil']:
        imagen_base64 = base64.b64encode(usuarios['FotoPerfil']).decode('utf-8')

    return render_template('profile.html', usuarios=usuarios, imagen_base64=imagen_base64, tareas=tareas)

# ======================================================= #
#                    REGISTRAR USUARIO                    #
# ======================================================= #
@app.route('/register', methods=['GET', 'POST'])
def register():
    conn = get_db_connection()
    ciudades = conn.execute('SELECT ID_ciudad, Nombre FROM Ciudades').fetchall()
    conn.close()

    if request.method == 'POST':
        nombre = request.form['name']
        apellido = request.form['apellido']
        identificacion = request.form['identification']
        email = request.form['email']
        direccion = request.form['address']
        telefono = request.form['phone']
        ciudad = request.form['city']
        password = request.form['password']
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        # Manejar la carga de archivos
        id_file = request.files['id_file']
        profile_file = request.files['profile_file']

        # Asegúrate de que los archivos no estén vacíos
        if not id_file or not profile_file:
            print("Se debe subir ambos archivos.")
            return redirect(url_for('register'))

        # Leer el contenido de los archivos
        id_file_data = id_file.read()
        profile_file_data = profile_file.read()

        conn = get_db_connection()
        print(ciudad)
        try:
            conn.execute('''
                INSERT INTO Usuarios (Nombre, Apellido, Correo, Identificacion, Direccion, Telefono, ID_ciudad, ID_tipo_usuario, ID_estado_usuario, Contrasena, FotoPerfil, FotoCedula)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (nombre, apellido, email, identificacion, direccion, telefono, ciudad, 1, 1, hashed_password, profile_file_data, id_file_data))
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f'Error al registrar el usuario: {str(e)}')
            return redirect(url_for('register'))  
        finally:
            conn.close()

        return redirect(url_for('login'))

    return render_template('register.html', ciudades=ciudades)

# ======================================================= #
#                    INICIAR SESIÓN                       #                         
# ======================================================= #
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['correo']
        password = request.form['contrasena']

        conn = get_db_connection()
        usuario = conn.execute('SELECT * FROM Usuarios WHERE Correo = ?', (email,)).fetchone()
        conn.close()

        if usuario is None:
            print('El usuario no existe')
            return redirect(url_for('login'))  

        if bcrypt.check_password_hash(usuario['Contrasena'], password):
            session['user_id'] = usuario['ID_usuario']
            return redirect(url_for('index'))
        else:
            print('Contraseña incorrecta')
            return redirect(url_for('login'))  

    return render_template('login.html')

# ======================================================= #
#                    CERRAR SESIÓN                        #
# ======================================================= #
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
