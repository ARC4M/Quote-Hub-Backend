from flask import Blueprint, request, jsonify, current_app, redirect, url_for
from models import (
    Cotizacion,
    Empresa,
    Producto,
    CodigoInvitacion,
    Soporte,
    LogActividad,
)
from database import db
from pdf_generator import generar_pdf
from email_sender import enviar_email
import os
from datetime import datetime
import jwt  # PyJWT
from functools import wraps
import secrets
from datetime import timedelta
from flask import Blueprint
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import base64
import json as _json
import cloudinary
import cloudinary.uploader

cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
)

cotizacion_bp = Blueprint("cotizacion", __name__)


@cotizacion_bp.route("/codigo/seguridad", methods=["POST"])
def generar_codigo_invitacion():
    data = request.json or {}
    admin_email = os.environ.get("ADMIN_EMAIL")
    admin_password = os.environ.get("ADMIN_PASSWORD")
    email = data.get("email")
    password = data.get("password")
    if not email or not password:
        return jsonify({"error": "Email y password requeridos"}), 400
    if email != admin_email or password != admin_password:
        return jsonify({"error": "Credenciales de administrador inválidas"}), 401
    # Generar código y vencimiento
    codigo = secrets.token_urlsafe(8)
    vencimiento = datetime.utcnow() + timedelta(minutes=3)  # 3 minutos de validez
    # Guardar el código y vencimiento en una tabla temporal (puedes crear una tabla o usar un diccionario en memoria para demo)
    # Aquí se usa una tabla simple en la base de datos
    # Guardar el código
    nuevo = CodigoInvitacion(codigo=codigo, creado=datetime.utcnow(), vence=vencimiento)
    db.session.add(nuevo)
    db.session.commit()
    return jsonify({"codigo": codigo, "vence": vencimiento.isoformat()})


# --- Decorador de autenticación JWT con control de token en base de datos ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if "Authorization" in request.headers:
            auth_header = request.headers["Authorization"]
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
        if not token:
            return jsonify({"error": "Token requerido"}), 401
        try:
            data = jwt.decode(
                token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )
            empresa = Empresa.query.get(data["empresa_id"])
            if not empresa:
                return jsonify({"error": "Empresa no encontrada"}), 401
            # Validar que el token coincida con el token_activo de la empresa
            if not empresa.token_activo or empresa.token_activo != token:
                return jsonify({"error": "Token inválido o sesión cerrada"}), 401
        except Exception as e:
            return jsonify({"error": "Token inválido", "detail": str(e)}), 401
        return f(empresa, *args, **kwargs)

    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if "Authorization" in request.headers:
            auth_header = request.headers["Authorization"]
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
        if not token:
            return jsonify({"error": "Token requerido"}), 401
        try:
            data = jwt.decode(
                token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )
            if not data.get("admin"):
                return jsonify({"error": "Solo el administrador puede acceder"}), 403
        except Exception as e:
            return jsonify({"error": "Token inválido", "detail": str(e)}), 401
        return f(*args, **kwargs)

    return decorated


# --- Endpoint de registro de empresa ---
@cotizacion_bp.route("/register", methods=["POST"])
def register():
    # Si el frontend envía multipart/form-data
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        data = request.form
        logo_file = request.files.get("logo")
    else:
        data = request.json or {}
        logo_file = None
    required = [
        "nombre",
        "email",
        "password",
        "nit",
        "direccion",
        "telefono",
        "contacto",
        "codigo_invitacion",
    ]
    for k in required:
        if not data.get(k):
            return jsonify({"error": f"Campo requerido: {k}"}), 400
    # Validar código de invitación
    codigo = data["codigo_invitacion"]
    invitacion = CodigoInvitacion.query.filter_by(codigo=codigo, usado=0).first()
    if not invitacion:
        return jsonify({"error": "Código de invitación inválido"}), 400
    if invitacion.vence < datetime.utcnow():
        return jsonify({"error": "Código de invitación vencido"}), 400
    invitacion.usado = 1
    db.session.commit()
    if Empresa.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Email ya registrado"}), 400
    # Subir logo a Cloudinary si se envía
    logo_url = ""
    if logo_file:
        try:
            upload_result = cloudinary.uploader.upload(logo_file)
            logo_url = upload_result.get("secure_url", "")
        except Exception as e:
            return jsonify({"error": f"Error subiendo logo: {str(e)}"}), 500
    empresa = Empresa(
        nombre=data["nombre"],
        email=data["email"],
        nit=data["nit"],
        direccion=data["direccion"],
        telefono=data["telefono"],
        contacto=data["contacto"],
        logo_url=logo_url,
    )
    empresa.set_password(data["password"])
    try:
        db.session.add(empresa)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Error al registrar empresa", "detail": str(e)}), 500
    return jsonify({"mensaje": "Empresa registrada correctamente"}), 201


