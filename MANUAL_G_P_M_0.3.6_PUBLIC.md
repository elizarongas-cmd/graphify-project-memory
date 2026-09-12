MANUAL DE GRAPHIFY + GRAPHIFY PROJECT MEMORY
Versión de referencia: Project Memory 0.3.6
Entorno principal: Windows
Ruta central de Project Memory:
C:\Tools\graphify-project-memory

============================================================
1. QUÉ TENEMOS
============================================================

El sistema está formado por cuatro piezas principales:

1. Git
2. Graphify
3. Graphify Project Memory (GPM)
4. AGENTS.md + documentación del proyecto

Cada una cumple una función diferente.

Git es la autoridad del código y del historial.
Graphify entiende la estructura del código y sus relaciones.
Project Memory mantiene el estado operativo del proyecto.
AGENTS.md contiene reglas para que Codex u otros agentes sepan cómo usar Graphify y Project Memory.

============================================================
2. PARA QUÉ SIRVE TODO EL SISTEMA
============================================================

El objetivo principal es poder entrar a un proyecto grande sin tener que volver a leer decenas o cientos de archivos cada vez.

El sistema permite:

- Saber dónde quedó el proyecto.
- Saber cuál es la tarea actual.
- Saber cuál es la siguiente acción.
- Recordar decisiones importantes.
- Registrar problemas pendientes.
- Guardar facts verificables con procedencia.
- Consultar relaciones del código mediante Graphify.
- Abrir únicamente los archivos necesarios.
- Reducir el contexto enviado al modelo.
- Detectar cuándo cambió realmente el código.
- Separar cambios del código de cambios de metadata.
- Crear checkpoints del estado del proyecto.
- Recuperar rápidamente el contexto después de días o semanas.
- Mantener trazabilidad usando Git.

============================================================
3. RESPONSABILIDAD DE CADA COMPONENTE
============================================================

GIT

Git conserva:

- Código fuente.
- Historial de cambios.
- Commits.
- Versiones recuperables.
- Evidencia real de lo que cambió.

Git sigue siendo la autoridad principal del código.

Project Memory nunca sustituye Git.

GRAPHIFY

Graphify analiza el proyecto y construye un grafo del código.

Sirve para conocer:

- Clases.
- Funciones.
- Métodos.
- Archivos.
- Dependencias.
- Relaciones.
- Rutas entre componentes.
- Elementos afectados por un cambio.
- Comunidades o áreas arquitectónicas.

Archivos principales:

graphify-out\graph.json
graphify-out\manifest.json
graphify-out\GRAPH_REPORT.md

PROJECT MEMORY

Project Memory mantiene la continuidad operacional.

Carpeta principal:

.project-memory

Puede contener:

config.json
baseline.json
state.json
facts.jsonl
decisions.jsonl
checkpoints.jsonl
issues.json
work-items.json
metrics.jsonl
graph-state.json
summaries\

AGENTS.MD

AGENTS.md contiene las reglas que deben seguir Codex u otros agentes.

Project Memory administra únicamente su bloque delimitado dentro de AGENTS.md.

El contenido humano fuera de ese bloque debe preservarse.

DOCUMENTACIÓN PÚBLICA Y EVOLUCIÓN

La documentación pública del proyecto se organiza en:

docs\ARCHITECTURE.md
    Explica la arquitectura, límites y responsabilidades entre Git, Graphify, Project Memory y el código fuente.

docs\DESIGN_RATIONALE.md
    Explica por qué se eligieron estas decisiones de diseño y qué capacidades se descartaron deliberadamente.

docs\project-memory\EVOLUTION.md
    Mantiene un historial técnico resumido y versionable de la evolución de Project Memory.

La documentación pública debe explicar el producto sin incluir notas internas, rutas privadas, credenciales ni detalles específicos de proyectos reales.

============================================================
4. ARQUITECTURA GENERAL
============================================================

Para una explicación pública más detallada de esta arquitectura consultar:

docs\ARCHITECTURE.md

y para las razones detrás de las decisiones de diseño:

docs\DESIGN_RATIONALE.md

La arquitectura correcta es:

Git
    autoridad del código y del historial

Graphify
    verdad estructural derivada del código

Project Memory
    verdad operacional y continuidad

Código fuente
    evidencia final cuando se necesita comprobar algo

Flujo normal:

Project Memory
    ↓
¿La memoria contiene suficiente información?
    ↓
