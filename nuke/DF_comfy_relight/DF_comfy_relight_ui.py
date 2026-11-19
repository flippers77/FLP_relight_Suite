# Copyright (c) Electric Theatre Collective. Internal use only. See LICENSE.
"""DF_comfy_relight_ui.py - light panel and helpers for the DF_comfy_relight gizmo.
David Filipe / Electric Theatre Collective

The gizmo holds every control as an ordinary Nuke knob. This module adds:
  * LightPanel  - a top-down canvas for dragging lights (PyCustom_Knob)
  * relink()    - binds the BlinkScript kernel parameters to the gizmo knobs
  * reload_kernel() - loads DFComfyRelight.blink from disk and recompiles

Canvas: left-right is image X, bottom-top is distance from camera
(camera at the bottom). Drag = move X and depth, Shift+drag = height,
double-click empty space = switch on the next free light there,
Ctrl+click = light on / off, mouse wheel = zoom.
"""

import math
import os
import re


def _superellipse(cx, cy, rx, ry, n, steps=72):
    pts = []
    for i in range(steps):
        t = 2.0 * math.pi * i / steps
        c, s = math.cos(t), math.sin(t)
        pts.append((cx + rx * math.copysign(abs(c) ** (2.0 / n), c),
                    cy + ry * math.copysign(abs(s) ** (2.0 / n), s)))
    return pts

def figure_polys(cx, cy, bw, bh):
    """Top-down head and shoulders, nose toward the bottom (the camera).
    Returns [(name, [(x, y), ...]), ...] in drawing order, inside the box (cx, cy, bw, bh)."""
    hw, hh = bw / 2.0, bh / 2.0
    def P(u, v):
        return (cx + u * hw, cy + v * hh)
    out = []
    # shoulders: wide rounded slab behind the head, slightly sloped at the ends
    out.append(("shoulders", [P(u, v) for u, v in _superellipse(0.0, -0.38, 1.0, 0.58, 2.6)]))
    # ears, behind the head outline
    for sx in (-1, 1):
        out.append(("ear", [P(u, v) for u, v in _superellipse(sx * 0.33, 0.14, 0.06, 0.13, 2.0, 24)]))
    # head
    out.append(("head", [P(u, v) for u, v in _superellipse(0.0, 0.14, 0.33, 0.56, 2.2)]))
    return out


try:
    import nuke
except ImportError:                      # lets the module be checked outside Nuke
    nuke = None

try:
    from PySide2 import QtCore, QtGui, QtWidgets
except ImportError:
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
    except ImportError:
        QtCore = QtGui = QtWidgets = None

MAX_LIGHTS = 8
KERNEL = "DFComfyRelight"
BS_NAME = "Relight_Kernel"
HERE = os.path.dirname(os.path.abspath(__file__))
KERNEL_FILE = os.path.join(HERE, "DFComfyRelight.blink")
BANNER_FILE = os.path.join(HERE, "df_banner.png")

# knobs that belong to one light; shown only for the selected light
LIGHT_KNOBS = ["title", "enable", "pos", "z", "intensity", "color",
               "fpow", "frad", "directional"]

# kernel parameter -> gizmo knob, for everything that is not per-light
GLOBAL_LINKS = {
    "hdriYaw": "df_hdri_rot_y", "hdriPitch": "df_hdri_rot_x", "hdriRoll": "df_hdri_rot_z",
    "hdriWidth": "df_hdri_width", "hdriDepth": "df_hdri_depth", "hdriHeight": "df_hdri_height",
    "hdriFloor": "df_hdri_floor", "hdriFlat": "df_hdri_flat",
    "reflEnable": "df_refl_enable", "reflInt": "df_refl_int", "reflGain": "df_refl_gain",
    "reflFlipX": "df_refl_flip_x", "reflFlipZ": "df_refl_flip_z", "reflFlipV": "df_refl_flip_v",
    "diffEnable": "df_diff_enable", "diffInt": "df_diff_int", "diffSoft": "df_diff_soft",
    "pointWeight": "df_weight", "ambient": "df_ambient", "wrap": "df_wrap",
    "normals01": "df_normals01", "flipNX": "df_flip_x", "flipNY": "df_flip_y", "flipNZ": "df_flip_z",
    "invertDepth": "df_near_white", "depthScale": "df_depth_scale",
    "occEnable": "df_occ_enable", "occSteps": "df_occ_steps", "occBias": "df_occ_bias",
    "occStrength": "df_occ_strength", "occSoftness": "df_occ_softness", "occMaxDist": "df_occ_reach",
    "rimEnable": "df_rim_enable", "rimPower": "df_rim_power", "rimInt": "df_rim_int",
    "outputMode": "df_output", "useMask": "df_use_mask", "subjectDepth": "df_subject_depth",
    "hdriOn": "df_hdri_on",
    "albedoDisplay": "df_albedo_display", "origLight": "df_orig_light",
}


