## Funcionalidad Detallada del Proyecto Quote-Hub-Backend

Este proyecto permite a empresas y microempresas gestionar cotizaciones de manera eficiente y automatizada. A continuación se describe el flujo y las funcionalidades principales:

### 1. Registro y Autenticación de Empresas
- Las empresas se registran usando un código de invitación generado por el administrador (con vencimiento y control de uso).
- El registro requiere datos como nombre, email, NIT, dirección, teléfono, contacto y contraseña.
- El sistema permite la autenticación tanto de empresas como del administrador, generando tokens JWT para el acceso seguro.
- Logout disponible para invalidar el token activo.

### 2. Gestión de Productos
- CRUD completo de productos: crear, listar, obtener, actualizar y eliminar productos asociados a la empresa.
- Carga masiva de productos mediante archivo Excel, con validación de formato y plantilla descargable desde la plataforma.
- Cada producto puede tener nombre, descripción, precio, unidad y código.

### 3. Gestión de Cotizaciones
- CRUD completo de cotizaciones: crear, listar, obtener, actualizar y eliminar cotizaciones.
- Al crear una cotización, se valida que los productos existan y pertenezcan a la empresa.
- El sistema calcula subtotal, descuentos, IVA y total automáticamente.
- Generación de PDF de la cotización con los datos de la empresa y productos.
- Envío automático de la cotización al correo del cliente, usando integración con Gmail OAuth2 (requiere autorización previa de la empresa).
- Almacena el PDF generado y el estado del envío (enviado/fallido).

### 4. Administración y Seguridad
- El administrador puede:
  - Listar todas las empresas registradas.
  - Ver estadísticas globales (empresas, productos, cotizaciones, solicitudes de soporte).
  - Gestionar códigos de invitación (crear, listar, revocar).
  - Ver logs de actividad global.
  - Listar y responder solicitudes de soporte de empresas.
- Acceso a endpoints administrativos protegido por autenticación especial.

### 5. Soporte y Comunicación
- Las empresas pueden enviar solicitudes de soporte.
- El administrador puede responder a las solicitudes, quedando registro de la respuesta y su estado.


### 6. Integraciones y Utilidades
- Integración con Cloudinary para almacenamiento de logos de empresa.
- Integración con Gmail API para envío seguro de correos electrónicos con archivos adjuntos (PDF).
- Endpoints para depuración de tokens OAuth2 y consulta de estado de autorización de Gmail.
- Endpoint público para listar empresas (requiere token de administrador).

---

## Características Únicas y Destacadas

Este proyecto incluye funcionalidades avanzadas y diferenciales que lo hacen destacar frente a soluciones tradicionales:

- **Registro seguro con códigos de invitación temporales y controlados por el administrador**, lo que evita registros no autorizados y permite un control total sobre el acceso.
- **Carga masiva de productos mediante Excel con plantilla descargable y validación automática**, facilitando la migración y gestión de grandes catálogos de productos sin errores.
- **Generación automática de cotizaciones en PDF con diseño profesional**, integrando todos los datos de la empresa y productos, sin intervención manual.
- **Envío de cotizaciones por correo electrónico directamente desde la plataforma usando integración OAuth2 con Gmail**, garantizando seguridad y cumplimiento de políticas modernas de envío.
- **Almacenamiento seguro de logos empresariales en la nube (Cloudinary)**, permitiendo personalización visual de las cotizaciones.
- **Panel administrativo completo**: gestión de empresas, productos, cotizaciones, soporte, estadísticas y logs de actividad, todo desde endpoints protegidos.
- **Soporte integrado y trazabilidad de respuestas**, permitiendo comunicación directa y registro de atención entre empresas y administradores.
- **Control de sesión y tokens activos**, con posibilidad de cierre de sesión remoto y validación de seguridad en cada operación.
- **Endpoints de depuración y diagnóstico para integraciones OAuth2**, facilitando la administración y soporte técnico.

