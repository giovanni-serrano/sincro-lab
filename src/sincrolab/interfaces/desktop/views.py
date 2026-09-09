"""Scrollable editorial surfaces populated by canonical controller content."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from sincrolab.interfaces.desktop.assets import DESIGN, Diagram
from sincrolab.interfaces.desktop.presentation import CasePreview
from sincrolab.interfaces.desktop.widgets import CaseCard, button, label


class Page(QScrollArea):
    """Keep content reachable at small sizes and larger system scaling."""

    def __init__(self, name: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName(name)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setProperty("role", "page")
        self.body = QVBoxLayout(content)
        self.body.setContentsMargins(32, 28, 32, 28)
        self.body.setSpacing(16)
        self.setWidget(content)


class CatalogPage(Page):
    case_selected = Signal(str)
    browse_requested = Signal()
    free_requested = Signal()
    learn_requested = Signal(str)

    def __init__(self, previews: tuple[CasePreview, ...], *, home: bool,
                 content: dict | None = None, parent=None) -> None:
        super().__init__("home" if home else "cases", parent)
        self.body.addWidget(label("LABORATORIO DE ESTABILIDAD TRANSITORIA" if home else "CASOS GUIADOS", "eyebrow"))
        self.body.addWidget(label("Comprende la respuesta del rotor" if home else "Tres escenarios para explorar", "heading"))
        self.body.addWidget(label(
            "Explora el modelo clásico de una máquina conectada a una barra infinita. "
            "Observa, predice y compara el efecto de tu intervención." if home else
            "Elige un fenómeno, registra tu predicción y contrástala con una simulación.", "muted"))
        if home:
            self.body.addWidget(Diagram("smib"))
            self.learn_button = button("Comenzar a aprender →", "home_learn", "primary")
            self.learn_button.clicked.connect(lambda: self.learn_requested.emit(
                content["learning_path"][0]["target_id"] if content and content["learning_path"] else "before-starting"))
            self.body.addWidget(self.learn_button, 0, Qt.AlignmentFlag.AlignLeft)
            actions = QHBoxLayout()
            self.browse_button = button("Explorar casos guiados →", "browse_cases", "link")
            self.browse_button.clicked.connect(self.browse_requested.emit)
            self.free_button = button("Modo libre →", "open_free", "link")
            self.free_button.clicked.connect(self.free_requested.emit)
            actions.addWidget(self.browse_button)
            actions.addWidget(self.free_button)
            actions.addStretch()
            self.body.addLayout(actions)
            if content:
                self.path_toggle = button("Tu recorrido de aprendizaje", "learning_path", "link")
                self.path_toggle.setCheckable(True)
                path = label("\n\n".join(f"{i}. {step['label']}. {step['description']}"
                             for i, step in enumerate(content["learning_path"], 1)))
                path.hide()
                self.path_toggle.toggled.connect(path.setVisible)
                self.body.addWidget(self.path_toggle, 0, Qt.AlignmentFlag.AlignLeft)
                self.body.addWidget(path)
            self.body.addWidget(label("Casos guiados", "section"))
        self.cards = []
        for number, preview in enumerate(previews, start=1):
            card = CaseCard(preview, number)
            card.selected.connect(self.case_selected.emit)
            self.body.addWidget(card)
            self.cards.append(card)
        if not home:
            self.body.addWidget(label("¿Prefieres tu propio escenario?", "title"))
            free = button("Explorar en modo libre →", "catalog_free", "link")
            free.clicked.connect(self.free_requested.emit)
            self.body.addWidget(free, 0, Qt.AlignmentFlag.AlignLeft)
        self.body.addStretch()


class LearnPage(Page):
    """Preserve block order while varying typography, spacing and disclosure."""

    case_requested = Signal(str)
    back_requested = Signal()

    def __init__(self, content: dict, parent=None) -> None:
        super().__init__("learn", parent)
        self.content = content
        self.body.addWidget(label("APRENDER", "eyebrow"))
        self.body.addWidget(label("Fundamentos y modelo", "heading"))
        self.return_button = button("Volver al caso activo", "theory_return_case", "link")
        self.return_button.clicked.connect(self.back_requested.emit)
        self.return_button.hide()
        self.body.addWidget(self.return_button)
        self.topics = QComboBox()
        self.topics.setObjectName("theory_topics")
        self.topics.setAccessibleName("Tema para aprender")
        self.topics.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.topics.setMinimumContentsLength(20)
        for topic in content["topics"]:
            self.topics.addItem(topic["title"], topic["topic_id"])
        self.topics.addItem("Glosario", "glossary")
        self.body.addWidget(self.topics)
        columns = QHBoxLayout()
        columns.setSpacing(28)
        self.rail = QWidget()
        self.rail.setFixedWidth(208)
        navigation = QVBoxLayout(self.rail)
        navigation.setContentsMargins(0, 0, 0, 0)
        navigation.setSpacing(4)
        self.topic_navigation = {}
        for group in DESIGN["topic_groups"]:
            navigation.addWidget(label(group["label"].upper(), "eyebrow"))
            for index in range(group["start"], min(group["stop"], len(content["topics"]))):
                topic = content["topics"][index]
                control = button("", f"topic_nav_{topic['topic_id']}", "topic")
                control.setCheckable(True)
                control.setAccessibleName(topic["title"])
                body = QVBoxLayout(control)
                body.setContentsMargins(6, 4, 6, 4)
                title = label(f"{index + 1:02d}  {topic['title']}", "caption")
                title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                body.addWidget(title)
                control.clicked.connect(lambda checked=False, key=topic["topic_id"]: self.select_topic(key))
                navigation.addWidget(control)
                self.topic_navigation[topic["topic_id"]] = control
            navigation.addSpacing(12)
        glossary = button("Glosario →", "topic_glossary", "link")
        glossary.clicked.connect(lambda: self.select_topic("glossary"))
        navigation.addWidget(glossary)
        navigation.addStretch()
        columns.addWidget(self.rail, 0, Qt.AlignmentFlag.AlignTop)
        article = QWidget()
        article.setMinimumWidth(0)
        article.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.article = QVBoxLayout(article)
        self.article.setContentsMargins(0, 0, 0, 0)
        self.article.setSpacing(16)
        self.topic_title = label("", "section")
        self.article.addWidget(self.topic_title)
        self.topic_body = QVBoxLayout()
        self.topic_body.setSpacing(20)
        self.article.addLayout(self.topic_body)
        self.article.addStretch()
        columns.addWidget(article, 1)
        self.body.addLayout(columns)
        self.body.addStretch()
        self.topics.currentIndexChanged.connect(self.render_topic)
        self.render_topic()

    def resizeEvent(self, event) -> None:
        wide = self.width() >= 870
        self.rail.setVisible(wide)
        self.topics.setVisible(not wide)
        super().resizeEvent(event)

    def select_topic(self, topic_id: str) -> None:
        self.topics.setCurrentIndex(self.topics.findData(topic_id))
        self.render_topic()

    def render_topic(self) -> None:
        while self.topic_body.count():
            widget = self.topic_body.takeAt(0).widget()
            widget.setParent(None)
            widget.deleteLater()
        self.block_widgets = []
        self.topic_buttons = {}
        self.case_buttons = {}
        self.next_button = None
        self.previous_button = None
        self.topic_title.setText(self.topics.currentText())
        key = self.topics.currentData()
        for topic_id, control in self.topic_navigation.items():
            control.setChecked(topic_id == key)
        if key == "glossary":
            self.topic_text = label("\n\n".join(f"{item['label']}\n{item['description']}" for item in self.content["glossary"]))
            self.topic_body.addWidget(self.topic_text)
        elif key is not None:
            index = next(i for i, item in enumerate(self.content["topics"]) if item["topic_id"] == key)
            topic = self.content["topics"][index]
            self.topic_body.addWidget(label("OBJETIVO DE APRENDIZAJE", "eyebrow"))
            self.objective = label(topic["learning_objective"], "muted")
            self.topic_body.addWidget(self.objective)
            for block_index, block in enumerate(topic["blocks"]):
                title = next(item["label"] for item in self.content["block_labels"] if item["key"] == block["kind"])
                container = QFrame()
                container.setProperty("role", block["kind"])
                layout = QVBoxLayout(container)
                inset = 16 if block["kind"] in ("equation", "key-idea", "reflection") else 0
                layout.setContentsMargins(inset, 8, inset, 8)
                layout.setSpacing(8)
                heading = label(title, "eyebrow" if block["kind"] in ("equation", "example", "reflection") else "title")
                text = label(block["text"], "equation_text" if block["kind"] == "equation" else "body")
                text.setProperty("block_kind", block["kind"])
                text.setObjectName(f"theory_block_{block_index}")
                layout.addWidget(heading)
                layout.addWidget(text)
                self.topic_body.addWidget(container)
                self.block_widgets.append((heading, text))
                if block_index == 0:
                    for diagram_id, metadata in DESIGN["diagrams"].items():
                        if key in metadata["topics"]:
                            self.topic_body.addWidget(Diagram(diagram_id))
            if topic["prerequisite_topic_ids"]:
                self.topic_body.addWidget(label("Repasar conceptos", "title"))
            for target in topic["prerequisite_topic_ids"]:
                title = next(item["title"] for item in self.content["topics"] if item["topic_id"] == target)
                self.topic_body.addWidget(label(title, "muted"))
                control = button("Repasar este concepto →", f"theory_topic_{target}", "link")
                control.setAccessibleName(f"Repasar: {title}")
                control.clicked.connect(lambda checked=False, key=target: self.select_topic(key))
                self.topic_body.addWidget(control)
                self.topic_buttons[target] = control
            for target in topic["case_ids"]:
                number, case = next((i, item) for i, item in enumerate(self.content["cases"], 1) if item["case_id"] == target)
                self.topic_body.addWidget(label(case["concept"], "title"))
                control = button(f"Abrir Caso {number} →", f"theory_case_{target}", "link")
                control.setAccessibleName(f"Abrir Caso {number}: {case['concept']}")
                control.clicked.connect(lambda checked=False, key=target: self.case_requested.emit(key))
                self.topic_body.addWidget(control)
                self.case_buttons[target] = control
            if index:
                previous = self.content["topics"][index - 1]
                self.previous_button = button("← Tema anterior", "theory_previous", "link")
                self.previous_button.clicked.connect(lambda: self.select_topic(previous["topic_id"]))
                self.topic_body.addWidget(self.previous_button)
            if index + 1 < len(self.content["topics"]):
                following = self.content["topics"][index + 1]
                self.topic_body.addWidget(label(f"Siguiente tema: {following['title']}", "muted"))
                self.next_button = button("Continuar al siguiente tema →", "theory_next", "primary")
                self.next_button.clicked.connect(lambda: self.select_topic(following["topic_id"]))
                self.topic_body.addWidget(self.next_button)
        self.verticalScrollBar().setValue(0)
