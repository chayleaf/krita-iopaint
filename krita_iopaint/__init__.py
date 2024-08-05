from .krita_iopaint import KritaIopaint

Krita.instance().addExtension(KritaIopaint(Krita.instance()))