Sí
    usar memoria

No
    ↓
Graphify
    ↓
buscar relaciones estructurales

Si todavía hace falta evidencia:
    ↓
abrir solamente rangos concretos del código fuente

============================================================
5. QUÉ SIGNIFICA RECUPERACIÓN ADAPTATIVA
============================================================

Cuando usamos:

gpm query "pregunta" --adaptive --project .

Project Memory intenta usar primero la memoria local.

Si la cobertura es suficiente, no necesita consultar Graphify ni abrir código.

Si la memoria no es suficiente:

1. Escala a Graphify.
2. Busca nodos relacionados.
3. Recupera relaciones.
4. Si hace falta, hidrata únicamente fragmentos concretos del código.

Esto evita leer todo el proyecto.

En pruebas reales con proyecto de audio de ejemplo se obtuvieron reducciones estimadas de contexto superiores al 95% en varias consultas.

Estas cifras son estimaciones locales de contexto evitado.
No equivalen necesariamente a tokens facturados por un proveedor de IA.

============================================================
6. INSTALACIÓN CENTRAL
============================================================

Si Project Memory está instalado desde una copia local, usa la ruta correspondiente. Ejemplo:

C:\Tools\graphify-project-memory

Antes de instalarlo en un proyecto nuevo, verificar:

gpm --version
graphify --help

============================================================
7. INSTALAR EN UN PROYECTO NUEVO
============================================================

Ejemplo:

gpm install --project "C:\Projects\example-project" --name "Nombre del proyecto" --with-graphify

La instalación debe:

- Crear .project-memory para ese proyecto.
- Crear o conectar Graphify.
- Integrar las reglas necesarias en AGENTS.md.
- Preservar el código existente.
- No copiar memoria de otros proyectos.
- No copiar decisiones de otros proyectos.
- No copiar checkpoints de otros proyectos.
- No crear commits automáticamente.
- Ser repetible sin duplicar reglas.
- Mantener separada la memoria de cada proyecto.

============================================================
8. VERIFICACIÓN DESPUÉS DE INSTALAR
============================================================

Ejecutar:

gpm doctor --project "C:\Projects\example-project"

Luego:

gpm status --project "C:\Projects\example-project"

Después:

gpm freshness --project "C:\Projects\example-project"

Y finalmente:

gpm query "¿Cuál es el estado actual del proyecto, cuál es la próxima acción y qué partes del código están relacionadas?" --adaptive --project "C:\Projects\example-project"

============================================================
9. ESTADO OPERACIONAL
============================================================

Project Memory mantiene:

- objective
- phase
- current_task
- next_action

Ejemplo:

gpm state --project . --phase "operational" --current-task "Implementar el nuevo flujo de generación de audio." --next-action "Revisar QueueService y ejecutar las pruebas relacionadas."

Después:

gpm status --project .

============================================================
10. FLUJO NORMAL DE TRABAJO
============================================================

Al comenzar una sesión:

cd /d C:\Projects\your-project

gpm status --project .

Si necesitas contexto:

gpm query "¿Qué necesito saber para continuar esta tarea?" --adaptive --project .

Después trabajar normalmente en el proyecto.

No es necesario crear facts, decisiones o checkpoints por cada cambio pequeño.

Registrar solamente información durable.

============================================================
11. GRAPHIFY WATCH
============================================================

Graphify incluye un watcher real.

Se inicia con:

graphify watch .

Ejemplo:

cd /d C:\Projects\example-audio-project

graphify watch .

Salida esperada:

[graphify watch] Watching C:\Projects\example-audio-project - press Ctrl+C to stop
[graphify watch] Code changes rebuild graph automatically.
[graphify watch] Debounce: 3.0s

Mientras esa consola permanezca abierta:

- Graphify vigila cambios de código.
- Espera aproximadamente 3 segundos.
- Reconstruye el grafo automáticamente.

La ventana donde corre watch debe dejarse abierta.

Para trabajar, abrir otra ventana de CMD.

IMPORTANTE

El watcher actualiza cambios de código.

Los cambios de documentos o imágenes pueden requerir una actualización explícita.

Para detenerlo:

Ctrl+C

============================================================
12. ACTUALIZACIÓN MANUAL DE GRAPHIFY
============================================================

Actualizar el grafo:

graphify update .

Graphify indica que update vuelve a extraer los archivos de código sin requerir LLM.