# --- Endpoint de login de empresa y administrador ---
@cotizacion_bp.route("/api/login", methods=["POST"])
def login():
    data = request.json or {}
    if not data.get("email") or not data.get("password"):
        return jsonify({"error": "Email y password requeridos"}), 400

    admin_email = os.environ.get("ADMIN_EMAIL")
    admin_password = os.environ.get("ADMIN_PASSWORD")

    # Login de administrador
    if data["email"] == admin_email and data["password"] == admin_password:
        token = jwt.encode(
            {"admin": True}, current_app.config["SECRET_KEY"], algorithm="HS256"
        )
        return jsonify({"token": token, "admin": True})

    # Login de empresa
    empresa = Empresa.query.filter_by(email=data["email"]).first()
    if not empresa or not empresa.check_password(data["password"]):
        return jsonify({"error": "Credenciales inválidas"}), 401
    token = jwt.encode(
        {"empresa_id": empresa.id}, current_app.config["SECRET_KEY"], algorithm="HS256"
    )
    empresa.token_activo = token
    db.session.commit()
    return jsonify(
        {
            "token": token,
            "empresa": {
                "nombre": empresa.nombre,
                "email": empresa.email,
                "nit": empresa.nit,
                "direccion": empresa.direccion,
                "telefono": empresa.telefono,
                "contacto": empresa.contacto,
                "logo_url": empresa.logo_url,
            },
        }
    )


# --- CRUD de productos ---
@cotizacion_bp.route("/producto", methods=["POST"])
@token_required
def crear_producto(empresa):
    data = request.json or {}
    nombre = data.get("nombre")
    precio = data.get("precio")
    if not nombre or precio is None:
        return jsonify({"error": "Nombre y precio son requeridos"}), 400
    producto = Producto(
        empresa_id=empresa.id,
        nombre=nombre,
        descripcion=data.get("descripcion"),
        precio=precio,
        unidad=data.get("unidad"),
        codigo=data.get("codigo"),
    )
    db.session.add(producto)
    db.session.commit()
    return jsonify({"mensaje": "Producto creado", "id": producto.id}), 201


@cotizacion_bp.route("/producto", methods=["GET"])
@token_required
def listar_productos(empresa):
    productos = Producto.query.filter_by(empresa_id=empresa.id).all()
    return jsonify(
        [
            {
                "id": p.id,
                "nombre": p.nombre,
                "descripcion": p.descripcion,
                "precio": p.precio,
                "unidad": p.unidad,
                "codigo": p.codigo,
            }
            for p in productos
        ]
    )


@cotizacion_bp.route("/producto/<int:producto_id>", methods=["GET"])
@token_required
def obtener_producto(empresa, producto_id):
    p = Producto.query.filter_by(id=producto_id, empresa_id=empresa.id).first()
    if not p:
        return jsonify({"error": "Producto no encontrado"}), 404
    return jsonify(
        {
            "id": p.id,
            "nombre": p.nombre,
            "descripcion": p.descripcion,
            "precio": p.precio,
            "unidad": p.unidad,
            "codigo": p.codigo,
        }
    )


@cotizacion_bp.route("/producto/<int:producto_id>", methods=["PUT"])
@token_required
def actualizar_producto(empresa, producto_id):
    p = Producto.query.filter_by(id=producto_id, empresa_id=empresa.id).first()
    if not p:
        return jsonify({"error": "Producto no encontrado"}), 404
    data = request.json or {}
    for field in ["nombre", "descripcion", "precio", "unidad", "codigo"]:
        if field in data:
            setattr(p, field, data[field])
    db.session.commit()
    return jsonify({"mensaje": "Producto actualizado"}), 200


@cotizacion_bp.route("/producto/<int:producto_id>", methods=["DELETE"])
@token_required
def eliminar_producto(empresa, producto_id):
    p = Producto.query.filter_by(id=producto_id, empresa_id=empresa.id).first()
    if not p:
        return jsonify({"error": "Producto no encontrado"}), 404
    db.session.delete(p)
    db.session.commit()
    return jsonify({"mensaje": "Producto eliminado"}), 200


