# Validación del modelo contra la realidad (julio 2026)

Qué mide de verdad la nota del Agent-Ready Scanner, medido con datos y no con
criterio. Documento vivo: si repites los estudios, actualiza los números y la
fecha, y **no borres los resultados negativos** — son los que evitan que
volvamos a dar por bueno lo que no lo está.

Regla que ordena todo lo de abajo: **una nota que no se ha validado se presenta
como hipótesis, no como medida.**

---

## Estudio 1 — ¿La nota predice que un agente pueda USAR la web?

**Método.** 29 dominios lanzados, 21 medibles. Dos agentes reales (OpenAI y
Google) intentando la tarea propia de cada tipología, 2 pasadas cada uno
(4 muestras por dominio). Variable de resultado: fracción de hitos de la tarea
alcanzados. `allow_submit=False` en todos: no se envía nada a terceros.

El check 6.3 NO entra en el cálculo de la nota, así que no hay circularidad:
la nota y el resultado del agente son independientes.

**Correlación nota ↔ éxito del agente**

| Muestra | n | Pearson |
|---|---|---|
| SaaS | 10 | 0,29 (0,49 excluyendo límites de método) |
| E-commerce | 7 | 0,63 (0,23 excluyendo límites de método) |
| Global | 21 | 0,41 |

**Por categoría** (n=21, contra el éxito del agente):

| Categoría | Peso | r |
|---|---|---|
| C4 Renderizado y velocidad | 17 | **0,53** |
| C1 Descubribilidad y acceso | 18 | **0,46** |
| C6 Superficie agéntica | 15 | 0,30 |
| C2 Control de bots | 10 | 0,18 |
| C5 Contenido y confianza | **20** | 0,11 |
| C3 Datos estructurados | **20** | **−0,01** |

**Conclusión.** La nota distingue los extremos (cloudflare.com 81,8 → 100% de
recorrido; noel.es 16,0 → 25%) pero **no ordena bien el medio de la tabla**, que
es donde cae casi todo cliente. Las dos categorías de mayor peso —40% del
modelo— son las que menos relación tienen con completar la tarea.

---

## Estudio 2 — ¿La nota predice que una IA te INTERPRETE bien?

**Método, y por qué así.** No se le pregunta al modelo qué sabe de la marca: eso
mediría notoriedad (cloudflare es famosa, noel.es vende jamón) y no calidad
técnica. Se le da **exactamente lo que la web sirve a un rastreador** y se le
piden 5 hechos de negocio, obligándole a responder NO CONSTA si el contenido no
lo sostiene. Dos modelos independientes, 36 dominios.

Tres métricas: **extracción** (cuántos hechos saca), **acuerdo** (¿los dos
modelos extraen el mismo valor? si discrepan, la web es ambigua para una IA) y
**anclaje** (¿el dato aparece literalmente en lo servido, o se lo ha inventado?).

**Resultado: nada predice nada.** Todas las correlaciones entre −0,25 y +0,22.

| Variable | media | NOTA GLOBAL | C3 Datos estructurados |
|---|---|---|---|
| Acuerdo entre modelos | 90% | 0,12 | −0,08 |
| Anclaje (no se lo inventa) | 90% | −0,13 | −0,24 |
| Extracción de hechos | 78% | −0,05 | 0,07 |

**Por qué sale plano, y esto es lo interesante.** Hay **efecto techo**: los LLM
actuales extraen hechos de negocio de HTML crudo casi con independencia de la
calidad técnica del sitio, en webs que van de 15 a 82 puntos. Para la
interpretación *básica*, los datos estructurados aportan mucho menos de lo que
el sector —y nuestro modelo— asumen.

**Lo que este estudio NO demuestra.** Mide extracción de hechos básicos, que es
fácil. No mide lo difícil: que te citen en una respuesta generativa, que los
atributos de tu producto salgan correctos en una comparativa, que te distingan
de un competidor con nombre parecido. **"C3 no sirve" NO está demostrado**; lo
demostrado es "C3 no cambia la extracción de hechos básicos".

**Señal secundaria útil:** el anclaje sí caza alucinación donde el contenido es
pobre. asana.com y coolblue.nl dieron 0% (el modelo se inventó precio/contacto);
coolblue sirve una cáscara de 257 bytes y el modelo rellenó el hueco con memoria
propia. elcorteingles.es y rijksoverheid.nl bajaron al 33% de acuerdo: los dos
modelos extrajeron valores distintos, o sea que son ambiguos para una IA.

---

## Qué se puede afirmar hoy, y qué no

**Se puede afirmar:**
- La nota separa lo muy bueno de lo muy malo.
- Acceso y renderizado (C1, C4) son lo que más se relaciona con que un agente
  complete la tarea.
- La medición con agentes es fiable: dos modelos independientes coinciden.

**NO se puede afirmar:**
- Que la nota ordene correctamente el tramo medio.
- Que los datos estructurados y el contenido (40% del peso) aporten a ninguno
  de los dos resultados que sabemos medir hoy.
- Nada sobre visibilidad generativa real (citas en respuestas de IA): **no se ha
  medido nunca**.

## Antes de repesar factores (no hacerlo aún)

1. n=21 y n=36 son pequeños: un r=0,4 ahí tiene un margen enorme (grosso modo
   de 0 a 0,7). Diferencias como 0,53 vs 0,30 **no son distinguibles**.
2. Probando combinaciones sobre los mismos datos aparecen correlaciones altas
   (C1+C4 dio 0,57). Es selección sobre la muestra y **no aguanta con datos
   nuevos**. Cualquier repesado necesita conjunto de validación aparte.
3. La mitad de las tiendas grandes es inmedible (8 de 16 bloquean), así que la
   muestra de e-commerce está sesgada hacia las que no se protegen.

## Bugs que salieron de validar, ya corregidos

Validar salió a cuenta aunque el modelo no se confirmara:

- El check 6.3 acusaba a la web cuando el bloqueo era nuestro (mango.com servía
  "Access Denied" al navegador y lo registrábamos como fallo del sitio).
- SaaS de manual (asana, canva, monday) clasificados "corporativo", lo que
  además les daba la TAREA equivocada en el 6.3.
- Gemini perdía el 39% de sus pasos por un presupuesto de salida corto (los
  modelos que razonan gastan tokens pensando del mismo saco), y la web pagaba
  ese "no conseguido".
- El panel comparativo coronaba a la mejor de dos tipologías con varas
  distintas.

## Cómo reproducir

Los scripts de los estudios no viven en el repo (son de análisis, no de
producto). Lo que hay que rehacer:

1. Nota + agentes reales por dominio (`audit_domain` + `run_agent_tests` con
   `allow_submit=False`), 2 proveedores × 2 pasadas.
2. Correlación de la nota y de cada categoría contra la fracción de hitos.
3. Estudio de interpretación: corpus servido → 5 hechos → acuerdo y anclaje.

Descartar siempre, y contarlo: dominios sin nota (bloqueo total), intentos
`no_verificable` y los marcados `limite_de_metodo`.