def link_table():
    """[(kernel parameter, component index, expression)] for every parameter."""
    rows = []
    for i in range(MAX_LIGHTS):
        p = "l%d" % i
        rows += [
            (p + "Enable", 0, "parent.%s_enable" % p),
            (p + "Pos", 0, "parent.%s_pos.x" % p),
            (p + "Pos", 1, "parent.%s_pos.y" % p),
            (p + "Z", 0, "parent.%s_z" % p),
            (p + "Int", 0, "parent.%s_intensity" % p),
            (p + "FPow", 0, "parent.%s_fpow" % p),
            (p + "FRad", 0, "parent.%s_frad" % p),
            (p + "R", 0, "parent.%s_color.r" % p),
            (p + "G", 0, "parent.%s_color.g" % p),
            (p + "B", 0, "parent.%s_color.b" % p),
            (p + "Dir", 0, "parent.%s_directional" % p),
        ]
    for param in sorted(GLOBAL_LINKS):
        expr = "parent.%s" % GLOBAL_LINKS[param]
        if param == "outputMode":
            # menu order (Combined, Lights, Shadows, Rim, Normals check, Relit) -> kernel mode numbers
            expr = "parent.df_output + 2*(parent.df_output>=2) + (parent.df_output>=4)"
        if param == "albedoDisplay":
            # the sRGB linearise inside the kernel is only used when the OCIO conversion is off
            expr = "parent.df_albedo_display*(1-parent.df_ocio_on)"
        rows.append((param, 0, expr))
    return rows


# ---------------------------------------------------------------------------
#  kernel helpers
# ---------------------------------------------------------------------------

def _kernel_node(node):
    try:
        return node.node(BS_NAME)
    except Exception:
        return None


def relink(node):
    """Point every kernel parameter at its gizmo knob. Safe to call repeatedly.
    Returns how many links were (re)made."""
    bs = _kernel_node(node)
    if bs is None:
        return 0
    made = 0
    for param, idx, expr in link_table():
        k = bs.knob("%s_%s" % (KERNEL, param))
        if k is None:
            continue
        try:
            anim = k.animation(idx)
            if anim is not None and (anim.expression() or "") == expr:
                continue
            k.setExpression(expr, idx)
            made += 1
        except Exception as exc:
            print("[DF_comfy_relight] could not link %s: %s" % (param, exc))
    return made


def kernel_ready(node):
    bs = _kernel_node(node)
    return bs is not None and bs.knob("%s_l0Enable" % KERNEL) is not None


def reload_kernel(node=None):
    """Load DFComfyRelight.blink from beside this file, recompile, relink.
    Wired to the 'reload kernel from file' button on the Setup tab."""
    node = node or nuke.thisNode()
    bs = _kernel_node(node)
    if bs is None:
        nuke.message("DF_comfy_relight: kernel node not found inside the gizmo.")
        return
    if not os.path.exists(KERNEL_FILE):
        nuke.message("DF_comfy_relight: missing file\n%s" % KERNEL_FILE)
        return
    with open(KERNEL_FILE) as fh:
        bs["kernelSource"].setValue(fh.read())
    bs["recompile"].execute()
    n = relink(node)
    print("[DF_comfy_relight] kernel reloaded, %d parameters linked" % n)


def _fix_logo(node):
    """Point the Setup-tab banner at the image in this install folder. The path
    is rewritten every time, so a script saved on one machine still shows the
    banner when it is opened on another (Windows <-> Linux included)."""
    try:
        k = node.knob("df_banner")
        if k is None or not os.path.exists(BANNER_FILE):
            return
        good = BANNER_FILE.replace("\\", "/")
        val = k.value()
        new = re.sub(r"src=['\"]?[^'\" >]*df_banner\.png['\"]?", "src='%s'" % good, val)
        if new != val:
            k.setValue(new)
    except Exception:
        pass


def select_light(node, index):
    """Show the native knobs of one light and hide the other seven."""
    for i in range(MAX_LIGHTS):
        for suffix in LIGHT_KNOBS:
            k = node.knob("l%d_%s" % (i, suffix))
            if k is not None:
                k.setVisible(i == index)


# ---------------------------------------------------------------------------
#  knob access used by the canvas
# ---------------------------------------------------------------------------

def _val(node, name, default=0.0):
    k = node.knob(name)
    if k is None:
        return default
    try:
        return k.value()
    except Exception:
        return default


