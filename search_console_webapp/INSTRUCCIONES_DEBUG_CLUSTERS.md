# 🔍 INSTRUCCIONES PARA DEBUG DE CLUSTERS

## 📋 PASOS A SEGUIR:

### 1️⃣ Abre la Consola del Navegador
- Presiona F12 o Click derecho > Inspeccionar
- Ve a la pestaña "Console"
- **LIMPIA la consola** (botón 🚫 o click derecho > Clear console)

### 2️⃣ Abre tu Proyecto
- En Manual AI, haz click en el proyecto que tiene clusters configurados
- Espera a que cargue

### 3️⃣ Ve al Tab Analytics
- Click en "Analytics"
- Espera a que termine de cargar

### 4️⃣ Busca en la Consola estos Logs:
Deberías ver algo como:
```
📊 Loading clusters statistics for project 17, days: 30
📦 Clusters statistics result: {...}
```

### 5️⃣ Comparte:

**A) Logs de la CONSOLA del navegador** (todo lo que aparece)

**B) Logs del SERVIDOR** desde el momento que abres el proyecto

Específicamente busca estas líneas en el servidor:
```
GET /manual-ai/api/projects/XX/clusters/statistics?days=30
```

Y también:
```
📋 Clusters config for project XX: enabled=...
📊 Found X keywords with results...
✅ Returning cluster statistics: ...
```

---

## 🎯 LO QUE NECESITO VER:

1. ¿Se está llamando al endpoint de statistics?
2. ¿Qué devuelve el backend?
3. ¿Hay algún error en la consola del navegador?
4. ¿Los logs del backend muestran que encuentra keywords?

---

## 💡 TAMBIÉN PRUEBA ESTO:

Abre directamente en tu navegador esta URL (reemplaza XX por tu project ID):

```
https://tu-dominio.com/manual-ai/api/projects/XX/clusters
```

Y comparte qué te devuelve (debería ser un JSON con enabled: true)

