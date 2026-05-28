#!/usr/bin/env python3
#
#

import argparse
import json
import os
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

from functools import partial

import graphviz
import hal

parser = argparse.ArgumentParser()
parser.add_argument("--interval", "-i", help="update interval", type=int, default=100)
parser.add_argument("--buffer", "-b", help="linechart buffer size", type=int, default=50)
parser.add_argument("--setup", "-s", help="setup file", type=str, default="")
parser.add_argument("--qt5", "-5", help="using pyqt5", default=False, action="store_true")
parser.add_argument("--qt6", "-6", help="using pyqt6", default=False, action="store_true")
args = parser.parse_args()
qtversion = "5"
if args.qt6:
    qtversion = "6"

if qtversion == "5":
    from PyQt5.QtCore import QPoint, QPointF, QRectF, QTimer, Qt
    from PyQt5.QtGui import (
        QBrush,
        QColor,
        QFont,
        QMouseEvent,
        QPainter,
        QPainterPath,
        QPen,
    )
    from PyQt5.QtWidgets import (
        QApplication,
        QCheckBox,
        QGraphicsItem,
        QGraphicsPathItem,
        QGraphicsScene,
        QGraphicsView,
        QHBoxLayout,
        QMainWindow,
        QPushButton,
        QScrollArea,
        QSplitter,
        QVBoxLayout,
        QWidget,
    )
else:
    from PyQt6.QtCore import QPoint, QPointF, QRectF, QTimer, Qt
    from PyQt6.QtGui import (
        QBrush,
        QColor,
        QFont,
        QMouseEvent,
        QPainter,
        QPainterPath,
        QPen,
    )
    from PyQt6.QtWidgets import (
        QApplication,
        QCheckBox,
        QGraphicsItem,
        QGraphicsPathItem,
        QGraphicsScene,
        QGraphicsView,
        QHBoxLayout,
        QMainWindow,
        QPushButton,
        QScrollArea,
        QSplitter,
        QVBoxLayout,
        QWidget,
    )


class NodeEdge(QGraphicsPathItem):
    width = 3
    width_selected = 6

    def __init__(self, parent, source_node, source_port, des_node, des_port):
        super().__init__(None)
        self.parent = parent
        self._source_node = source_node
        self._source_port = source_port
        self._target_node = des_node
        self._target_port = des_port
        self.color = Qt.GlobalColor.gray
        self.style = Qt.PenStyle.SolidLine
        self._pen_default = QPen(self.color)
        self._pen_default.setWidthF(2)
        # self.setZValue(-1)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        self.update_edge_path()
        self.hover = False

    def paint(self, painter: QPainter, option, widget):
        self._pen_default = QPen(self.color)
        if self.hover:
            self._pen_default.setWidthF(self.width_selected)
        else:
            self._pen_default.setWidthF(self.width)
        painter.setPen(self._pen_default)
        self.update_edge_path()
        painter.drawPath(self.path())

    def update_edge_path(self):
        if not self._source_node or not self._target_node:
            return
        pos1 = self._source_node.port_pos(self._source_port, self._target_node)
        pos2 = self._target_node.port_pos(self._target_port, self._source_node)
        distance = (pos2.x() - pos1.x()) / 2
        control_x_start = distance
        control_x_end = -distance
        path = QPainterPath(pos1)
        path.cubicTo(
            QPointF(pos1.x() + control_x_start, pos1.y()),
            QPointF(pos2.x() + control_x_end, pos2.y()),
            pos2,
        )
        self.setPath(path)

    def hoverEnterEvent(self, event):
        self.hover = True
        self.update()

    def hoverLeaveEvent(self, event):
        self.hover = False
        self.update()