# --- CRUD de cotizaciones ---
@cotizacion_bp.route("/cotizacion", methods=["POST"])
@token_required
def crear_cotizacion(empresa):
    data = request.json or {}
    if not all(data.get(k) for k in ("cliente", "correo", "productos")):
        return jsonify({"error": "Datos incompletos"}), 400
    import json

    productos_input = data["productos"]
    if isinstance(productos_input, str):
        try:
            productos_input = json.loads(productos_input)
        except Exception:
            return jsonify({"error": "El campo 'productos' no es un JSON válido"}), 400
    if not isinstance(productos_input, list) or not productos_input:
        return jsonify({"error": "Debe enviar al menos un producto válido"}), 400

    # Validar que todos los productos existan en la base de datos y pertenezcan a la empresa
    productos_db = {
        p.id: p for p in Producto.query.filter_by(empresa_id=empresa.id).all()
    }
    productos_final = []
    for p in productos_input:
        prod_id = p.get("id")
        cantidad = p.get("cantidad", 1)
        if not prod_id or prod_id not in productos_db:
            return (
                jsonify(
                    {
                        "error": f"Producto con id {prod_id} no existe o no pertenece a la empresa"
                    }
                ),
                400,
            )
        prod_db = productos_db[prod_id]
        # Usar datos reales del producto de la base de datos
        productos_final.append(
            {
                "id": prod_db.id,
                "nombre": prod_db.nombre,
                "descripcion": prod_db.descripcion,
                "precio": prod_db.precio,
                "unidad": prod_db.unidad,
                "codigo": prod_db.codigo,
                "cantidad": cantidad,
            }
        )

    subtotal = sum(p["cantidad"] * p["precio"] for p in productos_final)
    descuento = float(data.get("descuento", 0))
    iva = float(data.get("iva", 0))
    total = subtotal - descuento
    if iva > 0:
        total += total * (iva / 100)
    codigo_cotizacion = data.get("codigo_cotizacion")
    if not codigo_cotizacion:
        codigo_cotizacion = f"COT-{int(datetime.utcnow().timestamp())}"
    data["subtotal"] = subtotal
    data["descuento"] = descuento
    data["iva"] = iva
    data["total"] = total
    data["codigo_cotizacion"] = codigo_cotizacion
    # --- Agregar datos de empresa al PDF ---
    data["empresa"] = {
        "nombre": empresa.nombre,
        "nit": empresa.nit,
        "direccion": empresa.direccion,
        "telefono": empresa.telefono,
        "contacto": empresa.contacto,
        "logo_url": empresa.logo_url,
        "email": empresa.email,
    }
    data["productos"] = productos_final
    filename = f"cotizacion_{codigo_cotizacion}.pdf"
    try:
        pdf_bytes, _ = generar_pdf(data, filename)
    except Exception as e:
        return jsonify({"error": "Error generando PDF", "detail": str(e)}), 500
    try:
        # Solo permitir envío si la empresa tiene token de Gmail
        if not empresa.gmail_access_token:
            return (
                jsonify(
                    {
                        "error": "La empresa debe autorizar el envío de correos con Gmail (OAuth2) antes de poder enviar cotizaciones."
                    }
                ),
                400,
            )
        enviado = enviar_email_gmail_oauth2(
            empresa.gmail_access_token,
            empresa.email,
            data["correo"],
            "Cotización",
            "Adjunto PDF de cotización",
            pdf_bytes,
            refresh_token=empresa.gmail_refresh_token,
        )
    except Exception as e:
        enviado = False
    estado = "Enviado" if enviado else "Fallido"
    cotizacion = Cotizacion(
        empresa_id=empresa.id,
        cliente=data["cliente"],
        correo=data["correo"],
        telefono=data.get("telefono"),
        direccion=data.get("direccion"),
        vendedor=data.get("vendedor"),
        fecha=data.get("fecha"),
        validez=data.get("validez"),
        forma_pago=data.get("forma_pago"),
        tiempo_entrega=data.get("tiempo_entrega"),
        estado_cotizacion=data.get("estado_cotizacion"),
        notas_legales=data.get("notas_legales"),
        firma=data.get("firma"),
        codigo_cotizacion=codigo_cotizacion,
        observaciones=data.get("observaciones"),
        productos=productos_final,
        subtotal=subtotal,
        descuento=descuento,
        iva=iva,
        total=total,
        condiciones=data.get("condiciones", ""),
        estado_envio=estado,
        archivo_pdf=pdf_bytes,
    )
    try:
        db.session.add(cotizacion)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Error guardando cotización", "detail": str(e)}), 500
    return (
        jsonify({"mensaje": "Cotización procesada", "total": total, "estado": estado}),
        200,
    )


