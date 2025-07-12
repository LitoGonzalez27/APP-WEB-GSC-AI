# Sistema de Autenticación y Registro - Clicandseo

## 🚀 Características Implementadas

### ✅ Sistema Completo de Autenticación
- **Registro manual** con email y contraseña
- **Registro con Google OAuth**
- **Login manual** con validación
- **Login con Google OAuth**
- **Sistema de sesiones** con expiración por inactividad
- **Protección de rutas** con decoradores personalizados

### ✅ Base de Datos PostgreSQL
- **Tabla users** con todos los campos necesarios
- **Índices optimizados** para consultas rápidas
- **Gestión de contraseñas** con hash seguro (PBKDF2)
- **Soporte para Google OAuth** con google_id

### ✅ Roles y Permisos
- **Rol de usuario** (`user`) - Acceso básico
- **Rol de administrador** (`admin`) - Gestión completa
- **Decorador `@auth_required`** - Requiere autenticación
- **Decorador `@admin_required`** - Requiere privilegios admin

### ✅ Control de Acceso
- **Verificación de cuenta activa** (`is_active`)
- **Bloqueo de usuarios inactivos** por defecto
- **Redirección automática** según estado de cuenta
- **Gestión de usuarios suspendidos**

## 🏗️ Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND                                 │
├─────────────────────────────────────────────────────────────────┤
│  /login          │  /signup         │  /dashboard  │  /admin/   │
│  - Login manual  │  - Registro      │  - Panel     │  - Gestión │
│  - Google OAuth  │  - Google OAuth  │  - Usuario   │  - Admin   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       BACKEND (Flask)                          │
├─────────────────────────────────────────────────────────────────┤
│  auth.py                    │  app.py                          │
│  - Decoradores             │  - Rutas protegidas              │
│  - Gestión de sesiones     │  - Lógica de negocio            │
│  - OAuth & Manual auth     │  - APIs                         │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   DATABASE (PostgreSQL)                        │
├─────────────────────────────────────────────────────────────────┤
│  database.py                │  Tabla: users                   │
│  - Conexiones              │  - id, email, name, role        │
│  - Operaciones CRUD        │  - password_hash, google_id     │
│  - Funciones de auth       │  - is_active, timestamps        │
└─────────────────────────────────────────────────────────────────┘
```

## 📋 Rutas Implementadas

### 🔐 Autenticación
- `GET /login` - Página de inicio de sesión
- `POST /login` - Login manual con email/contraseña
- `GET /signup` - Página de registro
- `POST /signup` - Registro manual
- `GET /auth/login` - Inicio de sesión con Google
- `GET /auth/callback` - Callback de Google OAuth
- `POST /auth/complete-google-signup` - Completar registro con Google
- `POST /auth/logout` - Cerrar sesión

### 📊 Paneles de Usuario
- `GET /dashboard` - Panel principal del usuario
- `GET /admin/users` - Panel de administración (solo admin)

### 🔧 APIs de Administración
- `POST /admin/users/<id>/toggle-status` - Activar/desactivar usuario
- `POST /admin/users/<id>/update-role` - Cambiar rol de usuario

### 📈 APIs de Estado
- `GET /auth/status` - Estado de autenticación
- `POST /auth/keepalive` - Mantener sesión activa
- `GET /auth/user` - Información del usuario actual

## 🛠️ Instalación y Configuración

### 1. Instalar Dependencias
```bash
pip install -r requirements.txt
```

### 2. Configurar Variables de Entorno
```bash
# En tu archivo .env o variables de entorno
DATABASE_URL=postgresql://postgres:password@host:port/database
FLASK_SECRET_KEY=tu-clave-secreta-aqui
GOOGLE_REDIRECT_URI=http://localhost:5001/auth/callback
```

### 3. Inicializar Base de Datos
```bash
python init_database.py
```

### 4. Ejecutar la Aplicación
```bash
python app.py
```

## 👤 Usuario Administrador Inicial

Al ejecutar `init_database.py`, se crea automáticamente un usuario administrador:

- **Email**: `admin@clicandseo.com`
- **Contraseña**: `admin123456`
- **Rol**: `admin`
- **Estado**: `activo`

**⚠️ IMPORTANTE**: Cambiar la contraseña en producción.

## 🔒 Flujo de Autenticación

### 📝 Registro de Usuario

#### Registro Manual:
1. Usuario visita `/signup`
2. Llena formulario (nombre, email, contraseña)
3. Sistema crea usuario con `is_active = FALSE`
4. Usuario debe hacer login después del registro

#### Registro con Google:
1. Usuario hace clic en "Registrarse con Google"
2. Redirige a Google OAuth
3. Al regresar, si el usuario no existe, va a `/signup`
4. Sistema crea usuario con datos de Google
5. Usuario debe hacer login después del registro

### 🔑 Inicio de Sesión

#### Login Manual:
1. Usuario visita `/login`
2. Ingresa email y contraseña
3. Sistema valida credenciales
4. Si `is_active = FALSE`, muestra mensaje de cuenta suspendida
5. Si `is_active = TRUE`, redirige a `/dashboard`

#### Login con Google:
1. Usuario hace clic en "Continuar con Google"
2. Redirige a Google OAuth
3. Al regresar, sistema busca usuario por `google_id` o `email`
4. Si existe y está activo, redirige a `/dashboard`
5. Si no existe, redirige a `/signup`

## 🛡️ Seguridad Implementada

### 🔐 Contraseñas
- **Hash seguro**: PBKDF2 con salt aleatorio
- **Iteraciones**: 100,000 para mayor seguridad
- **Validación**: Mínimo 8 caracteres

### 🕐 Sesiones
- **Expiración**: 45 minutos de inactividad
- **Actualización automática**: En cada petición válida
- **Limpieza**: Sesiones expiradas se eliminan automáticamente

### 🔍 Validaciones
- **Email único**: No se permiten duplicados
- **Verificación de estado**: Usuarios inactivos no pueden acceder
- **Protección CSRF**: Tokens de estado en OAuth
- **Sanitización**: Limpieza de inputs

## 🎯 Comportamiento del Sistema

### 🚫 Usuarios Inactivos
- **Registro**: Todos los usuarios inician como `is_active = FALSE`
- **Acceso**: No pueden acceder a rutas protegidas
- **Mensaje**: "Tu cuenta está suspendida. Contacta con soporte."
- **Activación**: Solo administradores pueden activar cuentas

### 👑 Administradores
- **Gestión completa**: Pueden activar/desactivar usuarios
- **Cambio de roles**: Pueden hacer admin a otros usuarios
- **Panel especial**: Acceso a `/admin/users`
- **Estadísticas**: Ven métricas de usuarios del sistema

### 🔄 Flujo de Estados
```
Registro → is_active: FALSE → Admin activa → is_active: TRUE → Acceso completo
```

## 📱 Responsive Design

### 📱 Mobile-First
- **Formularios optimizados** para dispositivos móviles
- **Navegación adaptativa** que se oculta en pantallas pequeñas
- **Botones táctiles** con tamaño adecuado
- **Validación en tiempo real** para mejor UX

### 🎨 Componentes UI
- **Pestañas de registro** (Manual/Google)
- **Notificaciones toast** para feedback
- **Modales responsivos** para administración
- **Tablas adaptativas** que se convierten en cards

## 🔧 Mantenimiento

### 📊 Monitoreo
- **Logs detallados** de autenticación
- **Métricas de usuarios** en panel admin
- **Tracking de registros** diarios/semanales

### 🗄️ Base de Datos
- **Respaldos automáticos** (configurar en Railway)
- **Índices optimizados** para consultas rápidas
- **Limpieza de sesiones** expiradas

## 🚀 Próximas Mejoras

### 💳 Integración con Stripe
- **Suscripciones**: Activación automática tras pago
- **Webhooks**: Actualización de estado de cuenta
- **Planes**: Diferentes niveles de acceso

### 📧 Notificaciones
- **Email de bienvenida** tras registro
- **Recordatorios** de cuenta inactiva
- **Notificaciones** de cambios de seguridad

### 🔐 Seguridad Avanzada
- **2FA**: Autenticación de dos factores
- **Rate limiting**: Prevención de ataques de fuerza bruta
- **Audit logs**: Registro de todas las acciones

## 📞 Soporte

Si tienes problemas con el sistema de autenticación:

1. Verifica que PostgreSQL esté ejecutándose
2. Confirma que las variables de entorno están configuradas
3. Ejecuta `python init_database.py` para reinicializar
4. Revisa los logs en consola para errores específicos

**¡Tu sistema de autenticación está listo y es production-ready!** 🎉 