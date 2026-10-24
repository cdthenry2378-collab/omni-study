"""Reusable spring interpolation, particle burst, and validation tone helpers."""
from PyQt6.QtCore import Qt, QTimer, QPointF
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget
import math, random

class SpringValue:
    def __init__(self, value=0.0, stiffness=190.0, damping=22.0):
        self.value = self.target = float(value)
        self.velocity = 0.0
        self.stiffness, self.damping = stiffness, damping

    def step(self, dt: float) -> float:
        dt = min(max(dt, 0.0), 0.05)
        acceleration = self.stiffness * (self.target - self.value) - self.damping * self.velocity
        self.velocity += acceleration * dt
        self.value += self.velocity * dt
        return self.value

class ParticleOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.particles = []
        self.timer = QTimer(self); self.timer.timeout.connect(self._tick)

    def burst(self, x=None, y=None, count=32):
        cx = self.width()/2 if x is None else x
        cy = self.height()/2 if y is None else y
        for _ in range(max(1, min(150, count))):
            angle = random.random() * math.tau
            speed = random.uniform(60, 260)
            self.particles.append([cx, cy, math.cos(angle)*speed, math.sin(angle)*speed, random.uniform(.35,.8)])
        if not self.timer.isActive(): self.timer.start(16)
        self.show(); self.raise_()

    def _tick(self):
        dt = .016
        for p in self.particles:
            p[0] += p[2]*dt; p[1] += p[3]*dt; p[3] += 110*dt; p[4] -= dt
        self.particles = [p for p in self.particles if p[4] > 0]
        self.update()
        if not self.particles:
            self.timer.stop(); self.hide()

    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for x,y,vx,vy,life in self.particles:
            color = QColor("#00F0FF"); color.setAlphaF(max(0, min(1, life/.8)))
            painter.setPen(QPen(color, 2)); painter.drawPoint(QPointF(x,y))

def validation_chime():
    try:
        import winsound
        winsound.Beep(880, 65); winsound.Beep(1320, 85)
    except (ImportError, RuntimeError):
        try:
            from PyQt6.QtWidgets import QApplication
            QApplication.beep()
        except Exception:
            pass