# Listar cotizaciones de la empresa autenticada
@cotizacion_bp.route("/cotizacion", methods=["GET"])
@token_required
def listar_cotizaciones(empresa):
    cotizaciones = Cotizacion.query.filter_by(empresa_id=empresa.id).all()
    return jsonify(
        [
            {
                "id": c.id,
                "empresa_id": c.empresa_id,
                "codigo_cotizacion": c.codigo_cotizacion,
                "cliente": c.cliente,
                "correo": c.correo,
                "telefono": c.telefono,
                "direccion": c.direccion,
                "vendedor": c.vendedor,
                "fecha": c.fecha,
                "validez": c.validez,
                "forma_pago": c.forma_pago,
                "tiempo_entrega": c.tiempo_entrega,
                "estado_cotizacion": c.estado_cotizacion,
                "notas_legales": c.notas_legales,
                "firma": c.firma,
                "observaciones": c.observaciones,
                "productos": c.productos,
                "subtotal": c.subtotal,
                "descuento": c.descuento,
                "iva": c.iva,
                "total": c.total,
                "condiciones": c.condiciones,
                "estado_envio": c.estado_envio,
                "archivo_pdf": True if c.archivo_pdf else False,
            }
            for c in cotizaciones
        ]
    )


# Obtener cotización por ID (solo si pertenece a la empresa)
@cotizacion_bp.route("/cotizacion/<int:cotizacion_id>", methods=["GET"])
@token_required
def obtener_cotizacion(empresa, cotizacion_id):
    c = Cotizacion.query.filter_by(id=cotizacion_id, empresa_id=empresa.id).first()
    if not c:
        return jsonify({"error": "Cotización no encontrada"}), 404
    return jsonify(
        {
            "id": c.id,
            "codigo_cotizacion": c.codigo_cotizacion,
            "cliente": c.cliente,
            "correo": c.correo,
            "telefono": c.telefono,
            "direccion": c.direccion,
            "vendedor": c.vendedor,
            "fecha": c.fecha,
            "validez": c.validez,
            "forma_pago": c.forma_pago,
            "tiempo_entrega": c.tiempo_entrega,
            "estado_cotizacion": c.estado_cotizacion,
            "notas_legales": c.notas_legales,
            "firma": c.firma,
            "observaciones": c.observaciones,
            "productos": c.productos,
            "subtotal": c.subtotal,
            "descuento": c.descuento,
            "iva": c.iva,
            "total": c.total,
            "condiciones": c.condiciones,
            "estado_envio": c.estado_envio,
        }
    )


# Eliminar cotización (solo si pertenece a la empresa)
@cotizacion_bp.route("/cotizacion/<int:cotizacion_id>", methods=["DELETE"])
@token_required
def eliminar_cotizacion(empresa, cotizacion_id):
    c = Cotizacion.query.filter_by(id=cotizacion_id, empresa_id=empresa.id).first()
    if not c:
        return jsonify({"error": "Cotización no encontrada"}), 404
    db.session.delete(c)
    db.session.commit()
    return jsonify({"mensaje": "Cotización eliminada"}), 200


# Actualizar cotización (solo si pertenece a la empresa)
@cotizacion_bp.route("/cotizacion/<int:cotizacion_id>", methods=["PUT"])
@token_required
def actualizar_cotizacion(empresa, cotizacion_id):
    c = Cotizacion.query.filter_by(id=cotizacion_id, empresa_id=empresa.id).first()
    if not c:
        return jsonify({"error": "Cotización no encontrada"}), 404
    data = request.json or {}
    # Si se actualizan productos, validar que existan y pertenezcan a la empresa
    if "productos" in data:
        import json

        productos_input = data["productos"]
        if isinstance(productos_input, str):
            try:
                productos_input = json.loads(productos_input)
            except Exception:
                return (
                    jsonify({"error": "El campo 'productos' no es un JSON válido"}),
                    400,
                )
        if not isinstance(productos_input, list) or not productos_input:
            return jsonify({"error": "Debe enviar al menos un producto válido"}), 400
        productos_db = {
            p.id: p for p in Producto.query.filter_by(empresa_id=empresa.id).all()
        }
        productos_final = []
        for p in productos_input:
            prod_id = p.get("id")
            cantidad = p.get("cantidad", 1)
            if not prod_id or prod_id not in productos_db:
                return (
                    jsonify(
                        {
                            "error": f"Producto con id {prod_id} no existe o no pertenece a la empresa"
                        }
                    ),
                    400,
                )
            prod_db = productos_db[prod_id]
            productos_final.append(
                {
                    "id": prod_db.id,
                    "nombre": prod_db.nombre,
                    "descripcion": prod_db.descripcion,
                    "precio": prod_db.precio,
                    "unidad": prod_db.unidad,
                    "codigo": prod_db.codigo,
                    "cantidad": cantidad,
                }
            )
        c.productos = productos_final
        # Recalcular subtotal, total, etc. si se actualizan productos
        subtotal = sum(p["cantidad"] * p["precio"] for p in productos_final)
        c.subtotal = subtotal
        descuento = float(data.get("descuento", c.descuento or 0))
        iva = float(data.get("iva", c.iva or 0))
        total = subtotal - descuento
        if iva > 0:
            total += total * (iva / 100)
        c.descuento = descuento
        c.iva = iva
        c.total = total
    # Actualizar otros campos
    for field in [
        "cliente",
        "correo",
        "telefono",
        "direccion",
        "vendedor",
        "fecha",
        "validez",
        "forma_pago",
        "tiempo_entrega",
        "estado_cotizacion",
        "notas_legales",
        "firma",
        "observaciones",
        "condiciones",
        "estado_envio",
    ]:
        if field in data:
            setattr(c, field, data[field])
    db.session.commit()
    return jsonify({"mensaje": "Cotización actualizada"}), 200


