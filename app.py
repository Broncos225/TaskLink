from flask import Flask, render_template, request, redirect, url_for, session, jsonify, make_response, flash
import sqlite3
from flask_bcrypt import Bcrypt
from functools import wraps
from abc import ABC, abstractmethod
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from functools import wraps
import os
import re
import io
import base64
import threading
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'mi_secreto'
bcrypt = Bcrypt(app)

# ======================================================= #
#               SINGLETON DATABASE MANAGER                #
# ======================================================= #
class DatabaseManager:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance
    
    def get_connection(self):
        """Retorna una nueva conexión para cada llamada"""
        conn = sqlite3.connect('TaskLink.db')
        conn.row_factory = sqlite3.Row
        return conn

# Variable global del singleton
db_manager = DatabaseManager()

# ======================================================= #
#          TEMPLATE METHOD: GENERADOR DE REPORTES         #
# ======================================================= #
class ReportGenerator(ABC):
    def __init__(self):
        self.buffer = io.BytesIO()
        self.pdf = SimpleDocTemplate(self.buffer, pagesize=letter)
        self.elements = []
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Configurar estilos personalizados comunes"""
        self.title_style = ParagraphStyle(
            'title_style',
            parent=self.styles['Heading2'],
            textColor=colors.HexColor('#007bff'),
            fontSize=12,
            spaceAfter=8,
            spaceBefore=8
        )
        self.label_style = ParagraphStyle(
            'label_style',
            parent=self.styles['Normal'],
            textColor=colors.HexColor('#007bff'),
            fontSize=10,
            spaceAfter=2,
            spaceBefore=2
        )
        self.value_style = self.styles['Normal']
    
    @abstractmethod
    def get_data(self, conn):
        """Método abstracto para obtener datos específicos"""
        pass
    
    @abstractmethod
    def get_title(self):
        """Método abstracto para obtener el título del reporte"""
        pass
    
    @abstractmethod
    def create_content(self, data):
        """Método abstracto para crear el contenido específico del reporte"""
        pass
    
    def generate_report(self, conn):
        """Método template que genera el reporte completo"""
        # Título
        title = Paragraph(self.get_title(), self.styles['Title'])
        self.elements.append(title)
        self.elements.append(Spacer(1, 12))
        
        # Obtener datos y crear contenido
        data = self.get_data(conn)
        self.create_content(data)
        
        # Generar PDF
        self.pdf.build(self.elements)
        self.buffer.seek(0)
        return self.buffer

# ======================================================= #
#             IMPLEMENTACIONES DE REPORTES                #
# ======================================================= #
class UserReportGenerator(ReportGenerator):
    def get_data(self, conn):
        return conn.execute('''
            SELECT u.ID_usuario, u.Nombre, u.Apellido, u.Correo, tu.Nombre AS tipo_usuario,
                   eu.Nombre AS estado_usuario, c.Nombre AS ciudad, u.Fecha_creacion
            FROM Usuarios u
            JOIN Estados_Usuarios eu ON u.ID_estado_usuario = eu.ID_estado_usuario
            JOIN Tipos_Usuarios tu ON u.ID_tipo_usuario = tu.ID_tipo_usuario
            JOIN Ciudades c ON u.ID_ciudad = c.ID_ciudad
        ''').fetchall()
    
    def get_title(self):
        return "Reporte de Usuarios"
    
    def create_content(self, usuarios):
        for usuario in usuarios:
            # Título de la tarjeta de usuario
            self.elements.append(Paragraph(f"Usuario ID: {usuario['ID_usuario']} - {usuario['Nombre']} {usuario['Apellido']}", self.title_style))
            
            # Tabla con detalles del usuario
            details_data = [
                [Paragraph("<b>Correo:</b>", self.label_style), Paragraph(usuario['Correo'], self.value_style)],
                [Paragraph("<b>Tipo de Usuario:</b>", self.label_style), Paragraph(usuario['tipo_usuario'], self.value_style)],
                [Paragraph("<b>Estado:</b>", self.label_style), Paragraph(usuario['estado_usuario'], self.value_style)],
                [Paragraph("<b>Ciudad:</b>", self.label_style), Paragraph(usuario['ciudad'], self.value_style)],
                [Paragraph("<b>Fecha de Creación:</b>", self.label_style), Paragraph(str(usuario['Fecha_creacion']), self.value_style)],
            ]
            
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
            self.elements.append(details_table)
            self.elements.append(Spacer(1, 12))
            self.elements.append(Paragraph("<br/>", self.styles['Normal']))
            self.elements.append(Spacer(1, 24))

# Implementación concreta para reporte de tareas
class TaskReportGenerator(ReportGenerator):
    def get_data(self, conn):
        return conn.execute('''
            SELECT t.ID_tarea, t.Titulo, t.Descripcion, t.Fecha_creacion, t.Fecha_limite, 
                t.Fecha_finalizacion, t.Valor, r.Calificacion, et.Descripcion AS estado_tarea, 
                c.Nombre AS categoria, uc.Nombre || ' ' || uc.Apellido AS creador, 
                ut.Nombre || ' ' || ut.Apellido AS trabajador
            FROM Tareas t
            JOIN Estados_Tareas et ON t.ID_estado_tarea = et.ID_estado_tarea
            JOIN Categorias c ON t.ID_categoria = c.ID_categoria
            JOIN Usuarios uc ON t.ID_creador = uc.ID_usuario
            LEFT JOIN Usuarios ut ON t.ID_trabajador = ut.ID_usuario
            LEFT JOIN Reseñas r ON t.ID_tarea = r.ID_tarea
        ''').fetchall()
    
    def get_title(self):
        return "Reporte de Tareas"
    
    def create_content(self, tareas):
        for tarea in tareas:
            # Título de la tarea
            self.elements.append(Paragraph(f"Tarea ID: {tarea['ID_tarea']} - {tarea['Titulo']}", self.title_style))
            
            # Tabla con detalles de la tarea
            details_data = [
                [Paragraph("<b>Estado:</b>", self.label_style), Paragraph(tarea['estado_tarea'], self.value_style)],
                [Paragraph("<b>Categoría:</b>", self.label_style), Paragraph(tarea['categoria'], self.value_style)],
                [Paragraph("<b>Fecha de Creación:</b>", self.label_style), Paragraph(str(tarea['Fecha_creacion']), self.value_style)],
                [Paragraph("<b>Fecha Límite:</b>", self.label_style), Paragraph(str(tarea['Fecha_limite']), self.value_style)],
                [Paragraph("<b>Fecha de Finalización:</b>", self.label_style), Paragraph(str(tarea['Fecha_finalizacion']), self.value_style)],
                [Paragraph("<b>Valor:</b>", self.label_style), Paragraph(f"{tarea['Valor']:.2f}", self.value_style)],
                [Paragraph("<b>Calificación:</b>", self.label_style), Paragraph(str(tarea['Calificacion']), self.value_style)],
                [Paragraph("<b>Creador:</b>", self.label_style), Paragraph(tarea['creador'], self.value_style)],
                [Paragraph("<b>Trabajador:</b>", self.label_style), Paragraph(tarea['trabajador'] if tarea['trabajador'] else 'No asignado', self.value_style)],
            ]
            
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
            self.elements.append(details_table)
            self.elements.append(Spacer(1, 8))
            
            # Descripción de la tarea
            self.elements.append(Paragraph("<b>Descripción:</b>", self.label_style))
            self.elements.append(Paragraph(tarea['Descripcion'], self.value_style))
            self.elements.append(Spacer(1, 12))
            self.elements.append(Paragraph("<br/>", self.styles['Normal']))
            self.elements.append(Spacer(1, 24))

# ======================================================= #
#              FACTORY METHOD: REPORTES                   #
# ======================================================= #
class ReportFactory:
    @staticmethod
    def create_report(report_type):
        if report_type == 'usuarios':
            return UserReportGenerator()
        elif report_type == 'tareas':
            return TaskReportGenerator()
        else:
            raise ValueError(f"Tipo de reporte no soportado: {report_type}")
    
    @staticmethod
    def generate_report(report_type, conn):
        """Método de conveniencia para crear y generar reporte en un solo paso"""
        report_generator = ReportFactory.create_report(report_type)
        return report_generator.generate_report(conn)

from abc import ABC, abstractmethod

# ======================================================= #
#              PATRÓN OBSERVER (INTERFACES)               #
# ======================================================= #
class Observer(ABC):
    @abstractmethod
    def update(self, tarea_id, titulo, valor):
        pass

# Interfaz Subject
class Subject(ABC):
    @abstractmethod
    def attach(self, observer):
        pass
    
    @abstractmethod
    def detach(self, observer):
        pass
    
    @abstractmethod
    def notify(self, tarea_id, titulo, valor):
        pass

# ======================================================= #
#            SISTEMA DE NOTIFICACIONES (OBSERVER)         #
# ======================================================= #
class UserNotificationObserver(Observer):
    def __init__(self, usuario_id):
        self.usuario_id = usuario_id
    
    def update(self, tarea_id, titulo, valor):
        """Almacenar datos para inserción posterior"""
        self.tarea_id = tarea_id
        self.titulo = titulo
        self.valor = valor
        print(f"Observer preparado para usuario {self.usuario_id} - tarea '{titulo}' con valor ${valor}")

# Subject concreto - Notificador de tareas
class TaskNotificationSubject(Subject):
    def __init__(self):
        self._observers = []
    
    def attach(self, observer):
        """Agregar un observer a la lista"""
        if observer not in self._observers:
            self._observers.append(observer)
    
    def detach(self, observer):
        """Remover un observer de la lista"""
        if observer in self._observers:
            self._observers.remove(observer)
    
    def notify(self, tarea_id, titulo, valor):
        """Notificar a todos los observers registrados"""
        print(f"Notificando nueva tarea: {titulo}")
        for observer in self._observers:
            observer.update(tarea_id, titulo, valor)
    
    def notify_and_save(self, tarea_id, titulo, valor, conn):
        """Notificar y guardar todas las notificaciones usando una sola conexión"""
        print(f"Notificando nueva tarea: {titulo}")
        
        # Notificar a todos los observers
        for observer in self._observers:
            observer.update(tarea_id, titulo, valor)
        
        # Insertar todas las notificaciones usando la conexión existente
        for observer in self._observers:
            conn.execute(
                'INSERT INTO Notificaciones (usuario_id, tarea_id) VALUES (?, ?)', 
                (observer.usuario_id, tarea_id)
            )
    
    def load_active_users_as_observers(self, exclude_user_id, conn):
        """Cargar todos los usuarios activos como observers (excepto el creador)"""
        self._observers.clear()  # Limpiar observers anteriores
        
        # Obtener usuarios activos excluyendo al creador de la tarea
        usuarios = conn.execute(
            'SELECT ID_usuario FROM Usuarios WHERE ID_usuario != ? AND ID_estado_usuario = 1', 
            (exclude_user_id,)
        ).fetchall()
        
        # Crear observers para cada usuario activo
        for usuario in usuarios:
            user_observer = UserNotificationObserver(usuario['ID_usuario'])
            self.attach(user_observer)
        
        print(f"Cargados {len(self._observers)} usuarios como observers")

# Instancia global del notificador (singleton-like)
task_notifier = None

def get_task_notifier():
    """Obtener la instancia del notificador de tareas"""
    global task_notifier
    if task_notifier is None:
        task_notifier = TaskNotificationSubject()
    return task_notifier

# ======================================================= #
#             STRATEGY: FILTRADO DE TAREAS                #
# ======================================================= #
class TaskFilterStrategy(ABC):
    @abstractmethod
    def apply_filter(self, conditions, params, filter_value):
        """Aplica el filtro específico a las condiciones y parámetros"""
        pass

# ======================================================= #
#             STRATEGY: ORDENAMIENTO TAREAS               #
# ======================================================= #
class TaskSortStrategy(ABC):
    @abstractmethod
    def get_order_clause(self, sort_order):
        """Retorna la cláusula ORDER BY específica"""
        pass

# Estrategias concretas de filtrado
class CategoryFilterStrategy(TaskFilterStrategy):
    def apply_filter(self, conditions, params, filter_value):
        if filter_value:
            conditions.append('T.ID_categoria = ?')
            params.append(filter_value)

class StatusFilterStrategy(TaskFilterStrategy):
    def apply_filter(self, conditions, params, filter_value):
        if filter_value:
            conditions.append('T.ID_estado_tarea = ?')
            params.append(filter_value)

# Estrategias concretas de ordenamiento
class TitleSortStrategy(TaskSortStrategy):
    def get_order_clause(self, sort_order):
        return f'ORDER BY T.Titulo {sort_order}'

class DateSortStrategy(TaskSortStrategy):
    def get_order_clause(self, sort_order):
        return f'ORDER BY T.Fecha_creacion {sort_order}'

class ValueSortStrategy(TaskSortStrategy):
    def get_order_clause(self, sort_order):
        return f'ORDER BY T.Valor {sort_order}'

# ======================================================= #
#             CONTEXTO Y CONSTRUCTOR DE QUERIES           #
# ======================================================= #
class TaskQueryBuilder:
    def __init__(self):
        self.base_query = '''
            SELECT T.*, 
                   C.Nombre AS Categoria, 
                   ET.Descripcion AS Estado, 
                   U1.Nombre AS CreadorNombre, 
                   U1.Apellido AS CreadorApellido, 
                   U2.Nombre AS TrabajadorNombre, 
                   U2.Apellido AS TrabajadorApellido,
                   R.Calificacion
            FROM Tareas T
            JOIN Categorias C ON T.ID_categoria = C.ID_categoria
            JOIN Estados_Tareas ET ON T.ID_estado_tarea = ET.ID_estado_tarea
            LEFT JOIN Usuarios U1 ON T.ID_creador = U1.ID_usuario
            LEFT JOIN Usuarios U2 ON T.ID_trabajador = U2.ID_usuario
            LEFT JOIN Reseñas R ON T.ID_tarea = R.ID_tarea
        '''
        
        # Diccionario de estrategias de filtrado disponibles
        self.filter_strategies = {
            'category': CategoryFilterStrategy(),
            'status': StatusFilterStrategy()
        }
        
        # Diccionario de estrategias de ordenamiento disponibles
        self.sort_strategies = {
            'titulo': TitleSortStrategy(),
            'fecha': DateSortStrategy(),
            'valor': ValueSortStrategy()
        }
    
    def build_query(self, filters, sort_by='titulo', sort_order='asc'):
        """
        Construye la consulta SQL usando las estrategias
        
        Args:
            filters: dict con los filtros {'category': valor, 'status': valor}
            sort_by: str con el criterio de ordenamiento
            sort_order: str con el orden (asc/desc)
        """
        conditions = []
        params = []
        
        # Aplicar estrategias de filtrado
        for filter_name, filter_value in filters.items():
            if filter_name in self.filter_strategies:
                strategy = self.filter_strategies[filter_name]
                strategy.apply_filter(conditions, params, filter_value)
        
        # Construir query con condiciones
        query = self.base_query
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
        
        # Aplicar estrategia de ordenamiento
        if sort_by in self.sort_strategies:
            sort_strategy = self.sort_strategies[sort_by]
            query += f' {sort_strategy.get_order_clause(sort_order)}'
        else:
            # Fallback al ordenamiento por defecto
            query += f' ORDER BY T.Titulo {sort_order}'
        
        return query, params

# Instancia global del query builder
task_query_builder = TaskQueryBuilder()

# ======================================================= #
#              PATRÓN DECORATOR (PROCESAMIENTO)           #
# ======================================================= #
class DataProcessor(ABC):
    @abstractmethod
    def process(self, data):
        pass

# Componente concreto básico
class BaseDataProcessor(DataProcessor):
    def process(self, data):
        return data

# Decorator base
class DataProcessorDecorator(DataProcessor):
    def __init__(self, processor):
        self._processor = processor
    
    def process(self, data):
        return self._processor.process(data)

# ======================================================= #
#              DECORADORES DE VALIDACIÓN                  #
# ======================================================= #
class EmailValidatorDecorator(DataProcessorDecorator):
    def process(self, data):
        data = super().process(data)
        if 'email' in data:
            email = data['email']
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                data['errors'] = data.get('errors', [])
                data['errors'].append('El formato del correo electrónico no es válido')
        return data

class PhoneValidatorDecorator(DataProcessorDecorator):
    def process(self, data):
        data = super().process(data)
        if 'phone' in data:
            phone = data['phone']
            # Validar que solo contenga números, espacios, guiones y paréntesis
            phone_pattern = r'^[\d\s\-\(\)]+$'
            if not re.match(phone_pattern, phone) or len(phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')) < 7:
                data['errors'] = data.get('errors', [])
                data['errors'].append('El número de teléfono no es válido')
        return data

class RequiredFieldsDecorator(DataProcessorDecorator):
    def __init__(self, processor, required_fields):
        super().__init__(processor)
        self.required_fields = required_fields
    
    def process(self, data):
        data = super().process(data)
        for field in self.required_fields:
            if field not in data or not data[field] or str(data[field]).strip() == '':
                data['errors'] = data.get('errors', [])
                data['errors'].append(f'El campo {field} es requerido')
        return data

class IdentificationValidatorDecorator(DataProcessorDecorator):
    def process(self, data):
        data = super().process(data)
        if 'identification' in data:
            identification = str(data['identification']).strip()
            # Validar que tenga entre 6 y 15 dígitos
            if not identification.isdigit() or len(identification) < 6 or len(identification) > 15:
                data['errors'] = data.get('errors', [])
                data['errors'].append('La identificación debe contener entre 6 y 15 dígitos')
        return data

# ======================================================= #
#               DECORADOR DE FORMATO DATOS                #
# ======================================================= #
class DataFormatterDecorator(DataProcessorDecorator):
    def process(self, data):
        data = super().process(data)
        # Formatear strings: trim y capitalizar nombres
        if 'name' in data:
            data['name'] = data['name'].strip().title()
        if 'apellido' in data:
            data['apellido'] = data['apellido'].strip().title()
        if 'email' in data:
            data['email'] = data['email'].strip().lower()
        if 'phone' in data:
            # Limpiar teléfono de caracteres especiales para almacenamiento
            phone_clean = re.sub(r'[\s\-\(\)]', '', data['phone'])
            data['phone_formatted'] = phone_clean
        return data

# ======================================================= #
#             FACTORY DE PROCESADORES DE DATOS            #
# ======================================================= #
class UserDataProcessorFactory:
    @staticmethod
    def create_registration_processor():
        """Crear procesador para registro de usuario"""
        processor = BaseDataProcessor()
        
        # Aplicar decoradores en orden
        required_fields = ['name', 'apellido', 'identification', 'email', 'address', 'phone', 'city', 'password']
        processor = RequiredFieldsDecorator(processor, required_fields)
        processor = EmailValidatorDecorator(processor)
        processor = PhoneValidatorDecorator(processor)
        processor = IdentificationValidatorDecorator(processor)
        processor = DataFormatterDecorator(processor)
        
        return processor
    
    @staticmethod
    def create_profile_update_processor():
        """Crear procesador para actualización de perfil"""
        processor = BaseDataProcessor()
        
        required_fields = ['nombre', 'apellido', 'correo', 'identificacion', 'direccion', 'telefono', 'ciudad']
        processor = RequiredFieldsDecorator(processor, required_fields)
        processor = EmailValidatorDecorator(processor)
        processor = PhoneValidatorDecorator(processor)
        processor = IdentificationValidatorDecorator(processor)
        processor = DataFormatterDecorator(processor)
        
        return processor

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
        conn = db_manager.get_connection()
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
    conn = db_manager.get_connection()

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
    conn = db_manager.get_connection()

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
    conn = db_manager.get_connection()
    
    # Genera el reporte usando Factory Method
    buffer = ReportFactory.generate_report('usuarios', conn)
    
    conn.close()
    
    # Retornar respuesta
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
    conn = db_manager.get_connection()
    
    # Genera el reporte usando Factory Method
    buffer = ReportFactory.generate_report('tareas', conn)
    
    conn.close()
    
    # Retornar respuesta
    response = make_response(buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=Reporte de tareas.pdf'
    return response

# ======================================================= #
#                      INICIO                             #
# ======================================================= #
@app.route('/')
def index():
    conn = db_manager.get_connection()
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
    conn = db_manager.get_connection()

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
    conn = db_manager.get_connection()
    
    # Obtener parámetros de filtrado (mantenemos los mismos nombres)
    categoria_filtro = int(request.args.get('categoria', '')) if request.args.get('categoria', '').isdigit() else ''
    estado_filtro = int(request.args.get('estado', '')) if request.args.get('estado', '').isdigit() else ''
    orden = request.args.get('orden', 'asc')
    sort_by = request.args.get('sort_by', 'titulo')  # Nuevo parámetro opcional
    
    # Validar orden
    if orden not in ['asc', 'desc']:
        orden = 'asc'
    
    # Preparar filtros para las estrategias
    filters = {
        'category': categoria_filtro,
        'status': estado_filtro
    }
    
    # Usar el patrón Strategy para construir la consulta
    query, params = task_query_builder.build_query(filters, sort_by, orden)
    
    # Ejecutar la consulta
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
    conn = db_manager.get_connection()
    
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
    conn = db_manager.get_connection()
    
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
    conn = db_manager.get_connection()
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
    conn = db_manager.get_connection()
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
        
        conn = db_manager.get_connection()
        
        # Insertar la nueva tarea en la tabla Tareas
        conn.execute('''
            INSERT INTO Tareas (Titulo, Descripcion, Fecha_limite, Valor, Adjuntos, ID_estado_tarea, ID_categoria, ID_creador, ID_trabajador)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (titulo, descripcion, fecha_limite, valor, adjunto, estado, categoria, session['user_id'], None))
        
        # Obtener el ID de la tarea recién creada
        tarea_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        # Obtener el notificador y configurar observers
        notifier = get_task_notifier()
        notifier.load_active_users_as_observers(session['user_id'], conn)
        
        # Notificar y guardar usando la misma conexión
        notifier.notify_and_save(tarea_id, titulo, valor, conn)
        
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
        conn = db_manager.get_connection()

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
    conn = db_manager.get_connection()
    ciudades = conn.execute('SELECT ID_ciudad, Nombre FROM Ciudades').fetchall()
    conn.close()
    conn = db_manager.get_connection()
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
    # Preparar datos para el procesador
    profile_data = {
        'nombre': request.form.get('nombre', ''),
        'apellido': request.form.get('apellido', ''),
        'correo': request.form.get('correo', ''),
        'identificacion': request.form.get('identificacion', ''),
        'direccion': request.form.get('direccion', ''),
        'telefono': request.form.get('telefono', ''),
        'ciudad': request.form.get('ciudad', '')
    }
    
    # Crear procesador y validar datos
    processor = UserDataProcessorFactory.create_profile_update_processor()
    processed_data = processor.process(profile_data)
    
    # Verificar errores de validación
    if 'errors' in processed_data:
        flash('; '.join(processed_data['errors']), 'danger')
        return redirect(url_for('editar_perfil'))
    
    # Usar datos procesados
    nombre = processed_data['nombre']
    apellido = processed_data['apellido']
    correo = processed_data['correo']
    identificacion = processed_data['identificacion']
    direccion = processed_data['direccion']
    telefono = processed_data.get('telefono_formatted', processed_data['telefono'])
    ciudad = processed_data['ciudad']
    
    conn = db_manager.get_connection()
    try:
        conn.execute('''
            UPDATE Usuarios
            SET Nombre = ?, Apellido = ?, Correo = ?, Identificacion = ?, Direccion = ?, Telefono = ?, ID_ciudad = ?
            WHERE ID_usuario = ?
        ''', (nombre, apellido, correo, identificacion, direccion, telefono, ciudad, session['user_id']))
        
        conn.commit()
        flash('Perfil actualizado correctamente', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error al actualizar el perfil: {str(e)}', 'danger')
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

    conn = db_manager.get_connection()
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
    conn = db_manager.get_connection()
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
    conn = db_manager.get_connection()
    ciudades = conn.execute('SELECT ID_ciudad, Nombre FROM Ciudades').fetchall()
    conn.close()

    if request.method == 'POST':
        # Preparar datos para el procesador
        user_data = {
            'name': request.form.get('name', ''),
            'apellido': request.form.get('apellido', ''),
            'identification': request.form.get('identification', ''),
            'email': request.form.get('email', ''),
            'address': request.form.get('address', ''),
            'phone': request.form.get('phone', ''),
            'city': request.form.get('city', ''),
            'password': request.form.get('password', '')
        }
        
        # Crear procesador usando Factory y aplicar decoradores
        processor = UserDataProcessorFactory.create_registration_processor()
        processed_data = processor.process(user_data)
        
        # Verificar si hay errores de validación
        if 'errors' in processed_data:
            return jsonify({'error': '; '.join(processed_data['errors'])}), 400
        
        # Usar datos procesados y formateados
        nombre = processed_data['name']
        apellido = processed_data['apellido']
        identificacion = processed_data['identification']
        email = processed_data['email']
        direccion = processed_data['address']
        telefono = processed_data.get('phone_formatted', processed_data['phone'])
        ciudad = processed_data['city']
        password = processed_data['password']
        
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        # Manejar la carga de archivos
        id_file = request.files['id_file']
        profile_file = request.files['profile_file']

        if not id_file or not profile_file:
            return jsonify({'error': 'Se debe subir ambos archivos.'}), 400

        id_file_data = id_file.read()
        profile_file_data = profile_file.read()

        conn = db_manager.get_connection()
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

        conn = db_manager.get_connection()
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
