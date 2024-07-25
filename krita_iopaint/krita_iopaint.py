import json
import requests
from PyQt5.QtCore import QBuffer, QByteArray, QUrl
from PyQt5.QtGui import QImage
from PyQt5.QtNetwork import QNetworkRequest, QNetworkReply, QNetworkAccessManager

from krita import *

# IOPaint API URL
URL = "http://127.0.0.1:8080/api/v1/inpaint"

# context pixels to include around selection
PAD = 256


def clamp(doc, coords):
    if coords[0] < doc.x():
        coords[0] = doc.x()
    if coords[1] < doc.y():
        coords[1] = doc.y()
    if coords[2] > doc.width():
        coords[2] = doc.width()
    if coords[3] > doc.height():
        coords[3] = doc.height()


def img2b(img: QImage) -> bytes:
    buf = QBuffer()
    img.save(buf, "png")
    return buf.data().toBase64().data()


def img2b64(img: QImage) -> str:
    return "data:image/png;base64," + img2b(img).decode("utf-8")


def img_bytes(img: QImage) -> QByteArray:
    bits = img.constBits()
    data = QByteArray(bits.asstring(img.byteCount()))
    return data


def apply_mask(img: QImage, mask: QImage) -> QImage:
    img1 = [*img_bytes(img).data()]
    mask1 = img_bytes(mask).data()
    for i, pix in enumerate(mask1):
        img1[i * 4 + 3] = pix

    return QImage(
        QByteArray(bytes(img1)), img.width(), img.height(), QImage.Format.Format_ARGB32
    )


class KritaIopaint(Extension):
    def __init__(self, parent):
        super().__init__(parent)
        self.net = QNetworkAccessManager()
        self.inst = None

    # Krita.instance() exists, so do any setup work
    def setup(self):
        self.inst = Krita.instance()

    # called after setup(self)
    def createActions(self, window):
        action = window.createAction("iopaint_run", "IOPaint")
        action.triggered.connect(self.run)

    def run(self) -> None:
        doc = self.inst.activeDocument()
        sel = doc.selection().duplicate()
        node = doc.activeNode()
        coords = [
            sel.x() - node.position().x(),
            sel.y() - node.position().y(),
            sel.width(),
            sel.height(),
        ]
        pcoords = [
            coords[0] - PAD,
            coords[1] - PAD,
            coords[2] + PAD * 2,
            coords[3] + PAD * 2,
        ]
        clamp(node.bounds(), coords)
        clamp(node.bounds(), pcoords)

        mask = QImage(
            sel.pixelData(*pcoords),
            *pcoords[2:],
            pcoords[2],
            QImage.Format.Format_Grayscale8
        )
        img = QImage(
            node.pixelData(*pcoords), *pcoords[2:], QImage.Format.Format_ARGB32
        )

        mask_b64 = img2b64(mask)
        img_b64 = img2b64(img)
        res = requests.post(URL, json={"image": img_b64, "mask": mask_b64})
        res.raise_for_status()

        parent = node

        node = parent.duplicate()
        data = res.content
        img = QImage.fromData(data, "png").convertToFormat(QImage.Format.Format_ARGB32)
        bits = img.constBits()
        data = QByteArray(bits.asstring(img.byteCount()))
        img = apply_mask(img, mask)
        node.setPixelData(data, *pcoords)
        doc.rootNode().addChildNode(node, parent)
        node.mergeDown()
