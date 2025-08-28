# 🧪 CHECKLIST MANUAL TESTING - STAGING

## 📋 LISTA DE VERIFICACIÓN MANUAL

### **FASE 1: ACCESO Y NAVEGACIÓN**

#### ✅ **Panel de Administración Básico**
- [ ] **Acceder a**: `https://clicandseo.up.railway.app/admin/users`
- [ ] **Verificar**: Se carga la página sin errores
- [ ] **Verificar**: Aparece la tabla de usuarios
- [ ] **Verificar**: Las estadísticas se muestran correctamente (Total, Activos, Inactivos, Hoy)

#### ✅ **Barras Progresivas de Cuotas**
- [ ] **Verificar**: Se muestran barras progresivas en la columna "Plan & Quota"
- [ ] **Verificar**: Las barras tienen colores correctos:
  - 🟢 Verde (0-74%): Uso normal
  - 🟡 Amarillo (75-89%): Advertencia
  - 🔴 Rojo (90-100%): Peligro
- [ ] **Verificar**: Los porcentajes se calculan correctamente
- [ ] **Verificar**: El texto muestra "X/Y RU" correctamente

---

### **FASE 2: MODAL "VER" MEJORADO**

#### ✅ **Abrir Modal de Usuario**
- [ ] **Hacer clic** en botón "Ver" de cualquier usuario
- [ ] **Verificar**: Modal se abre inmediatamente
- [ ] **Verificar**: Se muestran las 4 secciones:

#### 📋 **Sección 1: Información Básica**
- [ ] **Verificar**: ID, Nombre, Email, Rol, Estado, Registro, Autenticación
- [ ] **Verificar**: Todos los campos tienen datos válidos

#### 💳 **Sección 2: Plan y Facturación**
- [ ] **Verificar**: Plan Actual (ej: "Basic (29,99€)")
- [ ] **Verificar**: Estado de Facturación (ej: "✅ Activo")
- [ ] **Verificar**: Stripe Customer ID (puede ser "No configurado")
- [ ] **Verificar**: Período de Facturación (ej: "15/10/2024 - 15/11/2024")
- [ ] **Verificar**: Próxima Renovación (ej: "15/11/2024 (12 días)")

#### 📊 **Sección 3: Cuotas y Uso**
- [ ] **Verificar**: Límite de Cuota (ej: "1225 RU/mes")
- [ ] **Verificar**: Cuota Utilizada (ej: "150 RU")
- [ ] **Verificar**: Porcentaje de Uso (ej: "12.2%")
- [ ] **Verificar**: Reset de Cuota (fecha específica)
- [ ] **Verificar**: Barra progresiva en el modal con colores correctos

#### 👑 **Sección 4: Custom Quota (Enterprise)**
- [ ] **Verificar**: Solo aparece si el usuario tiene custom quota
- [ ] **Verificar**: Custom Limit, Notas, Asignado por, Fecha

---

### **FASE 3: FUNCIONALIDADES ADMIN**

#### ✅ **Gestión de Roles**
- [ ] **Hacer clic** en botón de editar rol (⚙️)
- [ ] **Verificar**: Modal se abre con opciones: Usuario, AI User, Administrador
- [ ] **Cambiar** rol de un usuario de prueba
- [ ] **Verificar**: Cambio se aplica y se refleja en la tabla

#### ✅ **Gestión de Estados**
- [ ] **Hacer clic** en botón de cambiar estado (🔄)
- [ ] **Verificar**: Modal se abre con opciones: Activo, Inactivo
- [ ] **Cambiar** estado de un usuario de prueba
- [ ] **Verificar**: Cambio se aplica y se refleja en la tabla

#### ✅ **Gestión de Planes**
- [ ] **Hacer clic** en botón "Change Plan" (🔄)
- [ ] **Verificar**: Modal se abre con opciones: Free, Basic, Premium
- [ ] **Cambiar** plan de un usuario de prueba
- [ ] **Verificar**: Cambio se refleja en la barra progresiva y modal

#### ✅ **Custom Quota (Enterprise)**
- [ ] **Hacer clic** en botón "Assign Custom Quota" (👑)
- [ ] **Verificar**: Modal se abre con campos para límite y notas
- [ ] **Asignar** custom quota a un usuario
- [ ] **Verificar**: Usuario se marca como "Enterprise" y cambia la barra progresiva

#### ✅ **Reset de Quota**
- [ ] **Verificar**: Botón "Reset Quota" aparece solo si quota_used > 0
- [ ] **Hacer clic** en "Reset Quota"
- [ ] **Verificar**: Confirmación se muestra
- [ ] **Confirmar** reset
- [ ] **Verificar**: Quota se resetea a 0 y barra progresiva se actualiza