def _set(node, name, value, index=None):
    k = node.knob(name)
    if k is None:
        return
    if index is None:
        k.setValue(value)
    else:
        k.setValue(value, index)


def _image_size(node):
    try:
        w, h = node.width(), node.height()
        if w > 0 and h > 0:
            return float(w), float(h)
    except Exception:
        pass
    return 1920.0, 1080.0


def _depth_range(node):
    near = _val(node, "df_canvas_near", 0.0)
    far = _val(node, "df_canvas_far", 1.0)
    if abs(far - near) < 1e-4:
        far = near + 1.0
    return near, far


# ---------------------------------------------------------------------------
#  Qt panel
# ---------------------------------------------------------------------------

_panels = []          # live LightPanelWidget instances, for repaint on knob change
_driving = False      # True while the canvas itself is writing knobs

if QtWidgets is not None:
    Qt = QtCore.Qt

    WHITE = QtGui.QColor(255, 255, 255)
    BLACK = QtGui.QColor(0, 0, 0)
    GREY = QtGui.QColor(120, 120, 120)
    DIM = QtGui.QColor(60, 60, 60)
    MARGIN = 34
    HIT = 16

    STYLE = """
    QWidget#dfPanel { background: #000000; }
    QPushButton { background: #000000; color: #777777; border: 1px solid #444444;
                  font-weight: bold; min-width: 30px; min-height: 26px; }
    QPushButton#dfAction { color: #ffffff; border: 1px solid #777777; padding: 0px 10px; }
    QPushButton#dfAction:pressed { background: #ffffff; color: #000000; }
    QLabel { color: #999999; background: transparent; }
    QLabel#dfTitle { color: #ffffff; font-weight: bold; font-size: 14px; }
    QSlider::groove:horizontal { height: 2px; background: #555555; }
    QSlider::handle:horizontal { width: 12px; margin: -6px 0px; border-radius: 6px; background: #ffffff; }
    """

    ZOOM_MIN, ZOOM_MAX = 0.25, 4.0

    def canvas_zoom(node):
        try:
            z = float(_val(node, "df_canvas_zoom", 1.0))
        except Exception:
            z = 1.0
        if z <= 0.0:
            z = 1.0
        return min(max(z, ZOOM_MIN), ZOOM_MAX)

    def _lit(node, i):
        return bool(_val(node, "l%d_enable" % i, False))

    def light_qcolor(node, i):
        """The light's colour knob as a display colour. Hue only: scaled so the
        brightest channel is full, so a dim light still shows what colour it is."""
        try:
            c = [max(float(v), 0.0) for v in node.knob("l%d_color" % i).value()[:3]]
            top = max(c)
            if top <= 0.0:
                return QtGui.QColor(255, 255, 255)
            return QtGui.QColor.fromRgbF(*[min(v / top, 1.0) ** 0.4545 for v in c])
        except Exception:
            return QtGui.QColor(255, 255, 255)

    def _ctrl_held(mods):
        return bool(mods & (Qt.ControlModifier | Qt.MetaModifier))

    def toggle_light(node, i):
        """Switch one light on or off (one undo step)."""
        try:
            nuke.Undo.begin("Toggle light %d" % (i + 1))
        except Exception:
            pass
        try:
            _set(node, "l%d_enable" % i, not _val(node, "l%d_enable" % i, False))
        finally:
            try:
                nuke.Undo.end()
            except Exception:
                pass

    def _pos_of(event):
        p = event.position() if hasattr(event, "position") else event.pos()
        return float(p.x()), float(p.y())

    class Canvas(QtWidgets.QWidget):
        selected = QtCore.Signal(int)
        changed = QtCore.Signal()          # something other than a light moved

        def __init__(self, node, parent=None):
            super(Canvas, self).__init__(parent)
            self.node = node
            self.current = 0
            self._drag = None            # None, "ground", "height" or "subject"
            self._subject_rect = None
            self._last = (0.0, 0.0)
            self.setMinimumSize(520, 380)
            self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
            self.setMouseTracking(False)

        # -- mapping: image x / depth  <->  canvas pixels --------------------

        def _to_canvas(self, px, z):
            w, h = float(self.width()), float(self.height())
            iw, _ = _image_size(self.node)
            near, far = _depth_range(self.node)
            cx = MARGIN + (px / iw) * (w - 2 * MARGIN)
            cy = h - MARGIN - ((z - near) / (far - near)) * (h - 2 * MARGIN)
            k = canvas_zoom(self.node)
            return w / 2.0 + (cx - w / 2.0) * k, h / 2.0 + (cy - h / 2.0) * k

        def _from_canvas(self, cx, cy):
            w, h = float(self.width()), float(self.height())
            iw, _ = _image_size(self.node)
            near, far = _depth_range(self.node)
            k = canvas_zoom(self.node)
            cx = w / 2.0 + (cx - w / 2.0) / k
            cy = h / 2.0 + (cy - h / 2.0) / k
            px = (cx - MARGIN) / max(w - 2 * MARGIN, 1.0) * iw
            z = near + (h - MARGIN - cy) / max(h - 2 * MARGIN, 1.0) * (far - near)
            return px, z

        def _light_xy(self, i):
            px = _val(self.node, "l%d_pos" % i, (960.0, 540.0))
            try:
                x = float(px[0])
            except Exception:
                x = 960.0
            return self._to_canvas(x, float(_val(self.node, "l%d_z" % i, 0.2)))

        def _height_of(self, i):
            """Light height as -1..1 (0 = middle of frame)."""
            _, ih = _image_size(self.node)
            px = _val(self.node, "l%d_pos" % i, (960.0, 540.0))
            try:
                return (float(px[1]) / ih - 0.5) * 2.0
            except Exception:
                return 0.0

        def _hit(self, x, y):
            best, best_d = -1, HIT * HIT
            for i in range(MAX_LIGHTS):
                if not _val(self.node, "l%d_enable" % i, False):
                    continue
                lx, ly = self._light_xy(i)
                d = (lx - x) ** 2 + (ly - y) ** 2
                if d <= best_d:
                    best, best_d = i, d
            return best

        # -- painting ------------------------------------------------------

        def paintEvent(self, _event):
            p = QtGui.QPainter(self)
            p.setRenderHint(QtGui.QPainter.Antialiasing, True)
            w, h = self.width(), self.height()
            p.fillRect(0, 0, w, h, BLACK)

            # grid
            p.setPen(QtGui.QPen(DIM, 1))
            iw, _ih = _image_size(self.node)
            near, far = _depth_range(self.node)
            fx0, fy1 = self._to_canvas(0.0, near)        # frame left / camera edge
            fx1, fy0 = self._to_canvas(iw, far)          # frame right / far edge
            for n in range(9):
                gx = fx0 + n * (fx1 - fx0) / 8.0
                p.drawLine(QtCore.QPointF(gx, fy0), QtCore.QPointF(gx, fy1))
            for n in range(7):
                gy = fy0 + n * (fy1 - fy0) / 6.0
                p.drawLine(QtCore.QPointF(fx0, gy), QtCore.QPointF(fx1, gy))
            p.setPen(QtGui.QPen(GREY, 1))
            p.drawRect(QtCore.QRectF(fx0, fy0, fx1 - fx0, fy1 - fy0))

            font = p.font()
            font.setPointSize(8)
            p.setFont(font)
            p.setPen(GREY)
            p.drawText(QtCore.QRectF(0, 6, w, 20), Qt.AlignHCenter, "FAR")
            p.drawText(QtCore.QRectF(0, h - 24, w, 20), Qt.AlignHCenter, "CAMERA")
            p.drawText(QtCore.QRectF(6, h / 2.0 - 10, 24, 20), Qt.AlignLeft, "L")
            p.drawText(QtCore.QRectF(w - 30, h / 2.0 - 10, 24, 20), Qt.AlignRight, "R")

            # centre lines, a little brighter than the grid
            p.setPen(QtGui.QPen(GREY, 1))
            mx, my = (fx0 + fx1) / 2.0, (fy0 + fy1) / 2.0
            p.drawLine(QtCore.QPointF(mx, fy0), QtCore.QPointF(mx, fy1))
            p.drawLine(QtCore.QPointF(fx0, my), QtCore.QPointF(fx1, my))

            # subject: top-down head and shoulders, centred on the subject depth.
            # Drag it to change the depth.
            subject = float(_val(self.node, "df_subject_depth", 0.5))
            _, sy = self._to_canvas(0.0, subject)
            bw = 0.24 * (fx1 - fx0)
            bh = 0.28 * (fy1 - fy0)
            self._subject_rect = QtCore.QRectF(mx - bw / 2.0, sy - bh / 2.0, bw, bh)
            p.setPen(QtGui.QPen(WHITE, 1.5))
            p.setBrush(QtGui.QBrush(QtGui.QColor(34, 34, 34)))
            for _name, pts in figure_polys(mx, sy, bw, bh):
                p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(x, y) for x, y in pts]))
            p.setBrush(Qt.NoBrush)
            p.setPen(WHITE)
            p.drawText(QtCore.QRectF(mx - 80, sy + bh / 2.0 + 2, 160, 16), Qt.AlignCenter,
                       "SUBJECT   d %.3f" % subject)

            # lights
            bold = p.font()
            bold.setPointSize(9)
            bold.setBold(True)
            p.setFont(bold)
            for i in range(MAX_LIGHTS):
                if not _val(self.node, "l%d_enable" % i, False):
                    continue
                gx, gy = self._light_xy(i)
                stem = self._height_of(i) * 26.0
                # ground mark and height stem
                p.setPen(QtGui.QPen(GREY, 1))
                p.drawLine(QtCore.QPointF(gx - 4, gy), QtCore.QPointF(gx + 4, gy))
                p.drawLine(QtCore.QPointF(gx, gy), QtCore.QPointF(gx, gy - stem))
                centre = QtCore.QPointF(gx, gy - stem)
                sel = (i == self.current)
                col = light_qcolor(self.node, i)
                # soft glow in the light's colour, larger for brighter lights
                inten = min(max(float(_val(self.node, "l%d_intensity" % i, 1.0)), 0.0), 4.0)
                radius = 34.0 + 10.0 * inten
                glow = QtGui.QRadialGradient(centre, radius)
                inner = QtGui.QColor(col)
                inner.setAlpha(130 if sel else 90)
                outer = QtGui.QColor(col)
                outer.setAlpha(0)
                glow.setColorAt(0.0, inner)
                glow.setColorAt(1.0, outer)
                p.setPen(Qt.NoPen)
                p.setBrush(QtGui.QBrush(glow))
                p.drawEllipse(centre, radius, radius)
                # the light itself: filled with its colour, white ring when selected
                p.setPen(QtGui.QPen(WHITE, 2.5) if sel else QtGui.QPen(BLACK, 1.5))
                p.setBrush(QtGui.QBrush(col))
                r = 14.0 if sel else 12.0
                p.drawEllipse(centre, r, r)
                p.setFont(bold)
                p.setPen(BLACK if col.lightness() > 110 else WHITE)
                p.drawText(QtCore.QRectF(gx - 14, gy - stem - 14, 28, 28), Qt.AlignCenter, str(i + 1))
                # readout: distance from camera and height (-1..1)
                p.setFont(font)
                p.setPen(col)
                label = "d %.3f  h %.2f" % (float(_val(self.node, "l%d_z" % i, 0.0)), self._height_of(i))
                p.drawText(QtCore.QRectF(gx - 70, gy - stem + r + 4, 140, 14), Qt.AlignHCenter, label)
            p.setBrush(Qt.NoBrush)
            p.end()

        # -- mouse ---------------------------------------------------------

        def mousePressEvent(self, event):
            # Ctrl+click (Cmd+click on Mac) switches a light off. On a Mac, Ctrl+click
            # can arrive as a right-click, so that is accepted too.
            ctrl = _ctrl_held(event.modifiers())
            if event.button() != Qt.LeftButton and not (ctrl and event.button() == Qt.RightButton):
                return
            x, y = _pos_of(event)
            # a light is drawn at the top of its height stem, so test there too
            hit = self._hit(x, y)
            if hit < 0:
                for i in range(MAX_LIGHTS):
                    if not _val(self.node, "l%d_enable" % i, False):
                        continue
                    lx, ly = self._light_xy(i)
                    ly -= self._height_of(i) * 26.0
                    if (lx - x) ** 2 + (ly - y) ** 2 <= HIT * HIT:
                        hit = i
                        break
            if hit < 0:
                # nothing hit: a press on the subject box starts dragging its depth
                inside = self._subject_rect is not None and self._subject_rect.contains(QtCore.QPointF(x, y))
                if inside and not ctrl:
                    self._drag = "subject"
                    self._last = (x, y)
                    try:
                        nuke.Undo.begin("Move subject depth")
                    except Exception:
                        pass
                return
            if ctrl:
                toggle_light(self.node, hit)
                self.update()
                return
            self.current = hit
            self.selected.emit(hit)
            self._drag = "height" if (event.modifiers() & Qt.ShiftModifier) else "ground"
            self._last = (x, y)
            try:
                nuke.Undo.begin("Move light %d" % (hit + 1))
            except Exception:
                pass
            self.update()

        def mouseMoveEvent(self, event):
            global _driving
            if self._drag is None:
                return
            x, y = _pos_of(event)
            i = self.current
            iw, ih = _image_size(self.node)
            _driving = True
            try:
                if self._drag == "subject":
                    cur = float(_val(self.node, "df_subject_depth", 0.5))
                    _, sy = self._to_canvas(0.0, cur)
                    _, z = self._from_canvas(0.0, sy + (y - self._last[1]))
                    _set(self.node, "df_subject_depth", min(max(z, 0.0), 1.0))
                elif self._drag == "height":
                    dy = self._last[1] - y
                    cur = float(self.node.knob("l%d_pos" % i).value()[1])
                    _set(self.node, "l%d_pos" % i, cur + dy / 52.0 * ih, 1)
                else:
                    gx, gy = self._light_xy(i)
                    px, z = self._from_canvas(gx + (x - self._last[0]), gy + (y - self._last[1]))
                    _set(self.node, "l%d_pos" % i, px, 0)
                    _set(self.node, "l%d_z" % i, z)
            finally:
                _driving = False
            self._last = (x, y)
            if self._drag == "subject":
                self.changed.emit()        # keeps the slider under the canvas in step
            self.update()

        def mouseReleaseEvent(self, _event):
            if self._drag is not None:
                self._drag = None
                try:
                    nuke.Undo.end()
                except Exception:
                    pass

        def wheelEvent(self, event):
            try:
                steps = event.angleDelta().y() / 120.0
            except Exception:
                steps = 0.0
            if steps:
                z = min(max(canvas_zoom(self.node) * (1.1 ** steps), ZOOM_MIN), ZOOM_MAX)
                _set(self.node, "df_canvas_zoom", z)
                self.update()
            event.accept()                 # stop the properties panel scrolling

        def mouseDoubleClickEvent(self, event):
            x, y = _pos_of(event)
            if self._hit(x, y) >= 0:
                return
            for i in range(MAX_LIGHTS):
                if not _val(self.node, "l%d_enable" % i, False):
                    px, z = self._from_canvas(x, y)
                    _set(self.node, "l%d_pos" % i, px, 0)
                    _set(self.node, "l%d_z" % i, z)
                    _set(self.node, "l%d_enable" % i, True)
                    self.current = i
                    self.selected.emit(i)
                    self.update()
                    return

    class LightPanelWidget(QtWidgets.QWidget):
        def __init__(self, node, parent=None):
            super(LightPanelWidget, self).__init__(parent)
            self.node = node
            self._syncing = False
            self.setObjectName("dfPanel")
            self.setAttribute(Qt.WA_StyledBackground, True)
            self.setStyleSheet(STYLE)

            self.canvas = Canvas(node, self)
            self.canvas.selected.connect(self._on_canvas_select)
            self.canvas.changed.connect(self.refresh)

            self.status = QtWidgets.QLabel("", self)

            # slot buttons, then add / remove
            self.buttons = []
            row = QtWidgets.QHBoxLayout()
            row.setSpacing(6)
            group = QtWidgets.QButtonGroup(self)
            group.setExclusive(True)
            for i in range(MAX_LIGHTS):
                b = QtWidgets.QPushButton(str(i + 1), self)
                b.setCheckable(True)
                b.clicked.connect(lambda _checked=False, n=i: self._slot_clicked(n))
                group.addButton(b)
                row.addWidget(b)
                self.buttons.append(b)
            row.addSpacing(12)
            add_btn = QtWidgets.QPushButton("+ add light", self)
            add_btn.setObjectName("dfAction")
            add_btn.clicked.connect(lambda _checked=False: self._add_light())
            remove_btn = QtWidgets.QPushButton("- remove light", self)
            remove_btn.setObjectName("dfAction")
            remove_btn.clicked.connect(lambda _checked=False: self._remove_light())
            row.addWidget(add_btn)
            row.addWidget(remove_btn)
            row.addStretch(1)

            # sliders: subject depth and canvas zoom
            grid = QtWidgets.QGridLayout()
            grid.setHorizontalSpacing(10)
            self.subject_slider, self.subject_value = self._slider_row(grid, 0, "subject depth")
            self.zoom_slider, self.zoom_value = self._slider_row(grid, 1, "zoom")
            self.subject_slider.valueChanged.connect(self._subject_moved)
            self.zoom_slider.valueChanged.connect(self._zoom_moved)

            # selected light header with the colour picker
            head = QtWidgets.QHBoxLayout()
            self.title = QtWidgets.QLabel("Light 1", self)
            self.title.setObjectName("dfTitle")
            pick_btn = QtWidgets.QPushButton("pick colour...", self)
            pick_btn.setObjectName("dfAction")
            pick_btn.clicked.connect(lambda _checked=False: self._pick_colour())
            head.addWidget(self.title)
            head.addStretch(1)
            head.addWidget(pick_btn)

            hint = QtWidgets.QLabel(
                "drag: move   |   shift+drag: height   |   double-click: add   |   "
                "ctrl+click: on / off   |   wheel: zoom", self)

            lay = QtWidgets.QVBoxLayout(self)
            lay.setContentsMargins(8, 8, 8, 8)
            lay.setSpacing(8)
            lay.addWidget(self.canvas, 1)
            lay.addWidget(self.status)
            lay.addLayout(row)
            lay.addLayout(grid)
            lay.addLayout(head)
            lay.addWidget(hint)

            self._frame = None
            self._timer = QtCore.QTimer(self)
            self._timer.setInterval(150)
            self._timer.timeout.connect(self._tick)
            self._timer.start()

            _panels.append(self)
            first = 0
            for i in range(MAX_LIGHTS):
                if _lit(node, i):
                    first = i
                    break
            self.select(first)

        def _slider_row(self, grid, r, text):
            label = QtWidgets.QLabel(text, self)
            slider = QtWidgets.QSlider(Qt.Horizontal, self)
            slider.setRange(0, 1000)
            value = QtWidgets.QLabel("", self)
            value.setMinimumWidth(48)
            value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(label, r, 0)
            grid.addWidget(slider, r, 1)
            grid.addWidget(value, r, 2)
            return slider, value

        # -- sliders -------------------------------------------------------

        def _subject_moved(self, v):
            if self._syncing:
                return
            _set(self.node, "df_subject_depth", v / 1000.0)
            self.refresh()

        def _zoom_moved(self, v):
            if self._syncing:
                return
            z = ZOOM_MIN * (ZOOM_MAX / ZOOM_MIN) ** (v / 1000.0)
            _set(self.node, "df_canvas_zoom", z)
            self.refresh()

        # -- buttons -------------------------------------------------------

        def _slot_clicked(self, index):
            # Ctrl+click (Cmd+click on Mac) a slot button switches that light on or off
            if _ctrl_held(QtWidgets.QApplication.keyboardModifiers()):
                toggle_light(self.node, index)
            self.select(index)

        def _add_light(self):
            """Switch on the next free light, in front of the subject."""
            for i in range(MAX_LIGHTS):
                if _lit(self.node, i):
                    continue
                iw, ih = _image_size(self.node)
                subject = float(_val(self.node, "df_subject_depth", 0.5))
                try:
                    nuke.Undo.begin("Add light %d" % (i + 1))
                except Exception:
                    pass
                try:
                    _set(self.node, "l%d_pos" % i, iw * 0.5, 0)
                    _set(self.node, "l%d_pos" % i, ih * 0.65, 1)
                    _set(self.node, "l%d_z" % i, max(subject - 0.25, 0.02))
                    _set(self.node, "l%d_enable" % i, True)
                finally:
                    try:
                        nuke.Undo.end()
                    except Exception:
                        pass
                self.select(i)
                return

        def _remove_light(self):
            """Switch off the selected light and move to another one that is on."""
            i = self.canvas.current
            if _lit(self.node, i):
                toggle_light(self.node, i)
            for j in range(MAX_LIGHTS):
                if _lit(self.node, j):
                    self.select(j)
                    return
            self.refresh()

        def _pick_colour(self):
            """Colour dialog for the selected light. The pick is a display colour,
            so it is converted to linear before it goes on the knob."""
            i = self.canvas.current
            col = QtWidgets.QColorDialog.getColor(light_qcolor(self.node, i), self,
                                                  "Light %d colour" % (i + 1))
            if not col.isValid():
                return
            k = self.node.knob("l%d_color" % i)
            if k is None:
                return
            try:
                nuke.Undo.begin("Light %d colour" % (i + 1))
            except Exception:
                pass
            try:
                for c, v in enumerate((col.redF(), col.greenF(), col.blueF())):
                    k.setValue(v ** 2.2, c)
            finally:
                try:
                    nuke.Undo.end()
                except Exception:
                    pass
            self.refresh()

        # -- selection and refresh ------------------------------------------

        def select(self, index):
            self.canvas.current = index
            self.buttons[index].setChecked(True)
            select_light(self.node, index)
            self.refresh()

        def _on_canvas_select(self, index):
            self.buttons[index].setChecked(True)
            select_light(self.node, index)
            self.refresh()

        def refresh(self):
            # slot buttons take the colour of their light when it is switched on
            count = 0
            for i, b in enumerate(self.buttons):
                if _lit(self.node, i):
                    count += 1
                    col = light_qcolor(self.node, i)
                    name = col.name()
                    ink = "#000000" if col.lightness() > 110 else "#ffffff"
                    css = ("QPushButton { color: %s; border: 1px solid %s; }"
                           "QPushButton:checked { background: %s; color: %s; }" % (name, name, name, ink))
                else:
                    css = "QPushButton:checked { border: 1px solid #ffffff; color: #ffffff; }"
                if b.styleSheet() != css:
                    b.setStyleSheet(css)

            cur = self.canvas.current
            state = "" if _lit(self.node, cur) else "  (off)"
            self.title.setText("Light %d%s" % (cur + 1, state))
            tcss = "color: %s;" % (light_qcolor(self.node, cur).name() if _lit(self.node, cur) else "#777777")
            if self.title.styleSheet() != tcss:
                self.title.setStyleSheet(tcss)

            near, far = _depth_range(self.node)
            zoom = canvas_zoom(self.node)
            subject = float(_val(self.node, "df_subject_depth", 0.5))
            self.status.setText("%d of %d lights on   |   depth %.2f to %.2f   |   zoom %.2fx"
                                % (count, MAX_LIGHTS, near, far, zoom))
            self._syncing = True
            try:
                self.subject_slider.setValue(int(round(min(max(subject, 0.0), 1.0) * 1000)))
                self.subject_value.setText("%.3f" % subject)
                t = math.log(zoom / ZOOM_MIN) / math.log(ZOOM_MAX / ZOOM_MIN)
                self.zoom_slider.setValue(int(round(t * 1000)))
                self.zoom_value.setText("%.2fx" % zoom)
            finally:
                self._syncing = False
            self.canvas.update()

        def _tick(self):
            # repaint while the timeline plays so animated lights move
            try:
                f = nuke.frame()
            except Exception:
                return
            if f != self._frame:
                self._frame = f
                self.canvas.update()


