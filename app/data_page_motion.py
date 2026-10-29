"""Short body-only crossfade; headers and the native window never disappear."""
from PySide6.QtCore import Qt,QVariantAnimation,QEasingCurve,QPoint
from PySide6.QtGui import QPainter,QPixmap,QColor,QRegion
from PySide6.QtWidgets import QWidget
from ui_theme import SURFACE

class PageFade(QWidget):
    @staticmethod
    def snapshot(widget):
        ratio=widget.devicePixelRatioF()
        image=QPixmap(round(widget.width()*ratio),round(widget.height()*ratio));image.setDevicePixelRatio(ratio)
        # A transparent scroll viewport has no standalone backing background.
        # Seed the actual card colour, otherwise Windows can capture black.
        image.fill(QColor(SURFACE));widget.render(image,QPoint(),QRegion(),QWidget.RenderFlag.DrawChildren)
        return image
    def __init__(self,parent):
        super().__init__(parent);self.frame=None;self.opacity=0.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents);self.hide()
        self.animation=QVariantAnimation(self);self.animation.setDuration(160)
        self.animation.setStartValue(1.);self.animation.setEndValue(0.)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(self.advance);self.animation.finished.connect(self.clear)
    def present(self,frame,rect):
        self.animation.stop();self.frame=frame;self.opacity=1.;self.setGeometry(rect)
        self.show();self.raise_();self.animation.start()
    def advance(self,value):self.opacity=float(value);self.update()
    def clear(self):self.animation.stop();self.hide();self.frame=None
    def paintEvent(self,event):
        if self.frame is not None:
            p=QPainter(self);p.setOpacity(self.opacity);p.drawPixmap(0,0,self.frame)