Después de cambios grandes puede usarse:

graphify update . --force

Usar --force principalmente después de refactors que eliminan mucho código o cuando el grafo necesita reconstruirse aunque resulte más pequeño.

============================================================
13. COMPROBAR SI GRAPHIFY NECESITA ACTUALIZACIÓN
============================================================

Graphify también incluye:

graphify check-update .

Este comando puede utilizarse para comprobar si existe una actualización semántica pendiente.

No es necesario ejecutar consultas de IA periódicamente solo para mantener el sistema vivo.

============================================================
14. PROJECT MEMORY NO NECESITA UN WATCHER CONSTANTE
============================================================

Project Memory no debe registrar automáticamente cada cambio.

Eso produciría ruido.

La estrategia correcta es:

Graphify watch
    automático para código

Project Memory
    actualizar en puntos importantes

Git
    commits cuando el usuario lo autorice

============================================================
15. FRESHNESS
============================================================

Comando:

gpm freshness --project .

Freshness determina si el contexto estructural sigue correspondiendo con el código fuente actual.

Ejemplo correcto:

fresh: true

reasons: []

source_file_count: 153

effective_source_revision:
<commit real de código>

Project Memory 0.3.6 utiliza un fingerprint del contenido fuente.

Los cambios internos de Project Memory no deberían marcar el código como cambiado.

============================================================
16. SOURCE_REVISION Y OBSERVED_HEAD
============================================================

Project Memory separa dos conceptos importantes.

source_revision

Commit que representa la última revisión real del código fuente.

observed_head

HEAD actual de Git.

Esto permite que un commit que solo cambia metadata no se interprete como un cambio real de código.

Ejemplo:

source_revision:
e65da25...

observed_head:
32f3815...

Si el contenido fuente no cambió, Project Memory puede mantener correctamente el source_revision anterior.

============================================================
17. FACTS
============================================================

Un fact es una afirmación verificable del proyecto.

Ejemplo:

QueueService
depends_on
WorkflowService

Agregar un fact:

gpm fact-add "QueueService" "depends_on" "WorkflowService" --project . --source "src/audio/audio_queue_service.py" --start-line 10 --end-line 25 --confidence 1.0

Otro ejemplo:

gpm fact-add "WorkflowService" "stores_audio_under" "audio-storage" --project . --source "src/audio/audio_workflow_service.py" --start-line 16 --end-line 23 --confidence 1.0

Listar facts:

gpm facts --project .

Validar facts:

gpm validate-facts --project .

Resultado saludable:

checked: 2
changed: []
conflicts: []

============================================================
18. PROVENANCE
============================================================

Cada fact puede guardar:

- source_revision
- path
- line_start
- line_end
- confidence
- observed_at

Esto permite saber exactamente de dónde salió la información.

============================================================
19. DECISIONES E ISSUES
============================================================

Registrar únicamente decisiones duraderas.

No convertir cada idea momentánea en una decisión.

Los issues deben representar problemas reales pendientes.

No registrar como issue:

- comentarios temporales
- dudas casuales
- hipótesis todavía no verificadas

============================================================
20. CHECKPOINTS
============================================================

Un checkpoint captura un estado operacional importante.

Ejemplo:

gpm checkpoint "Flujo de generación de audio validado y pruebas completadas." --project . --no-graphify

Usar --no-graphify cuando Graphify ya está actualizado.

No crear checkpoints continuamente.

Buenos momentos:

- cierre de una funcionalidad
- antes de cambiar de área importante
- después de una validación relevante
- antes de dejar el proyecto por varios días
- antes de una entrega

============================================================
21. CONSULTAS
============================================================

Consulta normal:

gpm query "¿Dónde quedamos?" --project .

Consulta adaptativa:

gpm query "¿Dónde quedamos y qué archivos están relacionados con la próxima tarea?" --adaptive --project .

Para una funcionalidad concreta:

gpm query "¿Qué necesito saber para trabajar en el flujo de generación final de audio?" --adaptive --project .

============================================================
22. MÉTRICAS Y REPORTES
============================================================

Según la instalación pueden utilizarse:

gpm metrics --project .

gpm report --project . --all

Permiten observar:

- tokens de memoria
- tokens de Graphify
- tokens de código hidratado
- contexto evitado
- porcentaje estimado de reducción
- número de expansiones
- cantidad de archivos hidratados