class LightPanel(object):
    """What the gizmo's PyCustom_Knob creates. Nuke calls makeUI()."""

    def __init__(self, node):
        self.node = node

    def makeUI(self):
        _fix_logo(self.node)
        try:
            if not kernel_ready(self.node):
                reload_kernel(self.node)          # first use on this machine
            else:
                relink(self.node)
        except Exception as exc:
            print("[DF_comfy_relight] kernel setup: %s" % exc)
        return LightPanelWidget(self.node)

    def updateValue(self):
        pass


# colourspaces the passes were sent to ComfyUI in, and the working space they go back to
OCIO_FROM = ["out_rec709", "Rec.1886 Rec.709 - Display", "Output - Rec.709", "sRGB - Display", "Output - sRGB"]
OCIO_TO = ["ACES - ACEScg", "ACEScg", "scene_linear"]
OCIO_NODES = ("OCIO_albedo", "OCIO_irradiance")


def _pick(values, wanted):
    """First entry of an OCIO menu that matches a wanted name (menus may prefix a family path)."""
    for w in wanted:
        for v in values:
            if v == w or v.endswith("/" + w):
                return v
    return None


def _sync_ocio(node):
    """Keep the irradiance conversion identical to the albedo one (the two dropdowns shown are the albedo node's)."""
    try:
        a, b = node.node(OCIO_NODES[0]), node.node(OCIO_NODES[1])
        for k in ("in_colorspace", "out_colorspace"):
            if b[k].value() != a[k].value():
                b[k].setValue(a[k].value())
    except Exception:
        pass


