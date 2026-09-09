"""Shared Spanish learning content; no simulation or diagnostic decisions.

Equations below describe the existing model conventions for reading only.
Dynamic interpretations remain owned by learning and guided_learning.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LearningBlock:
    """One ordered teaching unit; kind describes presentation, never scoring."""

    kind: str
    text: str

    def __post_init__(self) -> None:
        if self.kind not in {
            "intuition", "explanation", "equation", "example",
            "key-idea", "reflection", "experiment",
        }:
            raise ValueError("Unknown learning block kind")
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("Learning block text must be non-empty")


@dataclass(frozen=True)
class TheoryTopic:
    """Ordered lesson with explicit prerequisites and experiment links."""

    topic_id: str
    title: str
    learning_objective: str
    blocks: tuple[LearningBlock, ...]
    prerequisite_topic_ids: tuple[str, ...] = ()
    case_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class DisplayQuantity:
    key: str
    label: str
    symbol: str
    unit: str
    description: str
    disclosure: str = "basic"


@dataclass(frozen=True)
class TermDefinition:
    key: str
    label: str
    description: str


@dataclass(frozen=True)
class CaseGuidance:
    case_id: str
    concept: str
    topic_ids: tuple[str, ...]
    observe: str
    intervene: str
    compare: str
    explain: str
    remember: str
    experimental_question: str
    prediction_guidance: str


@dataclass(frozen=True)
class LearningStep:
    label: str
    description: str
    destination: str
    target_id: str


# Stable IDs connect lessons and experiments without importing the case engine.
TOPICS = (
    TheoryTopic(
        "before-starting", "Antes de comenzar",
        "Entender qué pregunta investiga el laboratorio y cómo empezar a explorarla.",
        (
            LearningBlock(
                "intuition",
                "Imagina un generador entregando potencia a la red. Una perturbación grande cambia "
                "bruscamente lo que puede entregar; su rotor sigue en movimiento. La pregunta es si "
                "recupera una relación de giro coordinada con la red o continúa adelantándose respecto de "
                "ella."
            ),
            LearningBlock(
                "explanation",
                "La estabilidad transitoria estudia la capacidad de conservar el sincronismo después de "
                "una perturbación grande. SincroLab observa el primer avance y posible retorno del ángulo "
                "relativo del rotor. Más adelante aprenderás por qué ese diagnóstico de primera "
                "oscilación tiene un alcance limitado."
            ),
            LearningBlock(
                "key-idea",
                "Esta ruta es para estudiantes que cursan o cursaron Sistemas de Potencia. Basta recordar "
                "circuitos, potencia, frecuencia, sistemas trifásicos y la idea de generador; aquí "
                "construiremos los conceptos de estabilidad. No necesitas consultar una fuente externa "
                "para comenzar el primer caso."
            ),
            LearningBlock(
                "example",
                "Una menor capacidad de entregar potencia durante una falla puede hacer que el rotor gane "
                "velocidad. Despejar la falla cambia las condiciones eléctricas, pero no borra de "
                "inmediato el movimiento que ya adquirió. Ese encadenamiento es lo que experimentarás."
            ),
            LearningBlock(
                "reflection",
                "Si las condiciones eléctricas se recuperan, ¿por qué convendría observar también el "
                "movimiento que llevaba el rotor? No necesitas responder todavía: conserva la pregunta "
                "durante la ruta."
            ),
            LearningBlock(
                "experiment",
                "Lee el recordatorio y sigue hasta primera oscilación; después abre el Caso 1 y sus "
                "repasos. Observarás la configuración, registrarás una predicción, simularás, "
                "interpretarás, cambiarás un parámetro y compararás antes de explicar. Son casos "
                "sintéticos educativos, no estudios operacionales ni un simulador general de redes "
                "reales."
            ),
        ),
        case_ids=("first-swing-event-evidence",),
    ),
    TheoryTopic(
        "synchronous-generator", "Recordatorio: generador síncrono y sincronismo",
        "Relacionar el giro del rotor con la frecuencia sin confundir sincronismo con ángulo cero.",
        (
            LearningBlock(
                "intuition",
                "La turbina hace girar el rotor, la parte móvil del generador. El estator permanece fijo "
                "y contiene devanados en los que se entrega la potencia eléctrica. El campo magnético "
                "asociado al rotor cambia su orientación respecto del estator al girar."
            ),
            LearningBlock(
                "explanation",
                "En operación síncrona, el giro del campo del rotor y la variación eléctrica trifásica "
                "mantienen una relación determinada por el número de pares de polos. La frecuencia cuenta "
                "ciclos eléctricos por segundo; no necesariamente vueltas mecánicas del eje por segundo. "
                "La velocidad mecánica correspondiente a la frecuencia de red se llama velocidad "
                "síncrona."
            ),
            LearningBlock(
                "example",
                "Con un par de polos, una vuelta mecánica corresponde a un ciclo eléctrico; con dos "
                "pares, a dos ciclos. El ángulo eléctrico cuenta ese avance del campo. Este recordatorio "
                "no añade polos como parámetro: SincroLab trabaja directamente con ángulos y velocidades "
                "eléctricos."
            ),
            LearningBlock(
                "key-idea",
                "Permanecer en sincronismo significa mantener una relación angular acotada con la "
                "referencia de red, admitiendo oscilaciones transitorias. En equilibrio la velocidad "
                "relativa es cero, pero la separación angular puede ser distinta de cero: dos agujas que "
                "avanzan a la misma rapidez pueden conservar un desfase."
            ),
            LearningBlock(
                "reflection",
                "Si dos referencias avanzan a igual rapidez con una separación inicial, ¿esa separación "
                "tiene que desaparecer? ¿Estaría detenido alguno de los movimientos?"
            ),
            LearningBlock(
                "experiment",
                "Antes del Caso 1, pasa al modelo de red grande y al ángulo relativo. Luego comprueba que "
                "una velocidad relativa nula antes de la falla puede coexistir con un ángulo del rotor "
                "distinto de cero."
            ),
        ),
        ("before-starting",), ("first-swing-event-evidence",),
    ),
    TheoryTopic(
        "smib", "Una máquina conectada a una red grande: SMIB",
        "Entender qué representa la barra infinita y qué referencia ofrece al rotor.",
        (
            LearningBlock(
                "intuition",
                "Una máquina pequeña frente al conjunto de una red muy grande puede cambiar su propia "
                "respuesta sin alterar apreciablemente la tensión ni la frecuencia del conjunto. El "
                "modelo ideal lleva esa aproximación al extremo: la red conserva ambas magnitudes."
            ),
            LearningBlock(
                "explanation",
                "SMIB significa una máquina conectada a una barra infinita (Single Machine Infinite Bus). "
                "Una barra es un nodo eléctrico. Infinita describe su rigidez ideal frente a esta "
                "máquina, no una red de tamaño físico infinito: la magnitud de tensión y la frecuencia se "
                "fijan y su fase avanza a la velocidad síncrona."
            ),
            LearningBlock(
                "key-idea",
                "La red no gira como un objeto sólido. Lo que avanza es la fase de sus tensiones "
                "alternas, que usamos como referencia angular. El rotor sí gira físicamente; compararemos "
                "su posición eléctrica con esa referencia."
            ),
            LearningBlock(
                "example",
                "Si la referencia es de 60 Hz, sus tensiones completan 60 ciclos eléctricos cada segundo "
                "aunque el generador tenga una pequeña desviación transitoria de velocidad. En este "
                "modelo esa máquina no modifica los 60 Hz de la barra infinita."
            ),
            LearningBlock(
                "explanation",
                "El modelo clásico conserva dos estados: ángulo relativo y desviación de velocidad. "
                "Mantiene constante la potencia mecánica y resume la transferencia eléctrica con una "
                "curva potencia–ángulo por etapa. Así aísla el movimiento del rotor sin simular otras "
                "máquinas, reguladores o la dinámica electromagnética completa."
            ),
            LearningBlock(
                "reflection",
                "Si la referencia eléctrica sigue avanzando uniformemente y el rotor se adelanta un poco, "
                "¿qué variable debería registrar esa separación?"
            ),
            LearningBlock(
                "experiment",
                "Los tres casos comparten este modelo. En el Caso 1, identifica la frecuencia base en la "
                "configuración avanzada y conserva esta referencia al leer ángulo y velocidad."
            ),
        ),
        ("synchronous-generator",), ("first-swing-event-evidence",),
    ),
    TheoryTopic(
        "quantities", "Las magnitudes que utilizarás",
        "Distinguir entradas, estados y escalas antes de leer las ecuaciones.",
        (
            LearningBlock(
                "intuition",
                "Para seguir el movimiento necesitamos saber qué potencia entra, cuál sale y cómo "
                "responde el rotor. Normalizar las magnitudes permite comparar valores respecto de una "
                "misma base sin cargar cada cálculo con la escala nominal de la máquina."
            ),
            LearningBlock(
                "explanation",
                "Por unidad (pu) significa valor dividido por su base. Pm es potencia mecánica de entrada "
                "al eje y Pe potencia eléctrica activa entregada; ambas usan una base común. Pmax es la "
                "amplitud equivalente de la curva de transferencia eléctrica, no la potencia que sale en "
                "todo instante."
            ),
            LearningBlock(
                "example",
                "Sobre una base de potencia de 100 MVA, una potencia activa de 70 MW es 0.70 pu. Aquí "
                "hablamos de potencia activa: 0.70 pu de Pm o Pe corresponde a 70 MW en esa base, no a "
                "una afirmación sobre factor de potencia. La base es ilustrativa, no un dato adicional de "
                "los casos."
            ),
            LearningBlock(
                "explanation",
                "δ mide una separación angular eléctrica, en radianes. Δω mide desviación de velocidad "
                "respecto de la referencia, en pu. H mide la energía cinética nominal por potencia base, "
                "en segundos; D relaciona desviación de velocidad con potencia amortiguante. Los próximos "
                "temas construyen su significado dinámico."
            ),
            LearningBlock(
                "key-idea",
                "El tiempo t y los instantes de inicio y despeje se expresan en segundos. Δt es el paso "
                "numérico solicitado para calcular muestras: no es la duración de la falla. Parámetros "
                "como H o Pm describen el experimento; δ y Δω describen el estado que va evolucionando."
            ),
            LearningBlock(
                "reflection",
                "Si Pe vale 0.50 pu y Pm 0.70 pu en la misma base, ¿entra más potencia de la que sale? "
                "¿Qué parte móvil podría acumular esa diferencia?"
            ),
            LearningBlock(
                "experiment",
                "En la configuración del Caso 1, reconoce símbolos y unidades. Consulta el glosario "
                "cuando lo necesites; el valor de δ no está en grados y Δω no está en vueltas por minuto."
            ),
        ),
        ("smib",), ("first-swing-event-evidence",),
    ),
    TheoryTopic(
        "rotor-angle", "¿Qué significa el ángulo del rotor?",
        "Explicar por qué δ puede permanecer constante mientras el rotor sigue girando.",
        (
            LearningBlock(
                "intuition",
                "Piensa en dos agujas que giran: una representa la posición eléctrica del rotor y otra la "
                "fase de la red. Si ambas avanzan igual, la separación permanece constante aunque las dos "
                "sigan moviéndose. Es una intuición para comparar posiciones, no un modelo mecánico de la "
                "red."
            ),
            LearningBlock(
                "explanation",
                "El ángulo mecánico cuenta el giro del eje; el eléctrico cuenta el avance asociado a sus "
                "pares de polos. δ es la posición angular eléctrica del rotor relativa a la referencia "
                "síncrona de la barra infinita. Interesa cuánto se adelanta o atrasa, no el número "
                "acumulado de vueltas absolutas. El núcleo usa radianes."
            ),
            LearningBlock(
                "key-idea",
                "Δω = 0 no significa rotor detenido: significa que su velocidad eléctrica coincide con la "
                "referencia síncrona. Puede haber δ constante y distinto de cero. Con Δω > 0, δ aumenta; "
                "con Δω < 0, δ disminuye. Una disminución de δ describe movimiento relativo, no invertir "
                "necesariamente el giro del eje."
            ),
            LearningBlock(
                "explanation",
                "Llamamos ω a la velocidad angular eléctrica del rotor y ωs a la síncrona, ambas en "
                "rad/s. La frecuencia base f está en Hz. Δω expresa la diferencia de velocidades "
                "normalizada por ωs; la derivada de δ mide cuán rápido cambia la separación, en rad/s."
            ),
            LearningBlock(
                "equation",
                "ωs = 2πf; Δω = (ω − ωs) / ωs; dδ/dt = ωs · Δω."
            ),
            LearningBlock(
                "example",
                "Con f = 50 Hz y Δω = 0.01 pu en un instante, dδ/dt = π rad/s, aproximadamente 3.14 "
                "rad/s. Si Δω pasa a cero, la pendiente de δ se anula en ese instante; el rotor continúa "
                "a velocidad síncrona."
            ),
            LearningBlock(
                "reflection",
                "Si Δω todavía es positiva pero cada vez menor, ¿δ ya disminuye o sigue aumentando con "
                "una pendiente menor?"
            ),
            LearningBlock(
                "experiment",
                "En el Caso 1, lee juntas δ(t) y Δω(t). Predice la pendiente del ángulo a partir del "
                "signo de la velocidad relativa antes de buscar el diagnóstico."
            ),
        ),
        ("synchronous-generator", "smib", "quantities"), ("first-swing-event-evidence",),
    ),
    TheoryTopic(
        "power-angle", "Equilibrio antes de una perturbación",
        "Relacionar transferencia eléctrica y equilibrio inicial compatible.",
        (
            LearningBlock(
                "intuition",
                "Antes de provocar una falla queremos que el movimiento observado no provenga de un "
                "desequilibrio inicial accidental. Si la entrada mecánica iguala la salida eléctrica y no "
                "hay velocidad relativa, no hay razón para que el estado cambie en ese instante."
            ),
            LearningBlock(
                "explanation",
                "La potencia eléctrica depende del ángulo relativo. La curva potencia–ángulo del modelo "
                "es un seno cuya amplitud es Pmax. Al movernos por la parte creciente del seno aumenta "
                "Pe; después del máximo disminuye. La intersección con la potencia mecánica fija señala "
                "un posible equilibrio."
            ),
            LearningBlock(
                "equation",
                "Pe(δ) = Pmax · sen(δ). En equilibrio: Pm = Pe y Δω = 0. El estado inicial compatible usa "
                "δ₀ = arcsen(Pm / Pmax prefalla), en la rama principal."
            ),
            LearningBlock(
                "explanation",
                "La relación inicial exige Pmax prefalla > 0 y |Pm / Pmax prefalla| ≤ 1. Fuera de ese "
                "dominio no hay un ángulo inicial compatible por esta fórmula. El diagnóstico de primera "
                "oscilación exige además 0 < Pm < Pmax posfalla; las fronteras de ese intervalo no "
                "pertenecen a su régimen soportado."
            ),
            LearningBlock(
                "example",
                "En un ejemplo de equilibrio con Pm = 0.50 pu y Pmax prefalla = 1.00 pu, δ₀ = π/6 rad y "
                "Pe = 0.50 pu. Ese ángulo no es cero; aun así Δω = 0 y las dos derivadas son nulas. No es "
                "un resultado anticipado de ningún caso guiado."
            ),
            LearningBlock(
                "reflection",
                "Si Pm supera la amplitud máxima de la curva prefalla, ¿podrías encontrar una "
                "intersección aumentando el ángulo indefinidamente?"
            ),
            LearningBlock(
                "experiment",
                "Revisa el estado inicial del Caso 1 y las muestras anteriores a la falla. Los casos "
                "parten de un equilibrio compatible. El modo libre conserva el estado inicial mostrado; "
                "modificar una entrada no significa recalcular automáticamente un nuevo equilibrio."
            ),
        ),
        ("quantities", "rotor-angle"), ("first-swing-event-evidence",),
    ),
    TheoryTopic(
        "swing-equation", "Del desequilibrio de potencia al movimiento",
        "Seguir la cadena potencia → velocidad relativa → ángulo y formalizarla.",
        (
            LearningBlock(
                "intuition",
                "La turbina entrega potencia mecánica al rotor y el generador entrega potencia eléctrica "
                "a la red. Si momentáneamente entra más de la que sale, el excedente puede aumentar la "
                "energía cinética del rotor; si sale más, puede reducirla. La velocidad no cambia de "
                "golpe: cambia su ritmo de evolución."
            ),
            LearningBlock(
                "explanation",
                "Sin amortiguamiento, Pm > Pe hace aumentar Δω y Pm < Pe la hace disminuir. Pa nombra esa "
                "diferencia antes de amortiguamiento. Con D distinto de cero hay que incluir también la "
                "potencia D · Δω para obtener el balance neto que gobierna la aceleración."
            ),
            LearningBlock(
                "explanation",
                "H es energía cinética a velocidad nominal dividida por potencia base, en segundos: "
                "expresa cuánta energía está asociada al giro nominal en esa escala. D tiene unidades de "
                "pu de potencia por pu de desviación de velocidad. Con D > 0 su efecto se opone a la "
                "desviación; con Δω = 0 su contribución es cero."
            ),
            LearningBlock(
                "equation",
                "Pa = Pm − Pe; dΔω/dt = (Pm − Pe − D · Δω) / (2H); dδ/dt = ωs · Δω."
            ),
            LearningBlock(
                "example",
                "En un instante con Pm = 0.70 pu, Pe = 0.50 pu, Δω = 0 y H = 4 s, el balance neto es 0.20 "
                "pu y dΔω/dt = 0.025 pu/s. Inicialmente la pendiente de δ es cero, pero al crecer Δω el "
                "ángulo empieza a aumentar. No se ha predicho aún la estabilidad de toda la trayectoria."
            ),
            LearningBlock(
                "key-idea",
                "Un H mayor reduce la magnitud de la derivada de velocidad para el mismo balance neto "
                "instantáneo; no garantiza estabilidad de una trayectoria completa. D = 0 elimina "
                "amortiguamiento. El contrato admite D negativo, que no debe interpretarse como "
                "amortiguamiento disipativo."
            ),
            LearningBlock(
                "reflection",
                "Después del despeje, ¿basta un balance neto negativo para que δ disminuya "
                "inmediatamente, si Δω aún es positiva?"
            ),
            LearningBlock(
                "experiment",
                "En los Casos 1 y 3, conecta el balance con el cambio de Δω y este con la pendiente de δ. "
                "Usa las muestras y la explicación calculada para comprobar tu interpretación; un signo "
                "instantáneo no sustituye el diagnóstico de eventos."
            ),
        ),
        ("rotor-angle", "power-angle"), ("first-swing-event-evidence", "controlled-inertia-effect"),
    ),
    TheoryTopic(
        "fault-stages", "¿Qué hace una falla?",
        "Reconstruir la evolución prefalla, falla y posfalla sin reiniciar el rotor en el despeje.",
        (
            LearningBlock(
                "intuition",
                "Una falla puede reducir bruscamente la capacidad de entregar potencia eléctrica mientras "
                "la entrada mecánica continúa. El rotor empieza a acumular el efecto del desequilibrio "
                "durante el tiempo que persiste esa condición."
            ),
            LearningBlock(
                "explanation",
                "Prefalla usa una amplitud Pmax; la falla usa otra y el despeje activa la amplitud "
                "posfalla, que puede diferir de la original. En cada etapa Pe sigue la curva de esa red "
                "al ángulo actual. Pm permanece constante. Estos Pmax equivalentes representan una "
                "perturbación pedagógica, no un cálculo completo de cortocircuito."
            ),
            LearningBlock(
                "example",
                "En un instante con δ = π/6 rad, bajar Pmax de 1.00 a 0.40 pu cambia Pe de 0.50 a 0.20 pu "
                "sin cambiar instantáneamente δ. Si Pm = 0.50 pu y Δω = 0, aparece un balance acelerante "
                "positivo. Al avanzar el estado, Pe también puede variar dentro de la misma etapa."
            ),
            LearningBlock(
                "key-idea",
                "Cambiar Pmax puede cambiar Pe y la aceleración de golpe, pero δ y Δω permanecen "
                "continuos en inicio y despeje. Despejar no devuelve el rotor a su estado inicial: la "
                "posfalla parte del ángulo y la velocidad alcanzados. Incluso si empieza a desacelerar, "
                "puede seguir adelantándose."
            ),
            LearningBlock(
                "explanation",
                "Inicio y despeje ocurren en los tiempos especificados; la integración se divide en esos "
                "eventos. El instante de despeje se mide desde el origen temporal. La duración de la "
                "falla es despeje menos inicio de falla, no el valor del despeje por sí solo."
            ),
            LearningBlock(
                "reflection",
                "Si mantienes la misma red en falla durante más tiempo, ¿qué dos estados debes comparar "
                "justo al despejar para razonar sobre la posfalla?"
            ),
            LearningBlock(
                "experiment",
                "En el Caso 2, modifica solo el despeje después de un primer intento. Compara cuánto "
                "evoluciona el rotor durante la falla y el movimiento con que entra en posfalla, sin "
                "suponer de antemano un resultado."
            ),
        ),
        ("power-angle", "swing-equation"), ("late-clearing-bracket", "first-swing-event-evidence"),
    ),
    TheoryTopic(
        "first-swing", "Primera oscilación: reversión y cruce",
        "Comprender por qué el orden de eventos permite un diagnóstico limitado de primera oscilación.",
        (
            LearningBlock(
                "intuition",
                "Tras el despeje el rotor puede seguir adelantándose aunque ya esté perdiendo velocidad "
                "relativa. Para la primera excursión interesa saber si ese avance se frena y empieza a "
                "retornar antes de llegar a la frontera angular que examina el modelo."
            ),
            LearningBlock(
                "explanation",
                "Con 0 < Pm < Pmax posfalla hay dos intersecciones principales de Pm con la curva "
                "posfalla. La de menor ángulo está en la rama creciente. La de mayor ángulo está en la "
                "rama decreciente: más allá, aumentar δ reduce Pe en esa rama, por lo que el balance sin "
                "amortiguamiento favorece más avance. Es el equilibrio inestable asociado que usa el "
                "criterio, no una frontera universal de 180°."
            ),
            LearningBlock(
                "equation",
                "δ estable posfalla = arcsen(Pm / Pmax posfalla); δ inestable posfalla = π − δ estable "
                "posfalla. Son ángulos eléctricos en radianes."
            ),
            LearningBlock(
                "explanation",
                "Primera excursión positiva significa el primer tramo posfalla examinado con Δω > 0 y δ "
                "creciente. Reversión (reversal) es el paso muestreado de Δω > 0 a Δω ≤ 0: deja de "
                "avanzar respecto de la red; no significa que el eje invierta su giro. Cruce (crossing) "
                "es el paso que alcanza el equilibrio inestable desde un ángulo inferior."
            ),
            LearningBlock(
                "example",
                "Si dos muestras pasan de Δω = 0.003 a −0.001 pu mientras δ permanece bajo la frontera "
                "relevante, contienen una reversión. Si en ese mismo par también se alcanza la frontera, "
                "las muestras solas no indican qué ocurrió primero. Este ejemplo no describe el resultado "
                "de un caso del catálogo."
            ),
            LearningBlock(
                "key-idea",
                "Estable: reversión antes del cruce. Inestable: cruce antes de una reversión, con Δω "
                "positiva en ambas muestras del cruce. Se conservan únicamente intervalos de muestras "
                "adyacentes, sin interpolación. Estable aquí no demuestra estabilidad global, asintótica "
                "ni de oscilaciones posteriores."
            ),
            LearningBlock(
                "explanation",
                "No concluyente: falta excursión positiva, termina la ventana antes del evento o el orden "
                "es ambiguo. Si cruce y reversión comparten par, no se adivina su orden continuo. Tampoco "
                "se resuelve si la primera muestra de excursión positiva ya alcanza la frontera. No "
                "concluyente es un resultado científico válido, no un estado que deba convertirse a "
                "estable o inestable."
            ),
            LearningBlock(
                "reflection",
                "¿Por qué un máximo angular aparentemente pequeño no basta para clasificar si la ventana "
                "terminó antes de observar alguno de los eventos?"
            ),
            LearningBlock(
                "experiment",
                "Ya puedes abrir el Caso 1. Repasa allí qué observar y registra una predicción razonada "
                "sobre el orden posible de eventos. Después contrástala con el diagnóstico y los "
                "intervalos de evidencia avanzada, y explica una diferencia respecto de tu predicción."
            ),
        ),
        ("rotor-angle", "power-angle", "fault-stages"), ("first-swing-event-evidence",),
    ),
    TheoryTopic(
        "clearing-time", "Tiempo de despeje y transición crítica",
        "Interpretar el CCT como transición acotada entre dos tiempos evaluados.",
        (
            LearningBlock(
                "intuition",
                "Terminar la falla en otro instante cambia cuánto ha evolucionado el rotor y con qué "
                "ángulo y velocidad entra en posfalla. Por eso dos ejecuciones con la misma máquina y "
                "redes pueden presentar distinto orden de eventos al cambiar solo el despeje."
            ),
            LearningBlock(
                "explanation",
                "CCT significa tiempo crítico de despeje. Para acotar una transición, la búsqueda "
                "necesita un tiempo menor evaluado como estable y otro mayor evaluado como inestable. Ese "
                "par se llama intervalo de acotación o bracket. La bisección prueba el punto medio y "
                "sustituye el extremo con el mismo diagnóstico; así conserva la acotación."
            ),
            LearningBlock(
                "equation",
                "t estable < t inestable; ancho = t inestable − t estable. Los tiempos se expresan en "
                "segundos desde el origen de la simulación."
            ),
            LearningBlock(
                "example",
                "Si un intervalo hipotético tiene ancho 0.008 s, probar su punto medio y obtener un "
                "diagnóstico estable o inestable permite conservar una mitad de ancho 0.004 s. Es una "
                "ilustración del algoritmo, no tiempos ni resultados de un caso. Una evaluación no "
                "concluyente no se fuerza a otro estado para continuar."
            ),
            LearningBlock(
                "key-idea",
                "El resultado conserva ambos extremos evaluados y sus diagnósticos; el punto medio no es "
                "un CCT físico exacto. La tolerancia de búsqueda es exclusivamente el criterio de parada "
                "de bisección. No es incertidumbre física, barra de error ni estimación del error de "
                "integración. Un intervalo estrecho no demuestra convergencia respecto al paso temporal."
            ),
            LearningBlock(
                "explanation",
                "El criterio de áreas iguales (EAC) compara energía angular acelerante y desacelerante "
                "bajo hipótesis compatibles del modelo clásico, entre ellas ausencia de amortiguamiento. "
                "Puede aportar un ángulo crítico por una ruta analítica separada. Los casos guiados "
                "actuales tienen amortiguamiento: no se les aplica esa fórmula ni se convierte "
                "automáticamente un ángulo crítico en un tiempo."
            ),
            LearningBlock(
                "reflection",
                "Si la búsqueda termina con un intervalo estrecho pero la trayectoria se calculó con un "
                "paso grueso, ¿qué aspecto todavía necesitas comprobar?"
            ),
            LearningBlock(
                "experiment",
                "En el Caso 2, compara la ejecución inicial y una intervención en despeje. Lee los dos "
                "extremos del intervalo calculado junto con el diagnóstico; no elijas un ajuste "
                "suponiendo que el punto medio sea una solución exacta."
            ),
        ),
        ("fault-stages", "first-swing"), ("late-clearing-bracket",),
    ),
    TheoryTopic(
        "inertia", "Inercia y respuesta transitoria",
        "Separar el efecto instantáneo de H de una conclusión sobre toda la trayectoria.",
        (
            LearningBlock(
                "intuition",
                "Ante el mismo desequilibrio neto, una mayor reserva de energía cinética nominal hace más "
                "lento el cambio de velocidad relativa. Esto ofrece una forma de explorar la escala "
                "temporal del movimiento, sin cambiar la potencia que entra ni la curva eléctrica."
            ),
            LearningBlock(
                "explanation",
                "Compara dos ejecuciones que solo difieren en H. Al separarse sus estados también pueden "
                "diferir Pe y el término de amortiguamiento; por tanto no puedes suponer el mismo balance "
                "en todos los instantes solo porque las entradas de potencia y red se mantengan."
            ),
            LearningBlock(
                "equation",
                "Para el mismo balance neto instantáneo, dΔω/dt es proporcional a 1/H en dΔω/dt = (Pm − "
                "Pe − D · Δω) / (2H)."
            ),
            LearningBlock(
                "example",
                "Con un balance neto de 0.16 pu, H = 4 s da una derivada de velocidad de 0.02 pu/s y H = "
                "8 s da 0.01 pu/s. La comparación vale en ese instante y bajo el mismo balance; no "
                "establece el máximo angular ni la clasificación posterior."
            ),
            LearningBlock(
                "key-idea",
                "Mayor H no garantiza siempre estabilidad. Compara forma de δ(t), forma de Δω(t), máximos "
                "de ángulo y de desviación absoluta de velocidad en la misma ventana, además del "
                "diagnóstico cuando corresponda. Los máximos de toda la ventana no son automáticamente "
                "métricas de la primera oscilación."
            ),
            LearningBlock(
                "reflection",
                "Si dos trayectorias terminan en el mismo diagnóstico, ¿podría aun así observarse un "
                "efecto de la inercia? ¿Qué métricas lo mostrarían?"
            ),
            LearningBlock(
                "experiment",
                "En el Caso 3 puedes editar únicamente H. Conserva potencia, amortiguamiento, frecuencia, "
                "redes, tiempos de evento, estado inicial, horizonte y paso. Predice una comparación de "
                "trayectorias; después explica qué muestran las métricas reales, sin imponer una regla "
                "universal de estabilidad."
            ),
        ),
        ("swing-equation", "fault-stages", "first-swing"), ("controlled-inertia-effect",),
    ),
    TheoryTopic(
        "time-step", "Simulación numérica y paso temporal",
        "Distinguir resolución de trayectoria y parada de búsqueda, y razonar sobre convergencia.",
        (
            LearningBlock(
                "intuition",
                "El ordenador aproxima un movimiento continuo calculando estados en instantes sucesivos. "
                "Unir esos puntos produce una curva, pero el detalle que podemos distinguir depende de "
                "las muestras y del método de integración."
            ),
            LearningBlock(
                "explanation",
                "Δt es el paso temporal solicitado. Euler avanza usando la pendiente al inicio del paso; "
                "RK4 combina cuatro evaluaciones de pendiente para aproximar el avance. SincroLab "
                "implementa ambos métodos; las ejecuciones transitorias de Desktop y Web usan RK4 propio, "
                "sin reemplazarlo por SciPy."
            ),
            LearningBlock(
                "example",
                "Con Δt = 0.01 s, un evento situado 0.006 s después de una muestra obliga a terminar el "
                "tramo allí. El solver no desplaza el evento a la siguiente marca nominal. Integra "
                "prefalla, falla y posfalla por separado y conserva un solo estado continuo en la "
                "frontera."
            ),
            LearningBlock(
                "key-idea",
                "Paso temporal (dt_s) ≠ tolerancia de búsqueda (time_tolerance_s). El primero determina "
                "la resolución de integración; la segunda decide cuándo parar la bisección entre tiempos "
                "de despeje. Ninguno es por sí solo incertidumbre física. Los intervalos de "
                "reversión/cruce usan muestras, sin localizar raíces entre ellas."
            ),
            LearningBlock(
                "explanation",
                "Para estudiar convergencia, reduce Δt manteniendo controladas las demás entradas y "
                "cuantifica cuánto cambian trayectorias, métricas y diagnóstico. Cerca del límite, "
                "refinar puede resolver un orden de eventos ambiguo. Una curva suave o una tolerancia de "
                "búsqueda pequeña no prueban convergencia; un horizonte corto tampoco se arregla solo "
                "reduciendo el paso."
            ),
            LearningBlock(
                "reflection",
                "¿Qué cambiarías para observar durante más tiempo? ¿Y para tener muestras más próximas? "
                "¿Cuál de esos cambios estrecha directamente el criterio de parada de bisección?"
            ),
            LearningBlock(
                "experiment",
                "Después del Caso 2, identifica paso y tolerancia en la evidencia avanzada. Para explorar "
                "el paso usa el modo libre y registra las diferencias entre ejecuciones con las demás "
                "entradas iguales; los casos guiados conservan sus restricciones de edición."
            ),
        ),
        ("fault-stages", "first-swing", "clearing-time"), ("late-clearing-bracket",),
    ),
    TheoryTopic(
        "reading-plots", "Cómo leer las gráficas",
        "Transformar las curvas y la evidencia de eventos en una explicación física.",
        (
            LearningBlock(
                "intuition",
                "Leer ambas curvas juntas permite distinguir posición relativa, rapidez del avance y "
                "cambio de esa rapidez. Una sola imagen de δ puede ocultar si el rotor todavía se "
                "adelanta o ya empezó a retornar."
            ),
            LearningBlock(
                "explanation",
                "1. Lee el eje horizontal: tiempo en segundos. 2. Identifica inicio de falla y despeje en "
                "la configuración y ubica esos tiempos en las curvas. 3. Lee δ(t), en radianes, y Δω(t), "
                "en pu, para los mismos instantes. Una ordenada de velocidad cero significa velocidad "
                "síncrona, no rotor parado."
            ),
            LearningBlock(
                "example",
                "Si Δω pasa de 0.004 a 0.002 pu, sigue positiva: δ continúa aumentando aunque su "
                "pendiente disminuya. Cuando Δω llega a cero, la pendiente del ángulo se anula; la "
                "reversión muestreada registra el paso a velocidad relativa no positiva."
            ),
            LearningBlock(
                "explanation",
                "4. Busca la reversión y el posible cruce de la frontera posfalla en la evidencia "
                "avanzada. Compara sus intervalos adyacentes; las líneas dibujadas solo unen muestras, no "
                "dan un tiempo continuo exacto. No confundas el instante de despeje, que es una entrada, "
                "con esos eventos observados."
            ),
            LearningBlock(
                "key-idea",
                "5. Para comparar dos ejecuciones, lee los campos modificados y conserva la configuración "
                "inicial original. Distingue el diagnóstico de primera oscilación de los máximos "
                "reportados para toda la ventana. 6. Explica el cambio con la cadena Pm y Pe → balance "
                "neto → Δω → δ → orden de eventos, usando valores calculados."
            ),
            LearningBlock(
                "reflection",
                "Si aumenta el máximo angular de la ventana pero el primer evento sigue siendo una "
                "reversión antes del cruce, ¿por qué no debes cambiar el diagnóstico por tu cuenta?"
            ),
            LearningBlock(
                "experiment",
                "En el Caso 1 contrasta tu predicción con curvas y evidencia; cambia el despeje y explica "
                "qué cambió respecto del primer intento. En el Caso 3 compara también las dos métricas de "
                "ventana. Puedes volver a este tema desde la preparación de cada caso."
            ),
        ),
        ("rotor-angle", "swing-equation", "first-swing"), ("first-swing-event-evidence", "controlled-inertia-effect"),
    ),
    TheoryTopic(
        "limitations", "Limitaciones del laboratorio",
        "Delimitar qué puede sostener una conclusión del experimento.",
        (
            LearningBlock(
                "intuition",
                "Un modelo simplificado permite aislar causas y comprenderlas. Esa claridad depende de "
                "mantener a la vista qué fenómenos se dejaron fuera; una respuesta convincente del "
                "laboratorio no describe por sí sola una planta real."
            ),
            LearningBlock(
                "explanation",
                "Este es un modelo clásico SMIB con barra infinita y potencia mecánica constante. No "
                "representa dinámica multimáquina, reguladores de excitación o velocidad ni un estudio "
                "operacional. Cambiar Pmax no sustituye un estudio completo de cortocircuito o "
                "protección."
            ),
            LearningBlock(
                "example",
                "Una primera oscilación clasificada estable sostiene una afirmación sobre esa excursión y "
                "las muestras disponibles. No demuestra estabilidad asintótica, de oscilaciones "
                "posteriores ni de una red distinta."
            ),
            LearningBlock(
                "key-idea",
                "Las soluciones guiadas son intervenciones sintéticas posibles para aprender; no son "
                "ajustes de relés ni recomendaciones para operar una planta. La interpretación debe "
                "indicar modelo, entradas, ventana y resolución. Una comparación numérica consistente "
                "respalda ese caso, no validez universal."
            ),
            LearningBlock(
                "reflection",
                "Al explicar tu intento, ¿qué evidencia pertenece al resultado calculado y qué afirmación "
                "quedaría fuera de las hipótesis del modelo?"
            ),
            LearningBlock(
                "experiment",
                "Cierra cada caso conectando lo que cambiaste con las métricas y respondiendo la pregunta "
                "conceptual final. Puedes equivocarte, volver a predecir y repetir; tus intentos "
                "permanecen locales. Los libros sirven para profundizar, no son un requisito para "
                "completar esta ruta."
            ),
        ),
        ("smib", "first-swing", "clearing-time", "time-step"),
        ("first-swing-event-evidence", "late-clearing-bracket", "controlled-inertia-effect"),
    ),
)

BLOCK_LABELS = (
    TermDefinition("intuition", "Intuición física", ""),
    TermDefinition("explanation", "Construye la idea", ""),
    TermDefinition("equation", "Representación matemática", ""),
    TermDefinition("example", "Ejemplo breve", ""),
    TermDefinition("key-idea", "Idea clave", ""),
    TermDefinition("reflection", "Antes de continuar, piensa", ""),
    TermDefinition("experiment", "Conexión con el laboratorio", ""),
)

QUANTITIES = (
    DisplayQuantity("H_s", "Inercia del generador", "H", "s", "Constante de inercia del rotor."),
    DisplayQuantity("D_pu", "Coeficiente de amortiguamiento", "D", "pu/pu", "Potencia amortiguante por unidad de desviación de velocidad.", "advanced"),
    DisplayQuantity("f_base_hz", "Frecuencia base", "f", "Hz", "Frecuencia eléctrica de la referencia síncrona.", "advanced"),
    DisplayQuantity("Pm_pu", "Potencia mecánica", "Pm", "pu", "Potencia constante que entra al rotor."),
    DisplayQuantity("delta_rad", "Ángulo del rotor", "δ", "rad", "Ángulo eléctrico relativo a la barra infinita."),
    DisplayQuantity("omega_dev_pu", "Desviación de velocidad", "Δω", "pu", "Desviación relativa respecto a la velocidad síncrona."),
    DisplayQuantity("Pmax_prefault_pu", "Transferencia máxima prefalla", "Pmax", "pu", "Amplitud de la curva potencia–ángulo antes de la falla."),
    DisplayQuantity("Pmax_fault_pu", "Transferencia máxima durante la falla", "Pmax", "pu", "Amplitud equivalente durante la falla; no modela un cortocircuito completo."),
    DisplayQuantity("Pmax_postfault_pu", "Transferencia máxima posfalla", "Pmax", "pu", "Amplitud de la curva tras el despeje."),
    DisplayQuantity("t_fault_s", "Inicio de la falla", "t falla", "s", "Instante en que comienza la red en falla."),
    DisplayQuantity("t_clear_s", "Despeje de la falla", "t despeje", "s", "Instante desde el origen temporal; no duración de falla."),
    DisplayQuantity("t_start_s", "Inicio de simulación", "t inicio", "s", "Origen de la ventana simulada.", "advanced"),
    DisplayQuantity("t_end_s", "Fin de simulación", "t fin", "s", "Límite de la ventana disponible para observar eventos."),
    DisplayQuantity("dt_s", "Paso temporal", "Δt", "s", "Paso solicitado de integración, distinto de la tolerancia de búsqueda.", "advanced"),
    DisplayQuantity("time_s", "Tiempo", "t", "s", "Instante de cada muestra."),
    DisplayQuantity("stable_t_clear_s", "Extremo estable de despeje", "t estable", "s", "Tiempo evaluado con primera oscilación estable."),
    DisplayQuantity("unstable_t_clear_s", "Extremo inestable de despeje", "t inestable", "s", "Tiempo evaluado con primera oscilación inestable."),
    DisplayQuantity("bracket_width_s", "Ancho del intervalo", "ancho", "s", "Separación entre extremos evaluados."),
    DisplayQuantity("time_tolerance_s", "Tolerancia de búsqueda", "tol", "s", "Criterio de parada de bisección; no incertidumbre física.", "advanced"),
    DisplayQuantity("iterations", "Iteraciones de búsqueda", "N", "", "Evaluaciones intermedias realizadas por bisección.", "advanced"),
    DisplayQuantity("max_delta_rad", "Máximo ángulo en la ventana", "máx δ", "rad", (
        "Máximo de todas las muestras de la ventana, no necesariamente de la primera "
        "oscilación."
    )),
    DisplayQuantity("max_abs_omega_dev_pu", "Máxima desviación absoluta en la ventana", "máx |Δω|", "pu", "Máximo valor absoluto de desviación de velocidad en la ventana."),
)

GLOSSARY = (
    TermDefinition("synchronous-generator", "Generador síncrono", "Máquina cuyo giro eléctrico se relaciona con la frecuencia de red; el rotor es móvil y el estator permanece fijo."),
    TermDefinition("smib", "SMIB · una máquina y una barra infinita", "Modelo de un generador conectado a una red ideal de tensión y frecuencia fijas."),
    TermDefinition("speed-deviation", "Δω · desviación de velocidad", "Diferencia entre velocidad eléctrica del rotor y velocidad síncrona, dividida por la síncrona. Cero significa igual velocidad, no rotor detenido."),
    TermDefinition("damping", "D · amortiguamiento", "Coeficiente de la potencia D · Δω. Para D positivo se opone a la desviación; no altera el significado de Pa antes de amortiguamiento."),
    TermDefinition("time-step", "Δt · paso temporal", "Separación solicitada para integrar la trayectoria; puede acortarse en los eventos y el final. No es duración de falla ni tolerancia de búsqueda."),
    TermDefinition("search-tolerance", "Tolerancia de búsqueda", "Ancho de parada solicitado para el intervalo de bisección; no es incertidumbre física ni precisión de la trayectoria."),
    TermDefinition("pu", "pu · por unidad", (
        "Valor dividido por su base de referencia; las potencias del modelo usan una base "
        "común."
    )),
    TermDefinition("delta", "δ · ángulo del rotor", "Ángulo eléctrico relativo a la barra infinita, en radianes."),
    TermDefinition("omega", "ω · velocidad eléctrica", (
        "Velocidad angular eléctrica. ωs es la referencia síncrona, en rad/s; Δω es la "
        "desviación relativa en pu."
    )),
    TermDefinition("inertia", "H · inercia", "Energía cinética nominal dividida por potencia base, en segundos."),
    TermDefinition("mechanical-power", "Pm · potencia mecánica", "Potencia de entrada constante al rotor, en pu."),
    TermDefinition("electrical-power", "Pe · potencia eléctrica", "Potencia transferida según Pmax · sen(δ), en pu."),
    TermDefinition("transfer", "Pmax · transferencia máxima", (
        "Amplitud equivalente de la curva de potencia eléctrica de cada estado de red, en pu."
    )),
    TermDefinition("fault", "Falla", (
        "Perturbación representada aquí por un cambio temporal de capacidad de transferencia."
    )),
    TermDefinition("clearing", "Despeje", "Transición de la red en falla a la red posfalla en un instante especificado."),
    TermDefinition("first-swing", "Primera oscilación · primer swing", (
        "Primera excursión creciente posfalla examinada mediante reversión y cruce del límite"
        " relevante."
    )),
    TermDefinition("cct", "CCT · tiempo crítico de despeje", (
        "Transición entre respuestas de primera oscilación; la búsqueda temporal entrega "
        "extremos estable e inestable."
    )),
    TermDefinition("reversal", "Reversión", (
        "Cambio muestreado de desviación de velocidad positiva a no positiva, respecto a la "
        "referencia síncrona."
    )),
    TermDefinition("crossing", "Cruce", "Paso muestreado que alcanza el equilibrio inestable posfalla relevante."),
)

# Keys retain the existing scientific and prediction contracts, including spaces.
MEANINGS = (
    TermDefinition("stable", "Estable", (
        "La excursión creciente revierte antes de alcanzar el equilibrio inestable posfalla "
        "relevante; se evalúa solo la primera oscilación muestreada."
    )),
    TermDefinition("unstable", "Inestable", (
        "Se alcanza el equilibrio inestable posfalla antes de una reversión, con desviación "
        "de velocidad positiva en ambas muestras del cruce."
    )),
    TermDefinition("indeterminate", "No concluyente", (
        "La evidencia muestreada no permite resolver el diagnóstico: puede faltar excursión "
        "positiva, horizonte suficiente u orden inequívoco de eventos."
    )),
    TermDefinition("reversal_before_crossing", "Reversión antes del cruce", ""),
    TermDefinition("crossing_before_reversal", "Cruce antes de la reversión", ""),
    TermDefinition("no_positive_excursion", "Sin excursión positiva posfalla", ""),
    TermDefinition("horizon_ended_before_event", "La ventana terminó antes del evento", ""),
    TermDefinition("event_order_ambiguous", "Orden de eventos no resuelto", ""),
    TermDefinition("smaller excursion", "Menor excursión", (
        "Predice una respuesta menor respecto a la configuración inicial; compara después los"
        " máximos de ángulo y desviación absoluta de velocidad."
    )),
    TermDefinition("larger excursion", "Mayor excursión", (
        "Predice una respuesta mayor respecto a la configuración inicial; contrasta ambas "
        "métricas, sin asumir una clasificación."
    )),
    TermDefinition("no change", "Sin cambio", "Predice que la respuesta conserva las métricas de la configuración inicial."),
    TermDefinition("introductory", "Inicial", ""),
    TermDefinition("intermediate", "Intermedio", ""),
    TermDefinition("late_clearing", "Tiempo de despeje", ""),
    TermDefinition("inertia_effect", "Efecto de la inercia", ""),
    TermDefinition("first_swing_evidence", "Evidencia de primera oscilación", ""),
    TermDefinition("bisection_stopping_criterion", "Criterio de parada de bisección", ""),
)

CASE_GUIDANCE = (
    CaseGuidance("first-swing-event-evidence", "Reconocer la primera oscilación", ("rotor-angle", "swing-equation", "fault-stages", "first-swing", "reading-plots"),
        (
            "Observa δ y Δω después del despeje. Busca la reversión de Δω y consulta el "
            "intervalo de cruce del límite posfalla cuando exista."
        ),
        (
            "Puedes cambiar solo el instante de despeje. La pregunta experimental es si "
            "cambia el orden observado de reversión y cruce."
        ),
        (
            "Compara diagnóstico, razón e intervalos de evento con la ejecución inicial. El "
            "reto consiste en obtener una primera oscilación inestable dentro del modelo."
        ),
        (
            "Explica qué evento se observó primero y por qué una ventana insuficiente o un "
            "orden ambiguo exige un resultado no concluyente."
        ),
        remember=(
            "δ mide separación angular eléctrica respecto de la red; Δω positiva significa "
            "que esa separación aumenta. Al pasar Δω de positiva a no positiva hay reversión "
            "del avance relativo, no del giro mecánico. El cruce alcanza el equilibrio inestable "
            "posfalla relevante: importa qué evento ocurre primero."
        ),
        experimental_question="¿Qué evidencia permite reconocer si la primera excursión retorna antes de alcanzar la frontera posfalla?",
        prediction_guidance=(
            "Revisa Pm, las capacidades de transferencia y el tiempo bajo falla. Razona cómo "
            "puede cambiar Δω y qué tendría que ocurrir para detener el avance de δ antes de "
            "la frontera. Predice un orden posible y qué evidencia necesitarías para confirmarlo."
        )),
    CaseGuidance("late-clearing-bracket", "Explorar el tiempo de despeje", ("fault-stages", "first-swing", "clearing-time", "time-step"),
        (
            "Observa cuánto aumenta la desviación de velocidad durante la falla y qué "
            "trayectoria sigue el rotor después del despeje."
        ),
        (
            "Puedes cambiar solo el instante de despeje. Explora cómo el tiempo bajo la red "
            "en falla cambia el estado con que comienza la posfalla."
        ),
        (
            "Compara la respuesta inicial y la del intento, junto con los extremos del "
            "intervalo crítico calculado. El reto es lograr una primera oscilación estable en"
            " este modelo."
        ),
        (
            "Explica cómo se relacionan el despeje, la velocidad acumulada y el resultado. "
            "Distingue el paso temporal de la tolerancia de bisección."
        ),
        remember=(
            "Mientras dura la falla, el balance neto sigue cambiando la velocidad y el ángulo. "
            "El despeje cambia la curva eléctrica, pero conserva ambos estados. Un bracket "
            "crítico conserva un extremo estable menor y otro inestable mayor, evaluados por "
            "el mismo criterio; su punto medio no es un tiempo exacto."
        ),
        experimental_question="¿Cómo cambia la primera oscilación al variar solo el instante de despeje?",
        prediction_guidance=(
            "Relaciona la duración de la falla con el movimiento acumulado y la capacidad "
            "posfalla. ¿Qué estado esperas alcanzar al despejar y qué orden de eventos podría "
            "seguir? Formula tu hipótesis antes de consultar los resultados de la búsqueda."
        )),
    CaseGuidance("controlled-inertia-effect", "Explorar el efecto de la inercia", ("swing-equation", "fault-stages", "inertia", "reading-plots"),
        (
            "Observa la forma de δ(t) y Δω(t), y sus máximos en la ventana. La predicción "
            "compara la respuesta con la configuración inicial."
        ),
        (
            "Puedes cambiar únicamente la inercia H. Mantén red, evento, potencia, estado "
            "inicial, horizonte y paso iguales para estudiar esta comparación controlada."
        ),
        (
            "Compara los máximos de ángulo y desviación absoluta de velocidad de ambas "
            "ventanas. El objetivo es observar un cambio de trayectoria; no exige cambiar el "
            "estado de estabilidad."
        ),
        (
            "Explica cómo H aparece en la aceleración y qué cambio muestran las métricas "
            "reales. Una mayor inercia no garantiza siempre estabilidad."
        ),
        remember=(
            "H representa energía cinética nominal por potencia base y divide el balance "
            "neto en la ecuación de velocidad. Para el mismo balance instantáneo, mayor H "
            "reduce la magnitud de esa derivada; cuando las trayectorias se separan, sus "
            "balances también pueden diferir. No hay una regla universal mayor H = estable."
        ),
        experimental_question="¿Qué cambia en las trayectorias y sus máximos cuando solo varía la inercia?",
        prediction_guidance=(
            "Compara el H del próximo intento con el inicial y razona sobre la rapidez de "
            "cambio de Δω. ¿Qué esperas observar en δ y en la desviación absoluta de velocidad "
            "durante la misma ventana? Tu predicción compara trayectorias, no asigna estabilidad."
        )),
)

LEARNING_PATH = (
    LearningStep("Aprende los conceptos básicos", "Conoce el modelo, las variables y las limitaciones.", "learn", "before-starting"),
    LearningStep("Reconoce una primera oscilación", "Distingue reversión, cruce y evidencia no concluyente.", "case", "first-swing-event-evidence"),
    LearningStep("Explora el despeje", "Relaciona el evento con la transición estable/inestable.", "case", "late-clearing-bracket"),
    LearningStep("Explora la inercia", "Cambia una sola variable y explica la comparación.", "case", "controlled-inertia-effect"),
)


def quantity(key: str) -> DisplayQuantity:
    """Resolve an explicit presentation key without guessing units."""
    return next(item for item in QUANTITIES if item.key == key)


def meaning(key: str) -> TermDefinition:
    """Resolve retained internal vocabulary without changing its semantics."""
    return next(item for item in MEANINGS if item.key == key)
