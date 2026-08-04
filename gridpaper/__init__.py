from krita import Krita

from .gridpaper import GridPaperExtension

Krita.instance().addExtension(GridPaperExtension(Krita.instance()))
