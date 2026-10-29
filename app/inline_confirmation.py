"""Destructive commands are confirmed inside the existing editor surface."""
from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QScrollArea
from ui_theme import DANGER_SURFACE
from card_motion import AnimatedDisclosure


class InlineConfirmation(AnimatedDisclosure):
    def __init__(self,parent=None):
        body=QWidget();super().__init__(body,parent,background=DANGER_SURFACE);self.callback=None
        self.setObjectName('inline_confirmation')
        layout=QVBoxLayout(body);layout.setContentsMargins(1,0,1,0);layout.setSpacing(5)
        self.message=QLabel();self.message.setTextFormat(Qt.TextFormat.PlainText);self.message.setWordWrap(True);layout.addWidget(self.message)
        row=QHBoxLayout();row.addStretch()
        self.cancel_button=QPushButton('取消');self.cancel_button.clicked.connect(self.cancel);row.addWidget(self.cancel_button)
        self.confirm_button=QPushButton();self.confirm_button.setObjectName('confirm_destructive')
        self.confirm_button.clicked.connect(self.confirm);row.addWidget(self.confirm_button);layout.addLayout(row)
        self.confirm_button.setProperty('role','danger');self.cancel_button.setAutoDefault(False);self.confirm_button.setAutoDefault(False)
        self.settled.connect(self._focus_cancel)

    def _focus_cancel(self,expanded):
        if expanded and self.callback is not None and self.isVisible():self.cancel_button.setFocus()

    def request(self,text,callback,label='确认删除'):
        self.callback=callback;self.message.setText(text);self.confirm_button.setText(label)
        self.confirm_button.setEnabled(True);self.cancel_button.setEnabled(True)
        if self.expanded:self.refresh_content()
        self.set_expanded(True)
        # An accidental second Enter must not accept a destructive operation.
        if self._animating:self.setFocusPolicy(Qt.FocusPolicy.StrongFocus);self.setFocus()
        else:self.cancel_button.setFocus()
        parent=self.parentWidget()
        while parent is not None:
            if isinstance(parent,QScrollArea):
                QTimer.singleShot(0,self,lambda area=parent:area.ensureWidgetVisible(self));break
            parent=parent.parentWidget()

    def cancel(self):
        self.callback=None;self.confirm_button.setEnabled(False);self.set_expanded(False)

    def confirm(self):
        callback=self.callback;self.cancel()
        if callback is not None:callback()
    def keyPressEvent(self,event):
        if self.callback is not None and event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):event.accept();return
        super().keyPressEvent(event)