def init_node(node):
    """Run once when the node is created from the menu: make sure the default OCIO names exist in this
    Nuke's config, otherwise pick the nearest, or switch the conversion off rather than leave the node in error."""
    try:
        a = node.node(OCIO_NODES[0])
        vin, vout = a["in_colorspace"].values(), a["out_colorspace"].values()
        fin, fout = _pick(vin, OCIO_FROM), _pick(vout, OCIO_TO)
        if fin and fout:
            a["in_colorspace"].setValue(fin)
            a["out_colorspace"].setValue(fout)
        else:
            node["df_ocio_on"].setValue(False)
            nuke.warning("DF_comfy_relight: could not find the default colourspaces in this OCIO config. "
                         "Pick 'from' and 'to' on the Setup tab and tick 'convert albedo / irradiance'.")
        _sync_ocio(node)
    except Exception as e:
        nuke.warning("DF_comfy_relight: colourspace setup skipped (%s)" % e)
    return node


def knob_changed():
    """Gizmo knobChanged hook: repaint open panels when a knob changes."""
    if _driving:
        return
    try:
        _sync_ocio(nuke.thisNode())
    except Exception:
        pass
    for panel in list(_panels):
        try:
            panel.refresh()
        except Exception:                 # panel was closed and deleted by Qt
            try:
                _panels.remove(panel)
            except ValueError:
                pass
