from flask import Flask, render_template, request, redirect, url_for, session, jsonify, make_response, flash
import sqlite3
from flask_bcrypt import Bcrypt
from functools import wraps
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from functools import wraps
import os
import io
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
#                       SUMAR 5 HORAS                     #
# ======================================================= #
@app.template_filter('sumar_cinco_horas')
def sumar_cinco_horas(value):
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

        local_time = utc_time
        
        dia = local_time.strftime('%d')
        mes = meses[local_time.strftime('%m')]
        año = local_time.strftime('%Y')
        hora = local_time.strftime('%I:%M %p')

        return f"{dia} de {mes} del {año} {hora}"
    return value

# ======================================================= #
#                     VERIFICAR USUARIO                   #
# ======================================================= #
def verificar_usuario_activo(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        usuario_id = session.get('user_id')  # Obtener el ID del usuario de la sesión
        if not usuario_id:
            flash('Debes iniciar sesión primero.', 'danger')
            return redirect(url_for('login'))

        # Llamamos a la función para verificar si el usuario está activo
        conn = get_db_connection()
        estado_usuario = conn.execute(
            'SELECT ID_estado_usuario FROM Usuarios WHERE ID_usuario = ?', 
            (usuario_id,)
        ).fetchone()
        conn.close()
        
        # Verificamos si el usuario está inactivo (por ejemplo, estado 2)
        if estado_usuario and estado_usuario['ID_estado_usuario'] != 1:
            flash('Tu cuenta está inactiva y no puedes acceder a esta sección solo al perfil. Por favor, contacta al administrador.', 'warning')
            return redirect(url_for('index'))  # Redirige al usuario al índice

        return f(*args, **kwargs)
    return decorated_function


# ======================================================= #
#              ACTIVAR O DESACTIVAR USUARIOS              #
# ======================================================= #
@app.route('/toggle_usuario/<int:id_usuario>', methods=['POST'])
@login_requerido
@verificar_usuario_activo
def toggle_usuario(id_usuario):
    conn = get_db_connection()
    
    # Verificar el tipo de usuario y el estado actual
    usuario = conn.execute(
        'SELECT ID_tipo_usuario, ID_estado_usuario FROM Usuarios WHERE ID_usuario = ?', (id_usuario,)
    ).fetchone()
    
    # Solo cambiar estado si es tipo de usuario 1
    if usuario and usuario['ID_tipo_usuario'] == 1:
        nuevo_estado = 2 if usuario['ID_estado_usuario'] == 1 else 1  # Alternar entre Activo (1) e Inactivo (2)
        
        conn.execute(
            'UPDATE Usuarios SET ID_estado_usuario = ? WHERE ID_usuario = ?', (nuevo_estado, id_usuario)
        )
        conn.commit()
    
    conn.close()
    return redirect(url_for('admin'))  # Redirige de vuelta a la página de administración


# ======================================================= #
#                      ADMINISTRADOR                      #
# ======================================================= #
@app.route('/admin')
@login_requerido
@verificar_usuario_activo
def admin():
    conn = get_db_connection()

    imagen_base64 = None
    if 'user_id' in session:
        usuario = conn.execute('SELECT FotoPerfil FROM Usuarios WHERE ID_usuario = ?', (session['user_id'],)).fetchone()
        if usuario and usuario['FotoPerfil']:
            imagen_base64 = base64.b64encode(usuario['FotoPerfil']).decode('utf-8')
    
    is_logged_in = 'user_id' in session
    
    # Consulta SQL que ahora incluye la ciudad y tipo de usuario
    usuarios = conn.execute('''
        SELECT u.ID_usuario, u.Nombre, u.Apellido, u.Correo, u.FotoPerfil, 
               tu.Nombre AS tipo_usuario, eu.Nombre AS estado_usuario, c.Nombre AS ciudad, 
               u.Fecha_creacion, u.ID_tipo_usuario, u.ID_estado_usuario
        FROM Usuarios u
        JOIN Tipos_Usuarios tu ON u.ID_tipo_usuario = tu.ID_tipo_usuario
        JOIN Estados_Usuarios eu ON u.ID_estado_usuario = eu.ID_estado_usuario
        JOIN Ciudades c ON u.ID_ciudad = c.ID_ciudad
    ''').fetchall()
    
    usuario_actual = conn.execute('SELECT Nombre, Apellido FROM Usuarios WHERE ID_usuario = ?', (session['user_id'],)).fetchone()

    # Crear una lista de usuarios con imagenes y los datos necesarios
    usuarios_con_imagenes = []
    for usuario in usuarios:
        usuario_dict = dict(usuario)
        if usuario_dict['FotoPerfil']:
            usuario_dict['FotoPerfil'] = base64.b64encode(usuario_dict['FotoPerfil']).decode('utf-8')
        usuarios_con_imagenes.append(usuario_dict)

    conn.close()
    return render_template('admin.html', usuarios=usuarios_con_imagenes, usuario_actual=usuario_actual, imagen_base64=imagen_base64, is_logged_in=is_logged_in)



# ======================================================= #
#                    REPORTE USUARIOS                     #
# ======================================================= #
@app.route('/reporte_usuarios')
@login_requerido
@verificar_usuario_activo
def reporte_usuarios():
    conn = get_db_connection()
    
    # Consulta SQL que une las tablas Usuarios, Estados_Usuarios, Tipos_Usuarios y Ciudades
    usuarios = conn.execute('''
        SELECT u.ID_usuario, u.Nombre, u.Apellido, u.Correo, tu.Nombre AS tipo_usuario,
               eu.Nombre AS estado_usuario, c.Nombre AS ciudad, u.Fecha_creacion
        FROM Usuarios u
        JOIN Estados_Usuarios eu ON u.ID_estado_usuario = eu.ID_estado_usuario
        JOIN Tipos_Usuarios tu ON u.ID_tipo_usuario = tu.ID_tipo_usuario
        JOIN Ciudades c ON u.ID_ciudad = c.ID_ciudad
    ''').fetchall()

    # Crear un buffer para el PDF
    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=letter)
    
    # Crear una lista para almacenar los elementos del PDF
    elements = []
    styles = getSampleStyleSheet()

    # Título del reporte
    title = Paragraph("Reporte de Usuarios", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 12))

    # Estilos personalizados
    title_style = ParagraphStyle(
        'title_style',
        parent=styles['Heading2'],
        textColor=colors.HexColor('#007bff'),
        fontSize=12,
        spaceAfter=8,
        spaceBefore=8
    )
    label_style = ParagraphStyle(
        'label_style',
        parent=styles['Normal'],
        textColor=colors.HexColor('#007bff'),
        fontSize=10,
        spaceAfter=2,
        spaceBefore=2
    )
    value_style = styles['Normal']

    # Crear una tarjeta para cada usuario
    for usuario in usuarios:
        # Título de la tarjeta de usuario
        elements.append(Paragraph(f"Usuario ID: {usuario['ID_usuario']} - {usuario['Nombre']} {usuario['Apellido']}", title_style))
        
        # Tabla con detalles del usuario
        details_data = [
            [Paragraph("<b>Correo:</b>", label_style), Paragraph(usuario['Correo'], value_style)],
            [Paragraph("<b>Tipo de Usuario:</b>", label_style), Paragraph(usuario['tipo_usuario'], value_style)],
            [Paragraph("<b>Estado:</b>", label_style), Paragraph(usuario['estado_usuario'], value_style)],
            [Paragraph("<b>Ciudad:</b>", label_style), Paragraph(usuario['ciudad'], value_style)],
            [Paragraph("<b>Fecha de Creación:</b>", label_style), Paragraph(str(usuario['Fecha_creacion']), value_style)],
        ]

        # Crear la tabla de detalles con estilo
        details_table = Table(details_data, colWidths=[120, 250])
        details_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e0f7fa')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#007bff')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(details_table)
        
        # Separador entre usuarios
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("<br/>", styles['Normal']))
        elements.append(Spacer(1, 24))

    # Generar el PDF
    pdf.build(elements)

    # Regresar al cliente como un archivo PDF
    buffer.seek(0)
    response = make_response(buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=Reporte de usuarios.pdf'
    
    return response


# ======================================================= #
#                      REPORTE TAREAS                     #
# ======================================================= #
@app.route('/reporte_tareas')
@login_requerido
@verificar_usuario_activo
def reporte_tareas():
    conn = get_db_connection()
    
    # Consulta SQL que une las tablas Tareas, Estados_Tareas, Categorias y Usuarios
    tareas = conn.execute('''
        SELECT t.ID_tarea, t.Titulo, t.Descripcion, t.Fecha_creacion, t.Fecha_limite, 
            t.Fecha_finalizacion, t.Valor, r.Calificacion, et.Descripcion AS estado_tarea, 
            c.Nombre AS categoria, uc.Nombre || ' ' || uc.Apellido AS creador, 
            ut.Nombre || ' ' || ut.Apellido AS trabajador
        FROM Tareas t
        JOIN Estados_Tareas et ON t.ID_estado_tarea = et.ID_estado_tarea
        JOIN Categorias c ON t.ID_categoria = c.ID_categoria
        JOIN Usuarios uc ON t.ID_creador = uc.ID_usuario
        LEFT JOIN Usuarios ut ON t.ID_trabajador = ut.ID_usuario
        LEFT JOIN Reseñas r ON t.ID_tarea = r.ID_tarea  -- Añadimos LEFT JOIN para obtener calificaciones
    ''').fetchall()

    # Crear un buffer para el PDF
    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=letter)
    
    # Crear una lista para almacenar los elementos del PDF
    elements = []
    styles = getSampleStyleSheet()

    # Título del reporte
    title = Paragraph("Reporte de Tareas", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 12))

    # Estilos personalizados
    title_style = ParagraphStyle(
        'title_style',
        parent=styles['Heading2'],
        textColor=colors.HexColor('#007bff'),
        fontSize=12,
        spaceAfter=8,
        spaceBefore=8
    )
    label_style = ParagraphStyle(
        'label_style',
        parent=styles['Normal'],
        textColor=colors.HexColor('#007bff'),
        fontSize=10,
        spaceAfter=2,
        spaceBefore=2
    )
    value_style = styles['Normal']

    # Crear una tarjeta para cada tarea
    for tarea in tareas:
        # Título de la tarea
        elements.append(Paragraph(f"Tarea ID: {tarea['ID_tarea']} - {tarea['Titulo']}", title_style))
        
        # Tabla con detalles de la tarea
        details_data = [
            [Paragraph("<b>Estado:</b>", label_style), Paragraph(tarea['estado_tarea'], value_style)],
            [Paragraph("<b>Categoría:</b>", label_style), Paragraph(tarea['categoria'], value_style)],
            [Paragraph("<b>Fecha de Creación:</b>", label_style), Paragraph(str(tarea['Fecha_creacion']), value_style)],
            [Paragraph("<b>Fecha Límite:</b>", label_style), Paragraph(str(tarea['Fecha_limite']), value_style)],
            [Paragraph("<b>Fecha de Finalización:</b>", label_style), Paragraph(str(tarea['Fecha_finalizacion']), value_style)],
            [Paragraph("<b>Valor:</b>", label_style), Paragraph(f"{tarea['Valor']:.2f}", value_style)],
            [Paragraph("<b>Calificación:</b>", label_style), Paragraph(str(tarea['Calificacion']), value_style)],
            [Paragraph("<b>Creador:</b>", label_style), Paragraph(tarea['creador'], value_style)],
            [Paragraph("<b>Trabajador:</b>", label_style), Paragraph(tarea['trabajador'] if tarea['trabajador'] else 'No asignado', value_style)],
        ]

        # Crear la tabla de detalles con estilo
        details_table = Table(details_data, colWidths=[100, 300])
        details_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e0f7fa')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#007bff')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(details_table)
        
        # Espacio antes de la descripción
        elements.append(Spacer(1, 8))

        # Descripción de la tarea
        elements.append(Paragraph("<b>Descripción:</b>", label_style))
        elements.append(Paragraph(tarea['Descripcion'], value_style))

        # Separador entre tareas
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("<br/>", styles['Normal']))
        elements.append(Spacer(1, 24))

    # Generar el PDF
    pdf.build(elements)

    # Regresar al cliente como un archivo PDF
    buffer.seek(0)
    response = make_response(buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=Reporte de tareas.pdf'
    
    return response

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
@verificar_usuario_activo
def calificar_tarea(tarea_id):
    calificacion = request.form['calificacion']
    contenido_reseña = request.form.get('contenido', '')  # Texto opcional de la reseña
    usuario_actual = session['user_id']
    conn = get_db_connection()

    # Verificar si el usuario es el creador de la tarea y si ya está calificada en la tabla de Reseñas
    tarea = conn.execute('SELECT ID_creador FROM Tareas WHERE ID_tarea = ?', (tarea_id,)).fetchone()
    reseña_existente = conn.execute('SELECT 1 FROM Reseñas WHERE ID_tarea = ?', (tarea_id,)).fetchone()

    if tarea is None:
        conn.close()
        return jsonify({'success': False, 'error': 'La tarea no existe.'})

    if tarea['ID_creador'] != usuario_actual:
        conn.close()
        return jsonify({'success': False, 'error': 'Solo el creador de la tarea puede calificarla.'})

    if reseña_existente:
        conn.close()
        return jsonify({'success': False, 'error': 'Esta tarea ya ha sido calificada.'})

    # Guardar la reseña en la base de datos
    conn.execute(
        'INSERT INTO Reseñas (ID_tarea, Contenido, Calificacion) VALUES (?, ?, ?)',
        (tarea_id, contenido_reseña, calificacion)
    )
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': 'Calificación registrada exitosamente.'})





# ======================================================= #
#                      LISTA DE TAREAS                    #
# ======================================================= #
@app.route('/tareas')
@login_requerido
@verificar_usuario_activo
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
               R.Calificacion  -- Cambiamos de T.Calificacion a R.Calificacion
        FROM Tareas T
        JOIN Categorias C ON T.ID_categoria = C.ID_categoria
        JOIN Estados_Tareas ET ON T.ID_estado_tarea = ET.ID_estado_tarea
        LEFT JOIN Usuarios U1 ON T.ID_creador = U1.ID_usuario
        LEFT JOIN Usuarios U2 ON T.ID_trabajador = U2.ID_usuario
        LEFT JOIN Reseñas R ON T.ID_tarea = R.ID_tarea  -- Añadimos un LEFT JOIN para las reseñas
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
@verificar_usuario_activo
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
@verificar_usuario_activo
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
@verificar_usuario_activo
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
@verificar_usuario_activo
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
        
        # Insertar la nueva tarea en la tabla Tareas
        conn.execute('''
            INSERT INTO Tareas (Titulo, Descripcion, Fecha_limite, Valor, Adjuntos, ID_estado_tarea, ID_categoria, ID_creador, ID_trabajador)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (titulo, descripcion, fecha_limite, valor, adjunto, estado, categoria, session['user_id'], None))
        
        # Obtener el ID de la tarea recién creada
        tarea_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        # Obtener todos los trabajadores para enviarles una notificación
        trabajadores = conn.execute('SELECT ID_usuario FROM Usuarios WHERE ID_usuario != ?', (session['user_id'],)).fetchall()

        # Insertar notificaciones para cada trabajador
        for trabajador in trabajadores:
            conn.execute('INSERT INTO Notificaciones (usuario_id, tarea_id) VALUES (?, ?)', (trabajador['ID_usuario'], tarea_id))
        
        conn.commit()
        conn.close()
        
        return redirect(url_for('tareas'))
    
    return render_template('agregar_solicitud.html', usuarios=usuarios, categorias=categorias, imagen_base64=imagen_base64, is_logged_in=is_logged_in)

# ======================================================= #
#                      NOTIFICACIONES                     #
# ======================================================= #
@app.route('/notificaciones')
@login_requerido
def notificaciones():
    try:
        usuario_actual = session['user_id']
        conn = get_db_connection()

        # Obtener las notificaciones no notificadas junto con el título y el valor de la tarea
        notificaciones = conn.execute('''
            SELECT N.id, N.usuario_id, N.tarea_id, N.notificado, T.Titulo, T.Valor
            FROM Notificaciones N
            JOIN Tareas T ON N.tarea_id = T.ID_tarea
            WHERE N.usuario_id = ? AND N.notificado = FALSE
        ''', (usuario_actual,)).fetchall()

        print(notificaciones)  # Para verificar qué datos se obtienen

        # Marcar las notificaciones como notificadas
        if notificaciones:
            conn.execute('UPDATE Notificaciones SET notificado = TRUE WHERE usuario_id = ?', (usuario_actual,))
            conn.commit()

        conn.close()

        # Convertir las notificaciones a formato JSON, incluyendo el título y el valor de la tarea
        return jsonify([{
            "id": notification["id"],
            "usuario_id": notification["usuario_id"],
            "tarea_id": notification["tarea_id"],
            "notificado": notification["notificado"],
            "Titulo": notification["Titulo"],
            "Valor": notification["Valor"]  # Incluye el valor de la tarea
        } for notification in notificaciones])

    except Exception as e:
        print(f"Error en la ruta /notificaciones: {e}")
        return jsonify({"error": str(e)}), 500


# ======================================================= #
#                      EDITAR PERFIL                      #
# ======================================================= #
@app.route('/editar_perfil', methods=['GET'])
@login_requerido
@verificar_usuario_activo
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
@verificar_usuario_activo
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
@verificar_usuario_activo
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
@app.route('/profile', methods=['GET'])
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

    # Paginación de tareas
    page = request.args.get('page', 1, type=int)
    per_page = 2  # Número de tareas por página
    offset = (page - 1) * per_page

    tareas = conn.execute('''
        SELECT T.*, T.Fecha_limite, EST.Descripcion AS Estado
        FROM Tareas T
        JOIN Estados_Tareas EST ON T.ID_estado_tarea = EST.ID_estado_tarea
        WHERE T.ID_creador = ?
        LIMIT ? OFFSET ?
    ''', (session['user_id'], per_page, offset)).fetchall()

    total_tareas = conn.execute('''
        SELECT COUNT(*) FROM Tareas WHERE ID_creador = ?
    ''', (session['user_id'],)).fetchone()[0]

    # Paginación de reseñas
    review_page = request.args.get('review_page', 1, type=int)
    reviews_per_page = 2  # Número de reseñas por página
    review_offset = (review_page - 1) * reviews_per_page

    # Obtener las reseñas de las tareas creadas por el usuario
    reseñas = conn.execute('''
        SELECT R.*, U.Nombre AS Nombre_Usuario, U.Apellido AS Apellido_Usuario, R.Fecha AS Fecha, T.Titulo AS Titulo_Tarea
        FROM Reseñas R
        JOIN Tareas T ON R.ID_tarea = T.ID_tarea
        JOIN Usuarios U ON T.ID_creador = U.ID_usuario
        WHERE T.ID_trabajador = ?
        LIMIT ? OFFSET ?
    ''', (session['user_id'], reviews_per_page, review_offset)).fetchall()

    total_reseñas = conn.execute('''
        SELECT COUNT(*) FROM Reseñas R
        JOIN Tareas T ON R.ID_tarea = T.ID_tarea
        WHERE T.ID_trabajador = ?
    ''', (session['user_id'],)).fetchone()[0]

    conn.close()

    imagen_base64 = None
    if usuarios['FotoPerfil']:
        imagen_base64 = base64.b64encode(usuarios['FotoPerfil']).decode('utf-8')

    return render_template('profile.html', usuarios=usuarios, imagen_base64=imagen_base64, tareas=tareas,
                           page=page, total_tareas=total_tareas, per_page=per_page, reseñas=reseñas,
                           review_page=review_page, total_reseñas=total_reseñas, reviews_per_page=reviews_per_page)



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
            return jsonify({'error': 'Se debe subir ambos archivos.'}), 400

        # Leer el contenido de los archivos
        id_file_data = id_file.read()
        profile_file_data = profile_file.read()

        conn = get_db_connection()
        try:
            # Verificar si la cédula ya existe
            existing_user = conn.execute('SELECT Identificacion FROM Usuarios WHERE Identificacion = ?', 
                                      (identificacion,)).fetchone()
            if existing_user:
                return jsonify({'error': 'La cédula ingresada ya está registrada en el sistema'}), 409

            conn.execute('''
                INSERT INTO Usuarios (Nombre, Apellido, Correo, Identificacion, Direccion, Telefono, 
                                    ID_ciudad, ID_tipo_usuario, ID_estado_usuario, Contrasena, 
                                    FotoPerfil, FotoCedula)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (nombre, apellido, email, identificacion, direccion, telefono, ciudad, 
                 1, 1, hashed_password, profile_file_data, id_file_data))
            conn.commit()
            return jsonify({'success': 'Usuario registrado exitosamente'}), 200
        except sqlite3.IntegrityError as e:
            conn.rollback()
            if "Identificacion" in str(e):
                return jsonify({'error': 'La cédula ingresada ya está registrada en el sistema'}), 409
            elif "Correo" in str(e):
                return jsonify({'error': 'El correo electrónico ya está registrado'}), 409
            return jsonify({'error': 'Error al registrar el usuario'}), 400
        except Exception as e:
            conn.rollback()
            return jsonify({'error': 'Error al registrar el usuario'}), 400
        finally:
            conn.close()

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