# --- Endpoint de logout (cierre de sesión) ---
@cotizacion_bp.route("/logout", methods=["POST"])
@token_required
def logout(empresa):
    # Elimina el token activo de la empresa
    empresa.token_activo = None
    db.session.commit()
    return jsonify({"mensaje": "Sesión cerrada."}), 200

# --- ADMIN: Listar empresas (solo datos generales) ---
@cotizacion_bp.route("/admin/empresas", methods=["GET"])
@admin_required
def admin_listar_empresas():
    empresas = Empresa.query.all()
    return jsonify(
        [
            {
                "id": e.id,
                "nombre": e.nombre,
                "email": e.email,
                "nit": e.nit,
                "fecha_registro": str(getattr(e, "creado", "")),
                "estado": "activo",
                "gmail_autorizado": bool(e.gmail_access_token),
            }
            for e in empresas
        ]
    )


# --- ADMIN: Estadísticas globales ---
@cotizacion_bp.route("/admin/estadisticas", methods=["GET"])
@admin_required
def admin_estadisticas():
    total_empresas = Empresa.query.count()
    total_productos = Producto.query.count()
    total_cotizaciones = Cotizacion.query.count()
    total_soporte = Soporte.query.count()
    return jsonify(
        {
            "total_empresas": total_empresas,
            "total_productos": total_productos,
            "total_cotizaciones": total_cotizaciones,
            "total_soporte": total_soporte,
        }
    )


# --- ADMIN: Listar códigos de invitación ---
@cotizacion_bp.route("/admin/codigos-invitacion", methods=["GET"])
@admin_required
def admin_listar_codigos():
    codigos = CodigoInvitacion.query.order_by(CodigoInvitacion.creado.desc()).all()
    return jsonify(
        [
            {
                "id": c.id,
                "codigo": c.codigo,
                "creado": c.creado.isoformat(),
                "vence": c.vence.isoformat(),
                "usado": c.usado,
            }
            for c in codigos
        ]
    )


# --- ADMIN: Crear código de invitación ---
@cotizacion_bp.route("/admin/codigos-invitacion", methods=["POST"])
@admin_required
def admin_crear_codigo():
    from datetime import datetime, timedelta

    codigo = secrets.token_urlsafe(8)
    creado = datetime.utcnow()
    vence = creado + timedelta(minutes=10)
    nuevo = CodigoInvitacion(codigo=codigo, creado=creado, vence=vence)
    db.session.add(nuevo)
    db.session.commit()
    return jsonify({"codigo": codigo, "vence": vence.isoformat()})


# --- ADMIN: Revocar código de invitación ---
@cotizacion_bp.route("/admin/codigos-invitacion/<int:codigo_id>", methods=["DELETE"])
@admin_required
def admin_revocar_codigo(codigo_id):
    codigo = CodigoInvitacion.query.get(codigo_id)
    if not codigo:
        return jsonify({"error": "Código no encontrado"}), 404
    db.session.delete(codigo)
    db.session.commit()
    return jsonify({"mensaje": "Código revocado"})


# --- ADMIN: Logs de actividad global ---
@cotizacion_bp.route("/admin/logs", methods=["GET"])
@admin_required
def admin_logs():
    logs = LogActividad.query.order_by(LogActividad.fecha.desc()).limit(100).all()
    return jsonify(
        [
            {
                "id": l.id,
                "fecha": l.fecha.isoformat(),
                "tipo": l.tipo,
                "descripcion": l.descripcion,
                "empresa_id": l.empresa_id,
            }
            for l in logs
        ]
    )


# --- EMPRESA: Enviar solicitud de soporte ---
@cotizacion_bp.route("/soporte", methods=["POST"])
@token_required
def enviar_soporte(empresa):
    data = request.json or {}
    asunto = data.get("asunto")
    mensaje = data.get("mensaje")
    if not asunto or not mensaje:
        return jsonify({"error": "Asunto y mensaje requeridos"}), 400
    soporte = Soporte(empresa_id=empresa.id, asunto=asunto, mensaje=mensaje)
    db.session.add(soporte)
    db.session.commit()
    return jsonify({"mensaje": "Solicitud de soporte enviada"})


