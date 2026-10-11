# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Achilleus
"""Native Aero glass: a bounded OpenGL backdrop, with a still painter fallback.

The environment and lens formulas adapt the MIT-licensed glass effects in
Aki's Rockbox Scrobbler, Copyright (c) 2026 Achilleus. See
licenses/Rockbox-Scrobbler-MIT.txt. Text, controls and video stay native Qt.
"""
from __future__ import annotations

import os
import struct
import time

from PySide6.QtCore import QEvent, QPointF, QRectF, QTimer, Qt, Signal
from PySide6.QtGui import (
    QColor, QImage, QLinearGradient, QOpenGLContext, QOffscreenSurface,
    QPainter, QPen, QRadialGradient, QSurfaceFormat, QVector2D, QVector3D,
    QVector4D,
)
from PySide6.QtOpenGL import QOpenGLBuffer, QOpenGLFramebufferObject, QOpenGLShader, QOpenGLShaderProgram
from PySide6.QtWidgets import QApplication, QFrame, QWidget

VERTEX = """
#version 120
attribute vec2 aPosition;
varying vec2 vUV;
void main() { vUV = aPosition*.5+.5; gl_Position = vec4(aPosition,0.,1.); }
"""

FRAGMENT = """
#version 120
varying vec2 vUV;
uniform vec2 uResolution;
uniform float uTime;
uniform vec3 uPointer;
uniform vec4 uClick;
uniform vec4 uHeader;
uniform vec4 uLeft;
uniform vec4 uRight;
uniform vec4 uSettings;
float cloud(vec2 p, vec2 c, vec2 stretch) {
    vec2 d=(p-c)/stretch; return exp(-dot(d,d)*2.);
}
vec3 scene(vec2 px) {
    vec2 p=px/uResolution; float t=uTime*.045;
    vec3 c=vec3(.85,.94,.97);
    c=mix(c,vec3(.32,.78,.89),cloud(p,vec2(.13+sin(t)*.04,.20),vec2(.60,.65))*.78);
    c=mix(c,vec3(.76,.73,.93),cloud(p,vec2(.90,.25+cos(t)*.05),vec2(.46,.58))*.65);
    c=mix(c,vec3(.46,.87,.69),cloud(p,vec2(.78,.88),vec2(.65,.53))*.70);
    float ribbon=p.y-(.28+.25*sin(p.x*4.1+t)+.045*sin(p.x*10.-t*.8));
    c=mix(c,vec3(.94,.99,1.),exp(-ribbon*ribbon*200.)*.68);
    c+=vec3(.17,.20,.22)*exp(-pow(abs(ribbon-.038),2.)*14000.);
    float second=p.y-(.74+.17*cos(p.x*5.2-t*.7));
    c=mix(c,vec3(.46,.80,.88),exp(-second*second*550.)*.24);
    c+=vec3(.15)*exp(-pow(second-.019,2.)*14000.);
    return c;
}
float box(vec2 p,vec2 halfSize) {
    vec2 q=abs(p)-(halfSize-22.);
    return length(max(q,0.))+min(max(q.x,q.y),0.)-22.;
}
vec3 lens(vec3 base,vec2 screen,vec4 r,float dark) {
    if(r.z<1.) return base;
    vec2 local=screen-r.xy-r.zw*.5; float d=box(local,r.zw*.5);
    if(d>1.5) {
        float shadow=exp(-max(d,0.)/10.)*.065;
        return base*(1.-shadow);
    }
    vec2 n=normalize(vec2(box(local+vec2(.7,0.),r.zw*.5)-box(local-vec2(.7,0.),r.zw*.5),
                          box(local+vec2(0.,.7),r.zw*.5)-box(local-vec2(0.,.7),r.zw*.5))+vec2(.0001));
    float rim=exp(min(d,0.)/11.);
    vec2 delta=screen-uPointer.xy;
    float hover=exp(-dot(delta,delta)/22000.)*uPointer.z;
    vec2 bend=n*rim*25.+delta*hover*.12;
    vec2 wave=screen-uClick.xy; float distance=length(wave);
    float ring=distance-uClick.z*220.;
    float amplitude=exp(-uClick.z*2.)*exp(-ring*ring/1200.)*uClick.w;
    bend+=wave/max(distance,1.)*sin(ring*.085)*amplitude*11.;
    vec2 point=screen-bend; vec2 dispersion=n*rim*1.35;
    vec3 c=vec3(scene(point+dispersion).r,scene(point).g,scene(point-dispersion).b);
    vec3 soft=(scene(point+vec2(3.,2.))+scene(point-vec2(3.,2.)))*.5;
    c=mix(c,soft,(1.-rim)*.32);
    c=mix(c,vec3(.98,.995,1.),.38+(1.-rim)*.16);
    if(dark>.5) c=mix(c,vec3(.045,.29,.43),.84);
    vec2 light=normalize(uPointer.xy-(r.xy+r.zw*.5)+vec2(-180.,-230.));
    float reflection=pow(max(dot(n,light),0.),5.);
    c+=vec3(.18,.21,.23)*rim*reflection+vec3(.07,.09,.10)*hover;
    c+=vec3(.35)*exp(-abs(d+1.5))*(.25+reflection*.75);
    return mix(base,c,1.-smoothstep(-.75,1.5,d));
}
void main() {
    vec2 p=vec2(vUV.x,1.-vUV.y)*uResolution;
    vec3 c=scene(p);
    c=lens(c,p,uHeader,1.); c=lens(c,p,uLeft,0.);
    c=lens(c,p,uRight,0.); c=lens(c,p,uSettings,0.);
    gl_FragColor=vec4(clamp(c,0.,1.),1.);
}
"""