---

### **FASE 4: RESPONSIVIDAD Y UX**

#### ✅ **Diseño Responsive**
- [ ] **Redimensionar** ventana del navegador
- [ ] **Verificar**: Tabla se adapta correctamente
- [ ] **Verificar**: Modales se adaptan a pantallas pequeñas
- [ ] **Verificar**: Barras progresivas mantienen proporciones

#### ✅ **Performance y Carga**
- [ ] **Recargar** página varias veces
- [ ] **Verificar**: Carga rápida (< 3 segundos)
- [ ] **Verificar**: No hay errores en consola del navegador
- [ ] **Verificar**: Barras progresivas se inicializan correctamente

#### ✅ **Funcionalidades JavaScript**
- [ ] **Abrir** consola del navegador (F12)
- [ ] **Verificar**: Mensaje "🚀 Admin Panel Simple cargado correctamente"
- [ ] **Verificar**: Mensaje "🔄 Inicializando barras progresivas de cuotas..."
- [ ] **Verificar**: No hay errores JavaScript

---

### **FASE 5: DATOS Y SINCRONIZACIÓN**

#### ✅ **Datos Reales vs Mostrados**
- [ ] **Seleccionar** un usuario específico
- [ ] **Anotar** sus datos en la tabla principal
- [ ] **Abrir** su modal "Ver"
- [ ] **Verificar**: Datos coinciden entre tabla y modal
- [ ] **Verificar**: Barra progresiva refleja el porcentaje real

#### ✅ **Sincronización con Base de Datos**
- [ ] **Cambiar** plan de un usuario
- [ ] **Recargar** página
- [ ] **Verificar**: Cambio persiste después de recarga
- [ ] **Verificar**: Barra progresiva se actualiza según nuevo plan

#### ✅ **Casos Edge**
- [ ] **Verificar** usuario con quota_limit = 0 (no debería mostrar barra)
- [ ] **Verificar** usuario con quota_used = 0 (barra en 0%)
- [ ] **Verificar** usuario con quota_used >= quota_limit (barra al 100% en rojo)

---

### **FASE 6: INTEGRACIÓN STRIPE**

#### ✅ **Datos de Stripe**
- [ ] **Seleccionar** usuario con datos de Stripe
- [ ] **Verificar** en modal "Ver":
  - Stripe Customer ID no está vacío
  - Período de facturación tiene fechas reales
  - Próxima renovación calcula días correctamente

#### ✅ **Estados de Facturación**
- [ ] **Verificar** diferentes estados se muestran correctamente:
  - ✅ Activo
  - 🆓 Período de prueba
  - ⚠️ Pago atrasado
  - ❌ Cancelado

---

## 📊 **CRITERIOS DE ÉXITO**

### ✅ **MÍNIMO PARA APROBAR:**
- [ ] Panel se carga sin errores
- [ ] Barras progresivas funcionan y muestran colores correctos
- [ ] Modal "Ver" muestra las 4 secciones
- [ ] Datos básicos se cargan desde base de datos
- [ ] No hay errores JavaScript críticos

### 🚀 **ÓPTIMO PARA PRODUCCIÓN:**
- [ ] Todos los tests de la lista anterior ✅
- [ ] Período de facturación específico funciona
- [ ] Custom quotas se gestionan correctamente  
- [ ] Sincronización con Stripe es visible
- [ ] Performance es fluida y responsive

---

## 🛠️ **TROUBLESHOOTING**

### **Si las barras progresivas no aparecen:**
1. Verificar consola del navegador para errores JavaScript
2. Verificar que `initializeQuotaProgressBars()` se ejecuta
3. Verificar que los datos `data-quota-percentage` están presentes

### **Si el modal "Ver" no carga datos de billing:**
1. Verificar que `/admin/users/<id>/billing-details` responde
2. Verificar que `admin_billing_panel.py` está disponible
3. Verificar conexión a base de datos

### **Si los datos no coinciden:**
1. Verificar que la ruta `/admin/users` usa `get_users_with_billing()`
2. Verificar que las columnas de billing existen en la base de datos
3. Verificar logs de Railway para errores

---

## 📋 **RESULTADO FINAL**

**Fecha de testing**: ___________  
**Testeado por**: ___________

**Resumen de resultados:**
- Tests pasados: _____ / _____
- Tests críticos pasados: _____ / _____
- Estado general: 🟢 Listo / 🟡 Necesita ajustes / 🔴 Requiere corrección

**Observaciones:**
_________________________________________________
_________________________________________________
_________________________________________________

**¿Aprobado para producción?** ☐ Sí  ☐ No

**Próximos pasos:**
_________________________________________________
_________________________________________________