# --- ADMIN: Listar solicitudes de soporte ---
@cotizacion_bp.route("/admin/soporte", methods=["GET"])
@admin_required
def admin_listar_soporte():
    solicitudes = Soporte.query.order_by(Soporte.fecha.desc()).all()
    return jsonify(
        [
            {
                "id": s.id,
                "empresa_id": s.empresa_id,
                "asunto": s.asunto,
                "mensaje": s.mensaje,
                "fecha": s.fecha.isoformat(),
                "estado": s.estado,
                "respuesta": s.respuesta,
                "fecha_respuesta": (
                    s.fecha_respuesta.isoformat() if s.fecha_respuesta else None
                ),
            }
            for s in solicitudes
        ]
    )


# --- ADMIN: Responder solicitud de soporte ---
@cotizacion_bp.route("/admin/soporte/<int:soporte_id>/responder", methods=["POST"])
@admin_required
def admin_responder_soporte(soporte_id):
    data = request.json or {}
    respuesta = data.get("respuesta")
    soporte = Soporte.query.get(soporte_id)
    if not soporte:
        return jsonify({"error": "Solicitud de soporte no encontrada"}), 404
    soporte.respuesta = respuesta
    soporte.estado = "respondido"
    soporte.fecha_respuesta = datetime.utcnow()
    db.session.commit()
    return jsonify({"mensaje": "Respuesta enviada"})


@cotizacion_bp.route("/empresas", methods=["GET"])
def listar_empresas():
    from models import Empresa
    import os
    from flask import request, jsonify, current_app
    import jwt

    # Verificar token de admin
    token = None
    if "Authorization" in request.headers:
        auth_header = request.headers["Authorization"]
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
    if not token:
        return jsonify({"error": "Token requerido"}), 401
    try:
        data = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
        if not data.get("admin"):
            return (
                jsonify(
                    {"error": "Solo el administrador puede ver todas las empresas"}
                ),
                403,
            )
    except Exception as e:
        return jsonify({"error": "Token inválido", "detail": str(e)}), 401
    empresas = Empresa.query.all()
    return jsonify(
        [
            {
                "id": e.id,
                "nombre": e.nombre,
                "email": e.email,
                "nit": e.nit,
                "direccion": e.direccion,
                "telefono": e.telefono,
                "contacto": e.contacto,
                "logo_url": e.logo_url,
            }
            for e in empresas
        ]
    )


@cotizacion_bp.route("/oauth2/authorize")
def oauth2_authorize():
    token = (
        request.cookies.get("token")
        or request.args.get("token")
        or request.headers.get("Authorization")
    )
    if token and token.startswith("Bearer "):
        token = token.split(" ")[1]
    flow = Flow.from_client_secrets_file(
        "client_secret.json",
        scopes=["https://www.googleapis.com/auth/gmail.send"],
        redirect_uri=url_for("cotizacion.oauth2_callback", _external=True),
    )
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",  # Forzar que Google siempre pida consentimiento y devuelva refresh_token
        state=token,  # Pasar el token JWT en el parámetro state
    )
    return redirect(authorization_url)


@cotizacion_bp.route("/oauth2/callback")
def oauth2_callback():
    flow = Flow.from_client_secrets_file(
        "client_secret.json",
        scopes=["https://www.googleapis.com/auth/gmail.send"],
        redirect_uri=url_for("cotizacion.oauth2_callback", _external=True),
    )
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    # Obtener el token de autenticación de la empresa desde el parámetro state
    token = request.args.get("state")
    empresa = None
    if token:
        try:
            data = jwt.decode(
                token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )
            empresa = Empresa.query.get(data.get("empresa_id"))
        except Exception:
            empresa = None
    if not empresa:
        return (
            jsonify(
                {
                    "error": "No se pudo asociar el token OAuth2 a ninguna empresa autenticada"
                }
            ),
            401,
        )
    # Guardar los tokens en la empresa
    empresa.gmail_access_token = credentials.token
    # Solo actualizar el refresh_token si viene en la respuesta
    if credentials.refresh_token:
        empresa.gmail_refresh_token = credentials.refresh_token
        print(
            f"Nuevo refresh_token guardado para empresa {empresa.id}: {credentials.refresh_token[:20]}..."
        )
    else:
        print(
            f"No se recibió refresh_token para empresa {empresa.id}. Token actual: {empresa.gmail_refresh_token[:20] if empresa.gmail_refresh_token else 'None'}..."
        )
    db.session.commit()
    # Redirigir automáticamente al frontend después de autorizar
    frontend_url = request.args.get("frontend_url", "http://localhost:3001")
    return redirect(f"{frontend_url}/dashboard/configuracion?oauth=ok")