============================================================
23. GIT Y PROJECT MEMORY
============================================================

Git no debe ser sustituido por Project Memory.

Antes de commits importantes:

git status

Revisar cambios.

Después crear el commit únicamente con autorización explícita.

Ejemplo:

git add .

git commit -m "Estado canónico inicial: Example Project 1.0.0"

IMPORTANTE

Ese mensaje es solo un ejemplo.

Nunca crear un commit automáticamente ni reutilizar ese mensaje en otro proyecto sin verificar que corresponda.

============================================================
24. QUÉ ARCHIVOS CONVIENE VERSIONAR
============================================================

La política final depende del proyecto, pero normalmente conviene distinguir:

DURABLE / VERSIONABLE

.project-memory\config.json
.project-memory\baseline.json
.project-memory\state.json
.project-memory\facts.jsonl
.project-memory\decisions.jsonl
.project-memory\checkpoints.jsonl
.project-memory\issues.json
.project-memory\work-items.json
.project-memory\graph-state.json

graphify-out\graph.json
graphify-out\manifest.json
graphify-out\GRAPH_REPORT.md

AGENTS.md

docs\ARCHITECTURE.md
docs\DESIGN_RATIONALE.md
docs\project-memory\EVOLUTION.md

LOCAL / REGENERABLE

Caches
temporales
telemetría auxiliar
visualizaciones regenerables
copias pre-update
copias before-*
archivos runtime que no sean parte durable del proyecto

============================================================
25. RESPALDOS Y ZIP
============================================================

Para entregar un proyecto no es necesario copiar todos los caches.

Conservar principalmente:

graphify-out\graph.json
graphify-out\manifest.json
graphify-out\GRAPH_REPORT.md

.project-memory\
docs\ARCHITECTURE.md
docs\DESIGN_RATIONALE.md
docs\project-memory\EVOLUTION.md
AGENTS.md

Antes de compartir un ZIP revisar:

- credenciales
- tokens
- claves API
- datos personales
- audios privados
- bases de datos
- modelos grandes
- temporales

============================================================
26. QUÉ NO DEBE GUARDARSE EN PROJECT MEMORY
============================================================

No guardar:

- contraseñas
- API keys
- credenciales
- datos personales innecesarios
- audios completos
- modelos
- archivos temporales
- caches
- grandes blobs
- información especulativa presentada como hecho

============================================================
27. QUÉ HACER CUANDO REGRESAS A UN PROYECTO DESPUÉS DE DÍAS
============================================================

Paso 1:

cd /d C:\Projects\your-project

Paso 2:

gpm status --project .

Paso 3:

gpm freshness --project .

Paso 4:

gpm query "¿Dónde quedamos, qué está funcionando, qué problemas están pendientes y cuál es el siguiente paso?" --adaptive --project .

Paso 5:

Revisar solo los archivos que Project Memory y Graphify indiquen.

============================================================
28. FLUJO RECOMENDADO CON CODEX
============================================================

Antes de modificar código:

gpm status --project .

Después:

gpm query "Explica el contexto mínimo necesario para realizar esta tarea y qué archivos o símbolos están relacionados." --adaptive --project .

Codex debería:

1. Consultar memoria.
2. Consultar Graphify.
3. Abrir únicamente fuentes necesarias.
4. Modificar código.
5. Ejecutar pruebas.
6. Registrar decisiones duraderas si las hubo.
7. Registrar facts útiles si realmente aportan continuidad.
8. Crear checkpoint únicamente cuando corresponda.
9. No crear commits sin permiso.

============================================================
29. FLUJO CON GRAPHIFY WATCH ACTIVO
============================================================

VENTANA 1

cd /d C:\Projects\your-project

graphify watch .

Dejar esa ventana abierta.

VENTANA 2

cd /d C:\Projects\your-project

gpm status --project .

Trabajar normalmente.

Cuando Codex guarde código:

Graphify detecta el cambio.

Espera aproximadamente 3 segundos.

Actualiza el grafo.

La siguiente consulta de Project Memory puede utilizar el grafo actualizado.

============================================================
30. DIAGNÓSTICO RÁPIDO
============================================================

Si algo parece incorrecto:

gpm doctor --project .

gpm freshness --project .

gpm status --project .

git status

Para Graphify:

graphify --help

graphify check-update .

graphify diagnose multigraph

============================================================
31. REGLA DE ORO
============================================================

