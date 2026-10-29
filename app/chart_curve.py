"""Shape-preserving cubic traces: original samples, smooth tangents, no overshoot."""
from bisect import bisect_right
from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainterPath

class SmoothTrace:
    def __init__(self,points):
        self.points=tuple(QPointF(p) for p in points);self.x=[p.x() for p in self.points]
        self.path=QPainterPath();self.slopes=[]
        if not points:return
        self.path.moveTo(self.points[0])
        if len(points)==1:self.slopes=[0.];return
        h=[b.x()-a.x() for a,b in zip(self.points,self.points[1:])]
        if any(v<=0 for v in h):raise ValueError('Chart time axis must increase')
        d=[(b.y()-a.y())/v for a,b,v in zip(self.points,self.points[1:],h)]
        if len(points)==2:m=[d[0],d[0]]
        else:
            def endpoint(h0,h1,d0,d1):
                slope=((2*h0+h1)*d0-h0*d1)/(h0+h1)
                if slope*d0<=0:return 0.
                if d0*d1<0 and abs(slope)>abs(3*d0):return 3*d0
                return slope
            m=[endpoint(h[0],h[1],d[0],d[1])]
            for i in range(1,len(points)-1):
                if d[i-1]*d[i]<=0:m.append(0.)
                else:
                    w1=2*h[i]+h[i-1];w2=h[i]+2*h[i-1]
                    m.append((w1+w2)/(w1/d[i-1]+w2/d[i]))
            m.append(endpoint(h[-1],h[-2],d[-1],d[-2]))
        self.slopes=m
        for i,(a,b,width) in enumerate(zip(self.points,self.points[1:],h)):
            self.path.cubicTo(QPointF(a.x()+width/3,a.y()+m[i]*width/3),QPointF(b.x()-width/3,b.y()-m[i+1]*width/3),b)
    def head(self,progress):
        if not self.points:return None
        x=self.x[0]+(self.x[-1]-self.x[0])*max(0.,min(1.,progress))
        if len(self.points)==1 or x>=self.x[-1]:return QPointF(self.points[-1])
        i=max(0,bisect_right(self.x,x)-1);a,b=self.points[i:i+2];width=b.x()-a.x();t=(x-a.x())/width
        y=(2*t**3-3*t*t+1)*a.y()+(t**3-2*t*t+t)*width*self.slopes[i]+(-2*t**3+3*t*t)*b.y()+(t**3-t*t)*width*self.slopes[i+1]
        return QPointF(x,y)
