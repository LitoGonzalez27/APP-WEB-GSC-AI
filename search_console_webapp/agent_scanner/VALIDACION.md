# Validación del modelo contra la realidad (julio 2026)

Qué mide de verdad la nota del Agent-Ready Scanner, medido con datos y no con
criterio. Documento vivo: si repites los estudios, actualiza los números y la
fecha, y **no borres los resultados negativos** — son los que evitan que
volvamos a dar por bueno lo que no lo está.

Regla que ordena todo lo de abajo: **una nota que no se ha validado se presenta
como hipótesis, no como medida.**

## Qué mide esta herramienta y qué NO

Mide **preparación agéntica**, y solo eso: si un agente puede (1) alcanzar y
leer la web, (2) interpretarla lo bastante bien para actuar sobre ella, y (3)
operarla hasta completar una tarea.

**La visibilidad generativa —que una IA te cite en sus respuestas— NO es de esta
herramienta: es de Clicandseo.** Las dos se complementan y no se solapan. Esto
importa al juzgar los factores: aquí un factor solo se justifica por lo que
aporta al comportamiento agéntico. "Ayuda a que te encuentren" no es defensa
válida en este modelo, porque esa pregunta se responde en otro producto.

Consecuencia directa: C3 (datos estructurados) y C5 (contenido y confianza)
pesan el 40% del modelo y, contra las dos cosas que sabemos medir aquí, dan
−0,01 y 0,11. La coartada que les quedaba era la de visibilidad, y esa coartada
pertenece a otro producto.

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

**El error de diseño, y es mío: medí el tipo de interpretación equivocado.**
Pregunté "¿a qué se dedica esta empresa?", "¿cuál es su teléfono?". Eso es
interpretación ENCICLOPÉDICA, y a un agente no le sirve de nada. Por eso salió
con techo: es fácil.

Lo que un agente necesita interpretar es OPERATIVO: cuál de estos 40 enlaces es
el producto que busco; si este precio es el final o antes de impuestos, del
producto o de un accesorio; si mi clic funcionó y el artículo entró en el
carrito; si este botón avanza o abre un desplegable; si queda stock de esta
talla. Ahí es donde una web es clara o ambigua para un agente, ahí no debería
haber techo, y ahí es donde los datos estructurados tendrían su oportunidad
real de demostrar que sirven.

**"C3 no sirve" NO está demostrado.** Lo demostrado es "C3 no cambia la
extracción de hechos básicos", que es una pregunta que a un agente no le
importa. Queda pendiente el estudio 3.

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

## Estudio 3 — interpretación OPERATIVA (hecho, jul 2026)

**Método.** Se le da al modelo la lista de controles reales de la portada y se
le pide lo que hace un agente de compra en cada paso: elige el control que
pulsarías para avanzar hacia comprar, y **predice qué va a pasar** de una lista
cerrada (ficha_producto, listado_categoria, carrito, buscador, despliega_menu,
otra_pagina, no_pasa_nada). Después se pulsa de verdad y se clasifica lo que
ocurrió con esa misma lista. Se puntúa contra la **verdad observable** (URL
resultante y cambio de DOM), no contra criterio humano. Dos modelos.
25 dominios con al menos un clic verificable, de 37 lanzados.

**El instrumento SÍ separa**, al revés que el del estudio 2: acierto medio 46%
con desviación 42%, y dominios repartidos de 0% a 100%.

**Resultado principal, y es el dato de mercado de esta herramienta:**
**un modelo puntero acierta menos de la mitad de las veces qué va a pasar al
pulsar un control.** Ejemplos: hema.nl pulsa "bekijk je winkelmandje" esperando
el carrito y solo se abre un desplegable; rijksoverheid.nl pulsa el buscador y
no pasa nada; funda.nl y notion.com prometen una cosa y llevan a otra. Frente a
noel.es, gov.pl o stripe.com, donde los dos modelos aciertan siempre.

**Pero la nota tampoco predice esto.** Todo entre −0,12 y +0,17; NOTA GLOBAL
0,11. C3 (datos estructurados) da −0,12: **tercera medición distinta en la que
no aparece relación con el comportamiento agéntico.**