def enviar_email_gmail_oauth2(
    access_token,
    remitente,
    destinatario,
    asunto,
    cuerpo,
    archivo_pdf=None,
    refresh_token=None,
):
    from email.mime.multipart import MIMEMultipart
    from email.mime.application import MIMEApplication

    # Leer client_id, client_secret, token_uri del client_secret.json
    with open("client_secret.json") as f:
        secrets = _json.load(f)["web"]

    print(
        f"Enviando correo - Access token: {access_token[:20] if access_token else 'None'}..."
    )
    print(
        f"Enviando correo - Refresh token: {refresh_token[:20] if refresh_token else 'None'}..."
    )

    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri=secrets["token_uri"],
        client_id=secrets["client_id"],
        client_secret=secrets["client_secret"],
    )
    service = build("gmail", "v1", credentials=creds)

    # Crear mensaje multipart para poder adjuntar archivos
    message = MIMEMultipart()
    message["to"] = destinatario
    message["from"] = remitente
    message["subject"] = asunto

    # Agregar el cuerpo del mensaje
    message.attach(MIMEText(cuerpo, "plain", "utf-8"))

    # Adjuntar el PDF si se proporciona
    if archivo_pdf:
        pdf_attachment = MIMEApplication(archivo_pdf, _subtype="pdf")
        pdf_attachment.add_header(
            "Content-Disposition", "attachment", filename="cotizacion.pdf"
        )
        message.attach(pdf_attachment)
        print("PDF adjuntado al correo")

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    message_body = {"raw": raw}
    try:
        service.users().messages().send(userId="me", body=message_body).execute()
        print("Correo enviado exitosamente")
        return True
    except Exception as e:
        print("Error al enviar correo:", e)
        return False


@cotizacion_bp.route("/empresa/me", methods=["GET"])
@token_required
def empresa_me(empresa):
    """
    Devuelve la información de la empresa autenticada, incluyendo el estado de autorización de Gmail.
    """
    return jsonify(
        {
            "id": empresa.id,
            "nombre": empresa.nombre,
            "email": empresa.email,
            "nit": empresa.nit,
            "direccion": empresa.direccion,
            "telefono": empresa.telefono,
            "contacto": empresa.contacto,
            "logo_url": empresa.logo_url,
            "gmail_autorizado": bool(empresa.gmail_access_token),
            # Puedes agregar más campos si lo necesitas
        }
    )


@cotizacion_bp.route("/debug/oauth-tokens", methods=["GET"])
@token_required
def debug_oauth_tokens(empresa):
    """
    Endpoint temporal para verificar los tokens OAuth2 de la empresa.
    """
    return jsonify(
        {
            "empresa_id": empresa.id,
            "gmail_access_token": (
                empresa.gmail_access_token[:20] + "..."
                if empresa.gmail_access_token
                else None
            ),
            "gmail_refresh_token": (
                empresa.gmail_refresh_token[:20] + "..."
                if empresa.gmail_refresh_token
                else None
            ),
            "gmail_access_token_existe": bool(empresa.gmail_access_token),
            "gmail_refresh_token_existe": bool(empresa.gmail_refresh_token),
        }
    )