class CompNode(QGraphicsItem):
    name = ""
    radius = 5
    border_size = 4
    border_color = QColor(150, 150, 150)
    border_color_selected = QColor(250, 250, 250)
    border_color_hover = QColor(200, 200, 200)
    bg_color = QColor(100, 100, 100)
    title_size = 9
    info_size = 7
    text_scale = 1.8
    text_font = "Times"
    title_color = QColor(255, 255, 255)
    info_color = QColor(200, 200, 200)
    port_size = 10
    port_border = 2
    port_top = 40
    port_bottom = 10
    port_diff = 15

    def __init__(self, parent, x, y, w, h, title, pins):
        super().__init__()
        self.parent = parent
        self.width = w
        self.height = h
        self.title = title
        self.pins = pins
        if x is not None and y is not None:
            self.setPos(x, y)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        self.hover = False

    def port_selected(self, mpos):
        mpos_y = mpos.y()
        idx = int((mpos_y - self.radius - 16) // 16)
        if idx >= 0 and idx < len((self.pins)):
            return list(self.pins)[idx]
        return None

    def port_pos(self, port, other_node):
        pos = self.pos()
        pos_x = pos.x()
        pos_y = pos.y()
        opos = other_node.pos()
        if pos_x < opos.x():
            pos_x += self.width - 8
        else:
            pos_x += 8
        if port in self.pins:
            idx = list(self.pins).index(port)
            pos_y += self.radius + 16 + idx * 16 + 8
        return QPointF(pos_x, pos_y)

    def boundingRect(self):
        self.height = len(self.pins) * 16 + 16 + self.radius * 2
        return QRectF(0, 0, self.width, self.height)

    def paintArrow(self, painter, x, y, direction):
        if direction == "LEFT":
            path = QPainterPath()
            path.moveTo(QPointF(x - 5, y))
            path.lineTo(QPointF(x + 5, y + 5))
            path.lineTo(QPointF(x + 5, y - 5))
            path.lineTo(QPointF(x - 5, y))
        elif direction == "RIGHT":
            path = QPainterPath()
            path.moveTo(QPointF(x + 5, y))
            path.lineTo(QPointF(x - 5, y + 5))
            path.lineTo(QPointF(x - 5, y - 5))
            path.lineTo(QPointF(x + 5, y))
        else:
            path = QPainterPath()
            path.moveTo(QPointF(x + 5, y + 5))
            path.lineTo(QPointF(x - 5, y + 5))
            path.lineTo(QPointF(x - 5, y - 5))
            path.lineTo(QPointF(x + 5, y - 5))
            path.lineTo(QPointF(x + 5, y + 5))
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.setBrush(QBrush(Qt.GlobalColor.yellow))
        painter.fillPath(path, painter.brush())
        painter.drawPath(path)

    def paint(self, painter, option, widget):
        if self.hover:
            pen = QPen(self.border_color_hover, self.border_size)
        elif self.isSelected():
            pen = QPen(self.border_color_selected, self.border_size)
        else:
            pen = QPen(self.border_color, self.border_size)
        painter.setPen(QPen(self.title_color, 1))
        painter.setFont(QFont(self.text_font, self.title_size))

        # title
        rect = self.boundingRect()
        rect = QRectF(0, 0, self.width, self.radius + 16)
        title_path = QPainterPath()
        title_path.addRoundedRect(rect, self.radius, self.radius)
        painter.setClipPath(title_path)

        # path
        rect = self.boundingRect()
        path = QPainterPath()
        path.addRoundedRect(rect, self.radius, self.radius)
        painter.setClipPath(path)

        # background
        brush = QBrush(self.bg_color)
        painter.setBrush(brush)
        painter.fillPath(path, painter.brush())

        # title background
        brush = QBrush(QColor(150, 150, 200))
        painter.setBrush(brush)
        painter.fillPath(title_path, painter.brush())
        py = self.radius
        painter.setPen(QPen(self.title_color, 1))
        painter.drawText(
            QRectF(0, py - 3, self.width, 16),
            Qt.AlignmentFlag.AlignCenter,
            self.title,
        )
        py += 16

        # border
        painter.setPen(pen)
        painter.strokePath(path, painter.pen())

        # pin text
        for pin_name, pin_data in self.pins.items():
            pin_title = pin_data["pin"]
            value = pin_data["value"]
            pininfo = pin_data["pininfo"]
            if not pininfo:
                print(f"ERROR: name: {pin_name} pininfo: {pininfo}")
                continue
            direction = pininfo["direction"]
            signal = pininfo["signal"]
            if signal is None:
                painter.setPen(QPen(self.info_color, 1))
                painter.drawText(
                    QRectF(0, py, self.width, 16),
                    Qt.AlignmentFlag.AlignCenter,
                    f"{pin_title}={value}",
                )
            else:
                if direction == "IN":
                    self.paintArrow(painter, 8, py + 8, "RIGHT")
                    self.paintArrow(painter, self.width - 8, py + 8, "LEFT")
                elif direction == "OUT":
                    self.paintArrow(painter, 8, py + 8, "LEFT")
                    self.paintArrow(painter, self.width - 8, py + 8, "RIGHT")
                else:
                    self.paintArrow(painter, 8, py + 8, "BOTH")
                    self.paintArrow(painter, self.width - 8, py + 8, "BOTH")

                painter.setPen(QPen(self.title_color, 1))
                painter.drawText(
                    QRectF(0, py, self.width, 16),
                    Qt.AlignmentFlag.AlignCenter,
                    f"{pin_title}={value}",
                )
            py += 16

    def hoverEnterEvent(self, event):
        self.hover = True
        self.update()

    def hoverLeaveEvent(self, event):
        self.hover = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            QGraphicsItem.mousePressEvent(self, event)

    def mouseReleaseEvent(self, event):
        pos = self.pos()
        self.parent.nodesetup["positions"][self.title] = (pos.x(), pos.y())
        self.parent.writeSetup()
        QGraphicsItem.mouseReleaseEvent(self, event)

    def mouseDoubleClickEvent(self, event):
        port = None
        if event.button() == Qt.MouseButton.LeftButton:
            port = self.port_selected(event.pos())
            if port:
                self.parent.toggle_pin_graph(f"{self.title}.{port}")
            else:
                self.parent.toggle_group_graph(f"{self.title.split('.')[0]}.")


class NodeScene(QGraphicsScene):
    def __init__(self, x, y, w, h, parent):
        super().__init__(x, y, w, h)
        self.parent = parent
        self.setBackgroundBrush(QColor("#262626"))


class NodeViewer(QGraphicsView):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.scene = parent.scene
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(self.ViewportAnchor.AnchorUnderMouse)

        self.button_pressed = 0
        self.mouse_pos_last = QPoint()
        self.mouse_pos = QPoint()

    def getZoom(self):
        transform = self.transform()
        return transform.m11()

    def setZoom(self, zoomFactor):
        transform = self.transform()
        transform.reset()
        transform.scale(zoomFactor, zoomFactor)
        self.setTransform(transform)

    def wheelEvent(self, event):
        zoom = self.getZoom()
        angle = event.angleDelta().y()
        zoomFactor = max(min(1 + (angle / 1000), 1.2), 0.8)
        if zoom < 0.1 and zoomFactor < 1.0:
            return
        if self.getZoom() > 5.0 and zoomFactor > 1.0:
            return
        self.scale(zoomFactor, zoomFactor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)
        self.mouse_pos = event.pos()
        self.button_pressed = event.button()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.mouse_pos = event.pos()
        self.button_pressed = 0
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() in [Qt.MouseButton.RightButton]:
            self.parent.fit_view()
        else:
            super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self.mouse_pos_last = event.pos()
        if self.button_pressed in [Qt.MouseButton.LeftButton]:
            pass

        elif self.button_pressed in [Qt.MouseButton.MiddleButton]:
            offset = self.mouse_pos - event.pos()
            self.mouse_pos = event.pos()
            dx, dy = offset.x(), offset.y()
            self.horizontalScrollBar().setValue(int(self.horizontalScrollBar().value() + dx))
            self.verticalScrollBar().setValue(int(self.verticalScrollBar().value() + dy))

        super().mouseMoveEvent(event)


class LineCharts(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.data = self.parent.pin_graph_data
        self.width = 0
        self.height = 0
        self.resize(self.width, self.height)

    def resizeEvent(self, event):
        self.width = event.size().width()

    def mouseDoubleClickEvent(self, event):
        mpos_y = event.pos().y()
        py = 10
        gh = 70
        idx = int((mpos_y - py) // (22 + gh + 5))
        if idx < len(self.parent.nodesetup["linecharts"]):
            self.parent.nodesetup["linecharts"].pop(idx)
        self.parent.writeSetup()
        self.parent.check_splitter()

    def paintEvent(self, event):
        if self.width < 10:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(QFont("Arial", 12))
        painter.setPen(QPen(Qt.GlobalColor.black, 1))

        try:
            gw = self.width - 10
            gh = 70
            px = 5
            py = 10
            for pin, data in self.data.items():
                painter.setPen(QPen(Qt.GlobalColor.black, 1))
                if not data["data"]:
                    painter.drawText(QRectF(5, py, gw, 22), Qt.AlignmentFlag.AlignLeft, pin)
                    py += 22
                else:
                    painter.drawText(
                        QRectF(5, py, gw, 22),
                        Qt.AlignmentFlag.AlignLeft,
                        f"{pin}: {data['data'][0]}",
                    )
                    py += 22

                    if data["min"] is None:
                        data["min"] = float(data["data"][0])
                        data["max"] = float(data["data"][0])
                    for point in data["data"]:
                        data["min"] = min(data["min"], float(point))
                        data["max"] = max(data["max"], float(point))
                    vdiff = data["max"] - data["min"]

                    painter.fillRect(QRectF(px, py - 1, gw + 2, gh + 2), Qt.GlobalColor.gray)
                    painter.setPen(QPen(Qt.GlobalColor.blue, 1))

                    if vdiff != 0:
                        point = data["data"][0]
                        gy_last = (float(point) - data["min"]) / vdiff * gh
                        gx_last = gw
                        for gn, point in enumerate(data["data"][1:]):
                            gy = (float(point) - data["min"]) / vdiff * gh
                            gx = px + gw - (gn * gw / data["len"])
                            painter.drawLine(QPointF(gx_last, py + gy_last), QPointF(gx, py + gy))
                            gy_last = gy
                            gx_last = gx

                py += gh + 5

            self.height = py + 10
            self.setFixedHeight(self.height)

        except Exception:
            pass


class MainWindow(QMainWindow):
    default_grouping = ["halui.", "pyvcp.", "qtpyvcp.", "gladevcp.", "qtdragon.", "flexhal.", "rio-gui."]
    grouping = []
    cfilter = (
        "halui.",
        "joint.",
        "pid.",
        "spindle.",
        "iocontrol.",
        "axis.",
        "motion.digital-in-",
        "motion.digital-out-",
        "motion.feed-",
        "motion.tooloffset.",
        "motion.analog-in-",
        "motion.analog-out-",
        "motion-command-handler.time",
        "motion-controller.time",
        "motion.adaptive-feed",
        "motion.coord-error",
        "motion.coord-mode",
        "motion.current-vel",
        "motion.distance-to-go",
        "motion.eoffset-active",
        "motion.eoffset-limited",
        "motion.homing-inhibit",
        "motion.in-position",
        "motion.jog-inhibit",
        "motion.jog-is-active",
        "motion.jog-stop",
        "motion.jog-stop-immediate",
        "motion.on-soft-limit",
        "motion.requested-vel",
        "motion.servo.last-period",
        "motion.tp-reverse",
    )
    pfilter = (
        "-not",
        "-abs",
        "-s32",
        "-u32",
        ".maxcmdD",
        ".maxcmdDD",
        ".maxcmdDDD",
        ".maxerror",
        ".maxerrorD",
        ".maxerrorI",
        ".maxoutput",
        ".saturated",
        ".saturated-count",
        ".saturated-s",
        ".tune-cycles",
        ".tune-effort",
        ".tune-mode",
        ".tune-start",
        ".tune-type",
        ".command-deriv",
        ".do-pid-calcs.time",
        ".error-previous-target",
        ".feedback-deriv",
    )

    def __init__(self):
        super().__init__()
        self.setWindowTitle("LinuxCNC - HalViewer")

        self.nodesetup = {}
        if not args.setup:
            result = subprocess.run(["halreport"], stdout=subprocess.PIPE, check=False)
            for line in result.stdout.decode().split("\n"):
                if line.startswith("INI_FILE_NAME:"):
                    args.setup = f"{os.path.dirname(line.split()[-1])}/halviewer.json"
        if args.setup and os.path.isfile(args.setup):
            self.nodesetup = json.loads(open(args.setup, "r").read())
        if "linecharts" not in self.nodesetup:
            self.nodesetup["linecharts"] = []
        if "positions" not in self.nodesetup:
            self.nodesetup["positions"] = {}
        if "grouping" not in self.nodesetup:
            self.nodesetup["grouping"] = self.default_grouping[0:]
        if "unconnected" not in self.nodesetup:
            self.nodesetup["unconnected"] = True
        if "namesort" not in self.nodesetup:
            self.nodesetup["namesort"] = True
        if "dirsort" not in self.nodesetup:
            self.nodesetup["dirsort"] = False
        if "filter" not in self.nodesetup:
            self.nodesetup["filter"] = True

        self.pin_graph_data = {}
        self.run = True
        self.resize(1200, 900)
        self.scene = NodeScene(-7000, -7000, 12000, 12000, self)
        self.view = NodeViewer(self)
        self.charts = LineCharts(self)

        svg_data = self.export()
        self.root = ET.fromstring(svg_data)
        if self.root is None:
            print("ERROR parsing ini file")
            exit(0)

        self.h = hal.component(f"halview-{uuid.uuid4()}")
        self.h.ready()

        hboxButtons = QHBoxLayout()
        hboxBoxes = QHBoxLayout()

        for tval in ("unconnected", "namesort", "dirsort", "filter"):
            checkbox = QCheckBox(tval.title())
            checkbox.setChecked(self.nodesetup[tval])
            checkbox.stateChanged.connect(partial(self.toggle, tval))
            hboxBoxes.addWidget(checkbox, stretch=0)

        button_reset_grouping = QPushButton("Reset grouping")
        button_reset_grouping.clicked.connect(self.reset_grouping)
        hboxButtons.addWidget(button_reset_grouping, stretch=0)

        button_reset_layout = QPushButton("Reset layout")
        button_reset_layout.clicked.connect(self.reset_layout)
        hboxButtons.addWidget(button_reset_layout, stretch=0)

        button_fit = QPushButton("Fit to Window")
        button_fit.clicked.connect(self.fit_view)
        hboxButtons.addWidget(button_fit, stretch=0)

        button_freeze = QPushButton("Freeze")
        button_freeze.clicked.connect(self.freeze)
        hboxButtons.addWidget(button_freeze, stretch=0)

        vboxMain = QVBoxLayout()
        hboxButtons.addStretch()
        vboxMain.addLayout(hboxButtons)

        linecharts = QScrollArea()
        linecharts.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        linecharts.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        linecharts.setWidgetResizable(True)
        linecharts.setWidget(self.charts)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.view)
        self.splitter.addWidget(linecharts)
        self.splitter.setSizes([self.geometry().width() - self.charts.width, 0])
        vboxMain.addWidget(self.splitter)
        hboxBoxes.addStretch()
        vboxMain.addLayout(hboxBoxes)

        self.main = QWidget()
        self.setCentralWidget(self.main)
        self.main.setLayout(vboxMain)

        self.readGraph()
        self.check_splitter()
        self.show()
        self.fit_view()

        self.timer = QTimer()
        self.timer.timeout.connect(self.runTimer)
        self.timer.start(args.interval)

    def toggle(self, name, value):
        self.nodesetup[name] = bool(value)
        self.reload()
        self.fit_view()

    def reload(self):
        svg_data = self.export()
        self.root = ET.fromstring(svg_data)
        self.readGraph()
        self.writeSetup()

    def reset_grouping(self):
        self.nodesetup["grouping"] = self.default_grouping[0:]
        self.reload()
        self.fit_view()

    def reset_layout(self):
        self.nodesetup["positions"] = {}
        self.reload()
        self.fit_view()

    def check_splitter(self):
        if self.nodesetup["linecharts"]:
            if self.charts.width < 10:
                self.charts.width = 200
                self.splitter.setSizes([self.geometry().width() - self.charts.width, self.charts.width])
        elif self.charts.width > 100:
            self.charts.width = 0
            self.splitter.setSizes([self.geometry().width(), 0])

    def toggle_group_graph(self, group):
        if group in self.nodesetup["grouping"]:
            self.nodesetup["grouping"].remove(group)
        else:
            self.nodesetup["grouping"].append(group)
        self.reload()

    def toggle_pin_graph(self, pin):
        if pin in self.nodesetup["linecharts"]:
            self.nodesetup["linecharts"].remove(pin)
        else:
            self.nodesetup["linecharts"].append(pin)
        self.check_splitter()
        self.writeSetup()

    def export(self):
        colors = {
            "bg": "",
            "edge": "black",
            "header_bg": "black",
            "header_text": "white",
            "port_bg": "white",
            "port_text": "black",
            "setp_bg": "gray",
            "setp_text": "black",
        }

        self.gAll = graphviz.Digraph("G", format="svg", engine="dot")
        self.gAll.attr(ranksep="2.5")
        self.gAll.attr(rankdir="LR")

        self.pininfo = {}
        self.signals = {}
        self.components = {}
        self.setps = []

        result = subprocess.run(["halcmd", "show"], stdout=subprocess.PIPE, check=False)
        section = ""
        for line in result.stdout.decode().split("\n"):
            if line == "Parameters:":
                section = "params"
            elif line == "Component Pins:":
                section = "pins"
            elif not line:
                section = ""
            elif section == "pins" and line.split()[0].isnumeric():
                if "=" in line:
                    owner, vtype, direction, value, name, arrow, signal = line.split()
                    self.pininfo[name] = {
                        "owner": owner,
                        "vtype": vtype,
                        "direction": direction,
                        "value": value,
                        "name": name,
                        "arrow": arrow,
                        "signal": signal,
                    }
                    if signal not in self.signals:
                        self.signals[signal] = {
                            "source": "",
                            "targets": [],
                        }
                    if arrow == "<==":
                        self.signals[signal]["targets"].append(name)
                    elif arrow == "==>":
                        self.signals[signal]["source"] = name
                    elif arrow == "<=>":
                        if self.signals[signal]["source"]:
                            self.signals[signal]["targets"].append(name)
                        else:
                            self.signals[signal]["source"] = name
                elif self.nodesetup["unconnected"]:
                    owner, vtype, direction, value, name = line.split()
                    self.pininfo[name] = {
                        "owner": owner,
                        "vtype": vtype,
                        "direction": direction,
                        "value": value,
                        "name": name,
                        "arrow": None,
                        "signal": None,
                    }
                    if not self.nodesetup["filter"] or (not name.startswith((self.cfilter)) and not name.endswith(self.pfilter)):
                        self.setps.append(name)

        groups = {}
        basenames = set()
        for signal_name, parts in self.signals.items():
            source_parts = parts["source"].split(".")
            source_group = ".".join(source_parts[0:-1])
            source_pin = source_parts[-1]
            if source_group.startswith(tuple(self.nodesetup["grouping"])):
                source_group = ".".join(source_parts[0:1])
                source_pin = ".".join(source_parts[1:])
            if not source_group:
                source_group = source_pin
            basenames.add(source_parts[0])
            source = f"{source_group}:{source_pin}"
            if not source_group:
                source_group = source_parts[0]
            if source_group:
                if source_group not in groups:
                    groups[source_group] = []
                groups[source_group].append(source_pin)
            for target in parts["targets"]:
                target_parts = target.split(".")
                target_group = ".".join(target_parts[:-1])
                target_pin = target_parts[-1]
                if target_group.startswith(tuple(self.nodesetup["grouping"])):
                    target_group = ".".join(target_parts[0:1])
                    target_pin = ".".join(target_parts[1:])
                target_name = f"{target_group}:{target_pin}"
                if not target_group:
                    target_group = target_parts[0]
                if target_group not in groups:
                    groups[target_group] = []
                groups[target_group].append(target_pin)
                if not source_group and not source_pin:
                    continue
                if not target_name:
                    continue
                source_name = source.split("=")[0]
                eid = source_name.replace(":", ".")

                self.gAll.edge(
                    source_name,
                    target_name,
                    id=eid,
                    penwidth="2",
                    color=colors["edge"],
                )

        """
        for name in self.pininfo:
            base = name.split(".")[0]
            if base in groups or base in basenames:
                continue
            source_parts = name.split(".")
            source_group = ".".join(source_parts[:-1])
            source_pin = source_parts[-1]
            if source_group.startswith(tuple(self.nodesetup["grouping"])):
                source_group = ".".join(source_parts[0:1])
            if source_group:
                if source_group not in groups:
                    groups[source_group] = []
        """

        used = []
        for group_name in sorted(groups, reverse=True):
            pin_strs = []
            pinlist = groups[group_name]
            if self.nodesetup["namesort"]:
                pinlist = sorted(pinlist)
            for pin_name in pinlist:
                pin_str = f'<tr><td bgcolor="{colors["port_bg"]}" port="{pin_name}"><font color="{colors["port_text"]}">{pin_name}=000.000</font></td></tr>'
                pin_strs.append(pin_str)

            pinlist = self.setps
            if self.nodesetup["namesort"]:
                pinlist = sorted(pinlist)
            for setp_raw in pinlist:
                if setp_raw.startswith(f"{group_name}.") and setp_raw not in used:
                    used.append(setp_raw)
                    setp = setp_raw.replace(f"{group_name}.", "")
                    pin_str = f'<tr><td bgcolor="{colors["setp_bg"]}" port="{setp}"><font color="{colors["setp_text"]}">{setp}=000.000</font></td></tr>'
                    pin_strs.append(pin_str)

            title = group_name.replace("\\n", "<br/>")
            label = f'<<table border="0" cellborder="1" cellspacing="0"><tr><td bgcolor="{colors["header_bg"]}"><font color="{colors["header_text"]}">{title}</font></td></tr>{"".join(pin_strs)}</table>>'
            self.gAll.node(
                group_name,
                shape="plaintext",
                label=label,
                fontsize="11pt",
                style="",
            )

        return self.gAll.pipe()

    def readGraph(self):
        # clean scene
        for item in self.scene.items():
            self.scene.removeItem(item)

        self.pinsdict = {}
        self.nodesdict = {}

        nodes = self.root.findall(".//*[@class='node']")
        for node in nodes:
            title = node.find(".//{http://www.w3.org/2000/svg}title")
            if title is not None:
                polygon = node.find(".//{http://www.w3.org/2000/svg}polygon")
                x1 = float(polygon.attrib["points"].split()[0].split(",")[0])
                y1 = float(polygon.attrib["points"].split()[0].split(",")[1])
                x2 = float(polygon.attrib["points"].split()[2].split(",")[0])
                y2 = float(polygon.attrib["points"].split()[2].split(",")[1])
                for polygon in node.findall(".//{http://www.w3.org/2000/svg}polygon"):
                    for point in polygon.attrib["points"].split():
                        x, y = point.split(",")
                        x1 = min(float(x), x1)
                        y1 = min(float(y), y1)
                        x2 = max(float(x), x2)
                        y2 = max(float(y), y2)

                pins = {}
                pinlist = []
                pintext = node.findall(".//{http://www.w3.org/2000/svg}text")
                for text in pintext:
                    pinlist.append(text.text.split("=")[0])

                if self.nodesetup["dirsort"] or len(pintext) < 7:
                    sorting = ("IN", "INOUT", "OUT", None)
                else:
                    sorting = ("OFF",)
                for skey in sorting:
                    for pin_name in pinlist:
                        if title.text == pin_name:
                            continue
                        if skey != "OFF":
                            check = self.pininfo.get(f"{title.text}.{pin_name}", {}).get("direction")
                            if self.pininfo.get(f"{title.text}.{pin_name}", {}).get("signal") is None:
                                check = None
                            if check != skey:
                                continue
                        pdict = {
                            "node": title.text,
                            "pin": pin_name,
                            "value": None,
                            "pininfo": self.pininfo.get(f"{title.text}.{pin_name}", {}),
                        }
                        pins[pin_name] = pdict
                        self.pinsdict[f"{title.text}.{pin_name}"] = pdict

                w = abs(x2 - x1) + 30
                h = abs(y2 - y1)
                w = max(w, 70)
                h = max(h, 40)
                if title.text in self.nodesetup["positions"]:
                    x1, y1 = self.nodesetup["positions"][title.text]
                self.nodesdict[title.text] = CompNode(self, x1, y1, w, h, title.text, pins)
                self.scene.addItem(self.nodesdict[title.text])

        self.edges = {}
        edges = self.root.findall(".//*[@class='edge']")
        for edge in edges:
            title = edge.find(".//{http://www.w3.org/2000/svg}title")
            if title is not None:
                begin, end = title.text.split("->")
                begin_node, begin_pin = begin.split(":")
                end_node, end_pin = end.split(":")
                edgenode = NodeEdge(
                    self,
                    self.nodesdict[begin_node],
                    begin_pin,
                    self.nodesdict[end_node],
                    end_pin,
                )
                self.scene.addItem(edgenode)
                pin = f"{begin_node}.{begin_pin}"
                if pin not in self.edges:
                    self.edges[pin] = []
                self.edges[pin].append(edgenode)
        self.writeSetup()

    def writeSetup(self):
        if args.setup:
            open(args.setup, "w").write(json.dumps(self.nodesetup, indent=4))

    def runTimer(self):
        if not self.run:
            return

        for pin in self.nodesetup["linecharts"]:
            if pin not in self.pin_graph_data:
                self.pin_graph_data[pin] = {
                    "data": [],
                    "min": None,
                    "max": None,
                    "len": args.buffer,
                }
        for pin in list(self.pin_graph_data):
            if pin not in self.nodesetup["linecharts"]:
                del self.pin_graph_data[pin]

        # get hal data
        listOfDicts = hal.get_info_pins()
        updates = set()
        for part in listOfDicts:
            pinName = part.get("NAME")
            pinValue = part.get("VALUE")
            pinType = part.get("TYPE")

            try:
                # pin graph
                if pinName in self.pin_graph_data:
                    self.pin_graph_data[pinName]["data"] = [
                        pinValue,
                        *self.pin_graph_data[pinName]["data"][: self.pin_graph_data[pin]["len"]],
                    ]
            except Exception:
                pass

            dataColor = Qt.GlobalColor.white
            if pinType == 1:
                if pinValue:
                    dataColor = Qt.GlobalColor.green
                else:
                    dataColor = Qt.GlobalColor.red
            elif pinType == 2:
                pinValue = f"{pinValue:0.3f}"
            if pinName in self.pinsdict:
                node_name = self.pinsdict[pinName]["node"]
                pin_name = self.pinsdict[pinName]["pin"]
                node = self.nodesdict[node_name]
                if node.pins[pin_name]["value"] != pinValue:
                    node.pins[pin_name]["value"] = pinValue
                    updates.add(node)

            if pinName in self.edges:
                for edge in self.edges[pinName]:
                    edge.color = dataColor
                    updates.add(edge)

        for node in updates:
            node.update()

        self.charts.update()

    def freeze(self):
        self.run = 1 - self.run

    def fit_view(self):
        min_x = 99999
        min_y = 99999
        max_x = -99999
        max_y = -99999
        for item in self.scene.items():
            if isinstance(item, NodeEdge):
                continue
            px = item.pos().x()
            py = item.pos().y()
            min_x = min((min_x, px))
            min_y = min((min_y, py))
            max_x = max(max_x, px + item.width)
            max_y = max(max_y, py + item.height)
        # calc scale and offsets
        if min_x == 99999:
            min_x = 0
            max_x = 800
            min_y = 0
            max_y = 800
        w = max_x - min_x
        h = max_y - min_y
        slider_size = 20
        vw = self.view.width() - slider_size
        vh = self.view.height() - slider_size

        border = 50
        scale = min((vw - border) / w, (vh - border) / h)
        pos_x = int(min_x * scale)
        pos_y = int(min_y * scale)
        # center
        diff_x = vw - w * scale
        diff_y = vh - h * scale
        pos_x -= diff_x / 2
        pos_y -= diff_y / 2

        self.view.setZoom(scale)
        self.view.horizontalScrollBar().setSliderPosition(int(pos_x))
        self.view.verticalScrollBar().setSliderPosition(int(pos_y))

        self.update()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()