Estas características hacen que la solución sea robusta, segura, escalable y adaptable a las necesidades reales de empresas que requieren gestión avanzada de cotizaciones y comunicación profesional con sus clientes.

---

## Documentación de Endpoints del API

### Autenticación y Registro

#### 1. Generar Código de Invitación (Solo Admin)
```
POST /codigo/seguridad
```
**Body:**
```json
{
  "email": "admin@example.com",
  "password": "admin_password"
}
```
**Respuesta:**
```json
{
  "codigo": "abc123xyz",
  "vence": "2025-07-07T12:03:00Z"
}
```

#### 2. Registro de Empresa
```
POST /register
```
**Body (JSON o multipart/form-data):**
```json
{
  "nombre": "Mi Empresa SA",
  "email": "empresa@example.com",
  "password": "password123",
  "nit": "900123456-7",
  "direccion": "Calle 123 #45-67",
  "telefono": "+57 300 123 4567",
  "contacto": "Juan Pérez",
  "codigo_invitacion": "abc123xyz"
}
```
**Archivo (opcional):** `logo` (imagen del logo)

#### 3. Login (Empresa o Admin)
```
POST /login
```
**Body:**
```json
{
  "email": "empresa@example.com",
  "password": "password123"
}
```
**Respuesta:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "empresa": {
    "nombre": "Mi Empresa SA",
    "email": "empresa@example.com",
    "nit": "900123456-7",
    "direccion": "Calle 123 #45-67",
    "telefono": "+57 300 123 4567",
    "contacto": "Juan Pérez",
    "logo_url": "https://cloudinary.com/logo.jpg"
  }
}
```

#### 4. Logout
```
POST /logout
```
**Headers:** `Authorization: Bearer <token>`

### Gestión de Productos

#### 5. Crear Producto
```
POST /producto
```
**Headers:** `Authorization: Bearer <token>`
**Body:**
```json
{
  "nombre": "Producto Ejemplo",
  "descripcion": "Descripción del producto",
  "precio": 100000,
  "unidad": "unidad",
  "codigo": "PROD001"
}
```

#### 6. Listar Productos
```
GET /producto
```
**Headers:** `Authorization: Bearer <token>`

#### 7. Obtener Producto por ID
```
GET /producto/<id>
```
**Headers:** `Authorization: Bearer <token>`

#### 8. Actualizar Producto
```
PUT /producto/<id>
```
**Headers:** `Authorization: Bearer <token>`
**Body:**
```json
{
  "nombre": "Producto Actualizado",
  "precio": 120000
}
```

#### 9. Eliminar Producto
```
DELETE /producto/<id>
```
**Headers:** `Authorization: Bearer <token>`

#### 10. Carga Masiva de Productos
```
POST /producto/carga-masiva
```
**Headers:** `Authorization: Bearer <token>`
**Body:** `multipart/form-data` con archivo Excel
**Archivo:** `archivo` (archivo .xlsx o .xls)

#### 11. Descargar Plantilla Excel
```
GET /producto/plantilla-excel
```
**Headers:** `Authorization: Bearer <token>`

### Gestión de Cotizaciones

#### 12. Crear Cotización
```
POST /cotizacion
```
**Headers:** `Authorization: Bearer <token>`
**Body:**
```json
{
  "cliente": "Cliente Example SAS",
  "correo": "cliente@example.com",
  "telefono": "+57 300 987 6543",
  "direccion": "Av. Principal 123",
  "vendedor": "María García",
  "fecha": "2025-07-07",
  "validez": "30 días",
  "forma_pago": "Efectivo",
  "tiempo_entrega": "5 días hábiles",
  "estado_cotizacion": "Pendiente",
  "notas_legales": "Términos y condiciones aplicables",
  "firma": "María García - Representante de Ventas",
  "codigo_cotizacion": "COT-2025-001",
  "observaciones": "Cotización especial para cliente frecuente",
  "productos": [
    {
      "id": 1,
      "cantidad": 2
    },
    {
      "id": 2,
      "cantidad": 1
    }
  ],
  "descuento": 10000,
  "iva": 19,
  "condiciones": "Pago contra entrega"
}
```

#### 13. Listar Cotizaciones
```
GET /cotizacion
```
**Headers:** `Authorization: Bearer <token>`

#### 14. Obtener Cotización por ID
```
GET /cotizacion/<id>
```
**Headers:** `Authorization: Bearer <token>`

#### 15. Actualizar Cotización
```
PUT /cotizacion/<id>
```
**Headers:** `Authorization: Bearer <token>`
**Body:** (misma estructura que crear cotización)

#### 16. Eliminar Cotización
```
DELETE /cotizacion/<id>
```
**Headers:** `Authorization: Bearer <token>`

### Información de Empresa

#### 17. Obtener Datos de Empresa Autenticada
```
GET /empresa/me
```
**Headers:** `Authorization: Bearer <token>`

#### 18. Autorización OAuth2 para Gmail
```
GET /oauth2/authorize?token=<empresa_token>
```
Redirige a Google para autorizar el acceso a Gmail.

#### 19. Callback OAuth2
```
GET /oauth2/callback
```
Endpoint interno manejado por Google OAuth2.

### Soporte

#### 20. Enviar Solicitud de Soporte
```
POST /soporte
```
**Headers:** `Authorization: Bearer <token>`
**Body:**
```json
{
  "asunto": "Problema con envío de cotizaciones",
  "mensaje": "No puedo enviar cotizaciones por correo electrónico..."
}
```

### Endpoints Administrativos

#### 21. Listar Empresas (Admin)
```
GET /admin/empresas
```
**Headers:** `Authorization: Bearer <admin_token>`

#### 22. Estadísticas Globales (Admin)
```
GET /admin/estadisticas
```
**Headers:** `Authorization: Bearer <admin_token>`

#### 23. Listar Códigos de Invitación (Admin)
```
GET /admin/codigos-invitacion
```
**Headers:** `Authorization: Bearer <admin_token>`

#### 24. Crear Código de Invitación (Admin)
```
POST /admin/codigos-invitacion
```
**Headers:** `Authorization: Bearer <admin_token>`

#### 25. Revocar Código de Invitación (Admin)
```
DELETE /admin/codigos-invitacion/<id>
```
**Headers:** `Authorization: Bearer <admin_token>`

#### 26. Ver Logs de Actividad (Admin)
```
GET /admin/logs
```
**Headers:** `Authorization: Bearer <admin_token>`

#### 27. Listar Solicitudes de Soporte (Admin)
```
GET /admin/soporte
```
**Headers:** `Authorization: Bearer <admin_token>`

#### 28. Responder Solicitud de Soporte (Admin)
```
POST /admin/soporte/<id>/responder
```
**Headers:** `Authorization: Bearer <admin_token>`
**Body:**
```json
{
  "respuesta": "Hemos revisado tu solicitud y la solución es..."
}
```

### Endpoints de Utilidad

#### 29. Listar Empresas (Público con Token Admin)
```
GET /empresas
```
**Headers:** `Authorization: Bearer <admin_token>`

#### 30. Debug Tokens OAuth2
```
GET /debug/oauth-tokens
```
**Headers:** `Authorization: Bearer <token>`

---

## Códigos de Respuesta HTTP

- **200 OK**: Operación exitosa
- **201 Created**: Recurso creado exitosamente
- **400 Bad Request**: Datos inválidos o faltantes
- **401 Unauthorized**: Token inválido o expirado
- **403 Forbidden**: Sin permisos para acceder al recurso
- **404 Not Found**: Recurso no encontrado
- **500 Internal Server Error**: Error interno del servidor

---
Para más detalles sobre la instalación, configuración y uso, consulta la documentación técnica o el código fuente del proyecto.