@cotizacion_bp.route("/producto/carga-masiva", methods=["POST"])
@token_required
def cargar_productos_masiva(empresa):
    """
    Endpoint para cargar productos de manera masiva desde un archivo Excel.

    Formato esperado del Excel:
    - nombre (obligatorio): Nombre del producto
    - descripcion (opcional): Descripción del producto
    - precio (obligatorio): Precio del producto (número)
    - unidad (opcional): Unidad de medida (ej: unidad, kg, metro)
    - codigo (opcional): Código del producto

    El archivo debe ser un .xlsx o .xls
    """
    import pandas as pd
    from werkzeug.utils import secure_filename
    import io

    if "archivo" not in request.files:
        return jsonify({"error": "No se envió ningún archivo"}), 400

    archivo = request.files["archivo"]

    if archivo.filename == "":
        return jsonify({"error": "No se seleccionó ningún archivo"}), 400

    # Validar extensión del archivo
    extensiones_validas = ["xlsx", "xls"]
    extension = (
        archivo.filename.rsplit(".", 1)[1].lower() if "." in archivo.filename else ""
    )

    if extension not in extensiones_validas:
        return jsonify({"error": "Solo se permiten archivos Excel (.xlsx o .xls)"}), 400

    try:
        # Leer el archivo Excel
        df = pd.read_excel(
            archivo.stream, engine="openpyxl" if extension == "xlsx" else "xlrd"
        )

        # Validar columnas obligatorias
        columnas_obligatorias = ["nombre", "precio"]
        columnas_faltantes = [
            col for col in columnas_obligatorias if col not in df.columns
        ]

        if columnas_faltantes:
            return (
                jsonify(
                    {
                        "error": f"Faltan columnas obligatorias: {', '.join(columnas_faltantes)}",
                        "columnas_requeridas": ["nombre", "precio"],
                        "columnas_opcionales": ["descripcion", "unidad", "codigo"],
                    }
                ),
                400,
            )

        # Procesar los datos
        productos_creados = []
        productos_errores = []

        for index, row in df.iterrows():
            try:
                # Validar campos obligatorios
                nombre = str(row["nombre"]).strip()
                precio = row["precio"]

                if not nombre or nombre.lower() == "nan":
                    productos_errores.append(
                        {
                            "fila": index
                            + 2,  # +2 porque índice empieza en 0 y hay header
                            "error": "El nombre es obligatorio",
                        }
                    )
                    continue

                # Validar precio
                try:
                    precio = float(precio)
                    if precio < 0:
                        productos_errores.append(
                            {
                                "fila": index + 2,
                                "error": "El precio debe ser mayor o igual a 0",
                            }
                        )
                        continue
                except (ValueError, TypeError):
                    productos_errores.append(
                        {
                            "fila": index + 2,
                            "error": "El precio debe ser un número válido",
                        }
                    )
                    continue

                # Campos opcionales
                descripcion = str(row.get("descripcion", "")).strip()
                if descripcion.lower() == "nan":
                    descripcion = ""

                unidad = str(row.get("unidad", "unidad")).strip()
                if unidad.lower() == "nan":
                    unidad = "unidad"

                codigo = str(row.get("codigo", "")).strip()
                if codigo.lower() == "nan":
                    codigo = ""

                # Verificar si ya existe un producto con el mismo nombre o código
                producto_existente = None
                if codigo:
                    producto_existente = Producto.query.filter_by(
                        codigo=codigo, empresa_id=empresa.id
                    ).first()

                if not producto_existente:
                    producto_existente = Producto.query.filter_by(
                        nombre=nombre, empresa_id=empresa.id
                    ).first()

                if producto_existente:
                    productos_errores.append(
                        {
                            "fila": index + 2,
                            "error": f"Ya existe un producto con el nombre '{nombre}'"
                            + (f" o código '{codigo}'" if codigo else ""),
                        }
                    )
                    continue

                # Crear el producto
                producto = Producto(
                    nombre=nombre,
                    descripcion=descripcion,
                    precio=precio,
                    unidad=unidad,
                    codigo=codigo,
                    empresa_id=empresa.id,
                )

                db.session.add(producto)
                productos_creados.append(
                    {
                        "fila": index + 2,
                        "nombre": nombre,
                        "precio": precio,
                        "unidad": unidad,
                        "codigo": codigo or None,
                    }
                )

            except Exception as e:
                productos_errores.append(
                    {"fila": index + 2, "error": f"Error procesando fila: {str(e)}"}
                )

        # Guardar los productos válidos
        if productos_creados:
            db.session.commit()

        return (
            jsonify(
                {
                    "mensaje": f"Procesamiento completado",
                    "productos_creados": len(productos_creados),
                    "productos_con_errores": len(productos_errores),
                    "detalles_creados": productos_creados,
                    "errores": productos_errores,
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error procesando archivo: {str(e)}"}), 500


@cotizacion_bp.route("/producto/plantilla-excel", methods=["GET"])
@token_required
def descargar_plantilla_excel(empresa):
    """
    Genera y descarga una plantilla de Excel con el formato correcto para carga masiva.
    """
    import pandas as pd
    from flask import Response
    import io

    # Crear DataFrame con ejemplo
    datos_ejemplo = {
        "nombre": ["Producto Ejemplo 1", "Producto Ejemplo 2", "Producto Ejemplo 3"],
        "descripcion": [
            "Descripción del producto 1",
            "Descripción del producto 2",
            "Descripción del producto 3",
        ],
        "precio": [100000, 250000, 75000],
        "unidad": ["unidad", "kg", "metro"],
        "codigo": ["PROD001", "PROD002", "PROD003"],
    }

    df = pd.DataFrame(datos_ejemplo)

    # Crear archivo Excel en memoria
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Productos", index=False)

        # Acceder al workbook y worksheet para personalizar
        workbook = writer.book
        worksheet = writer.sheets["Productos"]

        # Ajustar ancho de columnas
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width

    output.seek(0)

    return Response(
        output.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=plantilla_productos.xlsx"
        },
    )
    
@cotizacion_bp.route("/", methods=["GET"])
def index():
    return jsonify({"mensaje": "Bienvenido a la API de Quote Hub"}), 200