**Límite honesto de este estudio:** solo 1-2 clics por dominio, así que la nota
por sitio es 0 / 0,5 / 1, muy gruesa. Esa aspereza atenúa cualquier correlación
por construcción. El 46% agregado (sobre ~46 observaciones) es sólido; el
r=0,11 por dominio NO es concluyente. Para correlacionar de verdad hacen falta
~10 clics por dominio, en varias páginas, no uno en la portada.

**Otro límite, nuestro:** 12 de 37 dominios se cayeron, 5 de ellos porque el
navegador headless no vio ni un control (mango.com, coolblue.nl,
elcorteingles.es, sephora.es, pzu.pl). Mientras eso siga así, medimos sobre una
muestra sesgada hacia webs que no se protegen.

---

## Estudio 4 — interpretación operativa con muestra suficiente (jul 2026)

**Método.** El mismo del estudio 3, que ya demostró separar webs, pero en
RECORRIDO: cada modelo da 5 pasos seguidos y en cada uno predice qué pasará
antes de pulsar. Así los clics cubren portada → listado → ficha de forma
natural, que es el camino de "ChatGPT, entra y cómprame esto". Si un clic falla
se vuelve a la portada y se sigue, para no perder los pasos restantes.
**221 observaciones** sobre 24 dominios con >=4 clics cada uno.

**Fiabilidad de la medida: r=0,71 entre los dos modelos.** Coinciden bastante
sobre qué webs son claras, así que la medida no es ruido y el techo de
correlación es alto (~0,85). Esto importa: significa que si la nota no
correlaciona, no es porque el termómetro falle.

**Resultado principal — el dato de mercado de esta herramienta:**

> **Un modelo puntero acierta solo el 27% de las veces qué va a pasar al pulsar
> un control.** 221 clics reales, 24 webs reales.

Y separa muchísimo (desviación 32%): stripe.com y cloudflare.com aciertan el
100%, canva.com el 90%, noel.es el 80% — frente a 8 dominios en el 0%
(empik.com, funda.nl, gov.pl, hema.nl, komputronik.pl, mailchimp.com,
pccomponentes.com, uu.nl). Ahí es donde se pierde la venta agéntica.

**¿Predice la nota? Sigue sin poder afirmarse.** r=0,27 (Spearman 0,21) con
n=24: no se distingue de cero. Por categoría, C1 0,38 · C6 0,23 · C3 0,16 ·
C2 0,13 · C4 −0,07 · C5 −0,03. Ojo al vuelco: C4 era el mejor predictor de
completar la tarea (0,53) y aquí es el peor.

**Por qué este estudio TAMPOCO cierra la pregunta, y es culpa nuestra:** 13 de
37 dominios se quedaron sin una sola observación por un bug propio — el
descarte de banners de cookies exigía texto exacto de una palabra y no cerraba
"Godta alle" ni "Allow all cookies", así que el overlay interceptaba todos los
clics. Corregido después de medir (main `d7301ec`). **La muestra de 24 está
sesgada hacia webs cuyo banner sí cerrábamos, y la correlación hay que
recalcularla con el arreglo puesto antes de tocar los pesos.**

---

## Dónde está C3 después de cuatro medidas

| Estudio | Qué mide | r de C3 |
|---|---|---|
| 1 | Completar la tarea | −0,01 |
| 2 | Interpretación enciclopédica | −0,08 |
| 3 | Interpretación operativa (1 clic) | −0,12 |
| 4 | Interpretación operativa (221 clics) | **+0,16** |

Cuatro formas distintas de preguntarlo. La cuarta, que es la de mejor muestra,
por fin da positivo — pero flojo y sobre una submuestra sesgada. **Sigue sin estar
demostrado que C3 no sirva** (los estudios 2 y 3 tienen los límites que se
detallan arriba), pero pesa 20 sobre 100 y no ha aparecido ni una vez. Es el
primer candidato a revisar cuando haya datos para repesar.