No leer todo el proyecto si no es necesario.

Primero:

Project Memory

Después:

Graphify

Finalmente:

Código fuente concreto

La cadena correcta es:

memoria
→ estructura
→ evidencia

============================================================
32. PROMPT UNIVERSAL PARA INSTALAR O VERIFICAR PROJECT MEMORY
============================================================

Configura, verifica y explica la integración de Graphify con Graphify Project Memory en este proyecto.

PROYECTO OBJETIVO:

C:\Projects\your-project

NOMBRE DEL PROYECTO:

NOMBRE DEL PROYECTO

REGLAS:

Busca primero graphify y gpm en PATH.

Si Project Memory está instalado desde una copia local, usa la ruta correspondiente. Ejemplo:

C:\Tools\graphify-project-memory

Comprueba:

- graphify-out\graph.json
- .project-memory\config.json
- AGENTS.md
- docs\ARCHITECTURE.md
- docs\DESIGN_RATIONALE.md
- docs\project-memory\EVOLUTION.md
- gpm doctor
- gpm freshness

No reinstales componentes que ya funcionen.

Si falta Project Memory:

gpm install --project "C:\Projects\your-project" --name "NOMBRE DEL PROYECTO" --with-graphify

La instalación debe:

- preservar código existente
- crear memoria exclusiva para el proyecto
- no copiar memoria de otros proyectos
- integrar AGENTS.md sin duplicados
- conectar Graphify
- no crear commits
- no guardar credenciales
- ser repetible

Después ejecutar:

gpm doctor --project "C:\Projects\your-project"

gpm status --project "C:\Projects\your-project"

gpm freshness --project "C:\Projects\your-project"

gpm query "¿Cuál es el estado actual, cuál es la próxima acción y qué partes del código están relacionadas?" --adaptive --project "C:\Projects\your-project"

Si todo funciona:

- registrar objetivo
- registrar phase
- registrar current_task
- registrar next_action
- importar únicamente decisiones verificadas
- crear un checkpoint inicial cuando corresponda

No inventar trabajo realizado.

No crear commits sin autorización explícita.

Al finalizar informar:

- versión detectada de gpm
- ubicación de Graphify
- existencia o creación del grafo
- existencia o creación de .project-memory
- resultado de doctor
- resultado de freshness
- estado registrado
- pruebas realizadas
- métricas si existen
- archivos modificados
- advertencias
- confirmación de que no se copiaron memorias externas
- confirmación de que no se creó ningún commit

============================================================
33. RESUMEN OPERATIVO
============================================================

INICIAR PROYECTO

cd /d C:\Projects\your-project

gpm status --project .

CONSULTAR CONTEXTO

gpm query "pregunta" --adaptive --project .

VERIFICAR SALUD

gpm doctor --project .

VERIFICAR SINCRONIZACIÓN

gpm freshness --project .

VIGILAR CÓDIGO AUTOMÁTICAMENTE

graphify watch .

ACTUALIZAR GRAPHIFY MANUALMENTE

graphify update .

COMPROBAR ACTUALIZACIÓN

graphify check-update .

LISTAR FACTS

gpm facts --project .

VALIDAR FACTS

gpm validate-facts --project .

CREAR CHECKPOINT

gpm checkpoint "Resumen del estado alcanzado." --project . --no-graphify

VER REPORTE

gpm report --project . --all

============================================================
34. ESTADO DE VALIDACIÓN DE LA VERSIÓN 0.3.6
============================================================

Versión de Project Memory:

0.3.6

La integración fue validada sobre proyectos reales de software antes de preparar esta versión pública.

Se comprobaron correctamente:

- freshness
- separación entre metadata y código fuente
- commits de metadata sin avance falso de source_revision
- detección de cambios reales de código
- restauración del estado fresh
- integración con Graphify
- recuperación adaptativa
- hidratación selectiva de código
- facts
- provenance
- validación de conflicts
- state operacional
- checkpoints
- continuidad
- métricas
- compatibilidad con Graphify watch

La evolución técnica de estas validaciones puede mantenerse en:

docs\project-memory\EVOLUTION.md

Graphify watch puede dejarse activo mientras se trabaja:

graphify watch .

Project Memory se actualiza de manera deliberada en puntos importantes.

No debe convertirse en un sistema que registre indiscriminadamente cada cambio pequeño.

============================================================
FIN DEL MANUAL
============================================================