class GlassRenderer:
    """Render offscreen to avoid mixing GL widgets with native video playback."""
    def __init__(self):
        self.context = None
        self.surface = None
        self.program = None
        self.buffer = None
        self.fbo = None
        self.error = ""
        self.locations = {}

    def initialize(self):
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            self.error = "Still glass in headless mode."
            return False
        try:
            fmt = QSurfaceFormat(); fmt.setVersion(2, 1); fmt.setDepthBufferSize(0); fmt.setStencilBufferSize(0)
            self.context = QOpenGLContext(); self.context.setFormat(fmt)
            if not self.context.create():
                raise RuntimeError("OpenGL context unavailable.")
            self.surface = QOffscreenSurface(); self.surface.setFormat(self.context.format()); self.surface.create()
            if not self.surface.isValid() or not self.context.makeCurrent(self.surface):
                raise RuntimeError("Offscreen graphics surface unavailable.")
            self.program = QOpenGLShaderProgram()
            if not self.program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Vertex, VERTEX):
                raise RuntimeError(self.program.log())
            if not self.program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Fragment, FRAGMENT) or not self.program.link():
                raise RuntimeError(self.program.log())
            self.locations = {name:self.program.uniformLocation(name) for name in ("uResolution","uTime","uPointer","uClick","uHeader","uLeft","uRight","uSettings")}
            self.buffer = QOpenGLBuffer(); self.buffer.create(); self.buffer.bind()
            quad = struct.pack("8f", -1, -1, 1, -1, -1, 1, 1, 1)
            self.buffer.allocate(quad, len(quad)); self.buffer.release()
            self.context.doneCurrent()
            return True
        except Exception as exc:
            self.error = str(exc)
            self.close()
            return False

    def draw(self, width, height, seconds, pointer, click, rectangles):
        if not self.context.makeCurrent(self.surface):
            raise RuntimeError("Graphics context lost.")
        try:
            ratio = min(1., 1024 / max(width, height))
            w, h = max(1, round(width*ratio)), max(1, round(height*ratio))
            if self.fbo is None or self.fbo.width() != w or self.fbo.height() != h:
                self.fbo = QOpenGLFramebufferObject(w,h)
            if not self.fbo.isValid() or not self.fbo.bind():
                raise RuntimeError("Glass framebuffer unavailable.")
            functions = self.context.functions(); functions.glViewport(0,0,w,h)
            self.program.bind(); self.buffer.bind()
            position = self.program.attributeLocation("aPosition")
            self.program.enableAttributeArray(position)
            self.program.setAttributeBuffer(position,0x1406,0,2)
            self.program.setUniformValue(self.locations["uResolution"],QVector2D(width,height))
            self.program.setUniformValue(self.locations["uTime"],float(seconds))
            self.program.setUniformValue(self.locations["uPointer"],QVector3D(*pointer))
            self.program.setUniformValue(self.locations["uClick"],QVector4D(*click))
            for name, rect in zip(("uHeader","uLeft","uRight","uSettings"),rectangles):
                self.program.setUniformValue(self.locations[name],QVector4D(rect.x(),rect.y(),rect.width(),rect.height()))
            functions.glDrawArrays(0x0005,0,4)
            self.program.disableAttributeArray(position); self.buffer.release(); self.program.release()
            frame = self.fbo.toImage()
            self.fbo.release()
            return frame
        finally:
            self.context.doneCurrent()

    def close(self):
        if self.context and self.surface and self.context.makeCurrent(self.surface):
            self.fbo = None
            if self.buffer:
                self.buffer.destroy(); self.buffer = None
            self.program = None
            self.context.doneCurrent()
        self.context = None
        self.surface = None


class AeroBackdrop(QWidget):
    availabilityChanged = Signal(bool)

    def __init__(self):
        super().__init__()
        self.setObjectName("base")
        self.setMouseTracking(True)
        self.renderer = GlassRenderer()
        self.frame = QImage()
        self.panels = []
        self.enabled = True
        self.available = False
        self.started = False
        self.elapsed = 0.
        self.last_tick = time.monotonic()
        self.pointer = [-1000.,-1000.,0.]
        self.click = [-1000.,-1000.,0.,0.]
        self.click_time = -100.
        self.timer = QTimer(self); self.timer.setInterval(50); self.timer.timeout.connect(self.tick)
        QApplication.instance().installEventFilter(self)

    def set_live(self, enabled):
        self.enabled = enabled
        self.frame = QImage()
        if enabled and self.available:
            self.last_tick = time.monotonic(); self.timer.start(); self.tick(force=True)
        else:
            self.timer.stop()
        self.update()
        for panel in self.panels:
            panel.update()

    def showEvent(self, event):
        super().showEvent(event)
        if not self.started:
            self.started = True
            QTimer.singleShot(0,self.start)

    def start(self):
        self.available = self.renderer.initialize()
        self.availabilityChanged.emit(self.available)
        self.set_live(self.enabled)
        for widget in self.window().findChildren(QWidget):
            widget.setMouseTracking(True)

    def tick(self, force=False):
        now = time.monotonic()
        delta = min(.1,now-self.last_tick); self.last_tick = now
        if not self.enabled or not self.available or not self.isVisible():
            return
        if not force and (self.window().isMinimized() or not self.window().isActiveWindow()):
            return
        self.elapsed += delta
        self.click[2] = max(0,self.elapsed-self.click_time)
        self.click[3] = 1. if self.click[2] < 2.5 else 0.
        rects = [QRectF(panel.geometry()) for panel in self.panels]
        rects += [QRectF()] * (4-len(rects))
        try:
            self.frame = self.renderer.draw(self.width(),self.height(),self.elapsed,self.pointer,self.click,rects[:4])
            self.update()
        except Exception as exc:
            self.renderer.error = str(exc); self.available = False
            self.renderer.close(); self.availabilityChanged.emit(False); self.set_live(False)

    def eventFilter(self, watched, event):
        if isinstance(watched,QWidget) and watched.window() is self.window():
            if event.type() in (QEvent.Type.MouseMove,QEvent.Type.MouseButtonPress):
                point = self.mapFromGlobal(event.globalPosition().toPoint())
                self.pointer = [float(point.x()),float(point.y()),1.]
                if event.type() == QEvent.Type.MouseButtonPress:
                    self.click[:2] = self.pointer[:2]; self.click_time = self.elapsed
            elif event.type() == QEvent.Type.Leave and watched is self:
                self.pointer[2] = 0.
        return False

    def paintEvent(self, _event):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.frame.isNull() and self.enabled and self.available:
            p.drawImage(self.rect(),self.frame)
            return
        gradient = QLinearGradient(0,0,self.width(),self.height())
        gradient.setColorAt(0,QColor("#b5e9f2")); gradient.setColorAt(.48,QColor("#e7f4fb")); gradient.setColorAt(1,QColor("#c9ede5"))
        p.fillRect(self.rect(),gradient)
        for x,y,color in ((.08,.05,"#8cd2ee"),(.97,.30,"#c8bfe9"),(.72,.91,"#a0e4bf")):
            glow = QRadialGradient(QPointF(self.width()*x,self.height()*y),max(self.width(),self.height())*.60)
            glow.setColorAt(0,QColor(color)); end=QColor(color); end.setAlpha(0); glow.setColorAt(1,end)
            p.fillRect(self.rect(),glow)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for offset in (0,20,42):
            p.setPen(QPen(QColor(255,255,255,110-offset),1.5))
            p.drawEllipse(QRectF(self.width()*.38,self.height()*.63+offset,self.width()*.95,self.height()*.5))

    def close_renderer(self):
        self.timer.stop()
        QApplication.instance().removeEventFilter(self)
        self.renderer.close()


class GlassPanel(QFrame):
    def __init__(self, backdrop, dark=False):
        super().__init__()
        self.backdrop = backdrop
        self.dark = dark
        self.setObjectName("glassHeader" if dark else "panel")
        backdrop.panels.append(self)

    def paintEvent(self, _event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect=QRectF(self.rect()).adjusted(1,1,-1,-1)
        shader=self.backdrop.available and self.backdrop.enabled and not self.backdrop.frame.isNull()
        gradient=QLinearGradient(rect.topLeft(),rect.bottomRight())
        if shader:
            gradient.setColorAt(0,QColor(255,255,255,18)); gradient.setColorAt(1,QColor(255,255,255,3))
        elif self.dark:
            gradient.setColorAt(0,QColor("#207d9a")); gradient.setColorAt(1,QColor("#154867"))
        else:
            gradient.setColorAt(0,QColor(255,255,255,185)); gradient.setColorAt(1,QColor(240,250,255,145))
        p.setBrush(gradient); p.setPen(QPen(QColor(255,255,255,210),1.))
        p.drawRoundedRect(rect,22,22)
        p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor(255,255,255,95),1.))
        p.drawRoundedRect(rect.adjusted(2,2,-2,-2),20,20)
