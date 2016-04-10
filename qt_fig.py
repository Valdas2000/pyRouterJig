###########################################################################
#
# Copyright 2015-2016 Robert B. Lowrie (http://github.com/lowrie)
#
# This file is part of pyRouterJig.
#
# pyRouterJig is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# pyRouterJig is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# pyRouterJig; see the file LICENSE. If not, see <http://www.gnu.org/licenses/>.
#
###########################################################################

'''
Contains the Qt functionality for drawing the template and boards.
'''
from __future__ import print_function
from __future__ import division
from future.utils import lrange

import time

import router
import utils

from PyQt4 import QtCore, QtGui
#from PySide import QtCore, QtGui

def paint_text(painter, text, coord, flags, shift=(0, 0), angle=0, fill=None):
    '''
    Puts text at coord with alignment flags.  Returns a QRect of the bounding box
    of the text that was painted.

    painter: QPainter object
    text: The text to print.
    coord: The coordinate at which to place the text
    flags: QtCore.Qt alignment flags
    shift: Adjustments in coord, in pixels
    angle: Rotation angle
    fill: If not None, a QBrush that fills the bounding rectangle behind the text.
    '''
    # Save the current transform, then switch to transform that places the origin
    # at coord and rotated by angle.
    transform = painter.transform()
    (x, y) = transform.map(coord[0], coord[1])
    x += shift[0]
    y += shift[1]
    painter.resetTransform()
    painter.translate(x, y)
    painter.rotate(angle)
    # Create a large rectangle and use it to find the bounding rectangle around the text.
    # Find the origin of the rectangle based on the alignment.
    big = 5000
    xorg = 0
    yorg = 0
    if flags & QtCore.Qt.AlignRight:
        xorg = -big
    elif flags & QtCore.Qt.AlignHCenter:
        xorg = -big // 2
    if flags & QtCore.Qt.AlignBottom:
        yorg = -big
    elif flags & QtCore.Qt.AlignVCenter:
        yorg = -big // 2
    rect = QtCore.QRectF(xorg, yorg, big, big)
    rect = painter.boundingRect(rect, flags, text)
    # Draw the text
    if fill is not None:
        painter.fillRect(rect, fill)
    painter.drawText(rect, flags, text)
    # Find the text rectangle in our original coordinate system
    rect1 = painter.transform().mapRect(rect)
    (inverted, invertable) = transform.inverted()
    rect = inverted.mapRect(rect1)
    # Restore the original transform
    painter.setTransform(transform)
    return rect

class Qt_Fig(QtGui.QWidget):
    '''
    Interface to the qt_driver, using Qt to draw the boards and template.
    The attribute "canvas" is self, to mimic the old interface to matplotlib,
    which this class replaced.
    '''
    def __init__(self, template, boards, config):
        QtGui.QWidget.__init__(self)
        self.canvas = self
        self.config = config
        self.fig_width = -1
        self.fig_height = -1
        self.set_fig_dimensions(template, boards)
        self.geom = None
        color = QtGui.QColor(*config.background_color)
        self.background = QtGui.QBrush(color)
        self.current_background = self.background
        self.labels = ['B', 'C', 'D', 'E', 'F']
        # font sizes are in 1/32" of an inch
        self.font_size = {'title':4,
                          'fingers':3,
                          'template':3,
                          'boards':4,
                          'template_labels':3,
                          'watermark':4}
        self.transform = None
        self.base_transform = None
        self.mouse_pos = None
        self.scaling = 1.0
        self.translate = [0.0, 0.0]

    def minimumSizeHint(self):
        '''
        Minimum size for this widget
        '''
        return QtCore.QSize(100, 100)

    def sizeHint(self):
        '''
        Size hint for this widget
        '''
        return QtCore.QSize(self.window_width, self.window_height)

    def set_fig_dimensions(self, template, boards):
        '''
        Computes the figure dimension attributes, fig_width and fig_height, in
        increments.
        Returns True if the dimensions changed.
        '''
        # Try default margins, but reset if the template is too small for margins
        units = boards[0].units
        top_margin = units.abstract_to_increments(self.config.top_margin)
        bottom_margin = units.abstract_to_increments(self.config.bottom_margin)
        left_margin = units.abstract_to_increments(self.config.left_margin)
        right_margin = units.abstract_to_increments(self.config.right_margin)
        separation = units.abstract_to_increments(self.config.separation)
        self.margins = utils.Margins(separation, separation, left_margin, right_margin,
                                     bottom_margin, top_margin)

        # Set the figure dimensions
        fig_width = template.length + self.margins.left + self.margins.right
        fig_height = template.height + self.margins.bottom + self.margins.top
        for i in lrange(4):
            if boards[i].active:
                fig_height += boards[i].height + self.margins.sep

        if boards[3].active:
            fig_height += template.height + self.margins.sep

        if self.config.show_caul:
            fig_height += template.height + self.margins.sep

        min_width = 64
        if fig_width < min_width:
            fig_width = min_width
            self.margins.left = (fig_width - template.length) // 2
            self.margins.right = self.margins.left
            fig_width = template.length + self.margins.left + self.margins.right

        dimensions_changed = False
        if fig_width != self.fig_width:
            self.fig_width = fig_width
            dimensions_changed = True
        if fig_height != self.fig_height:
            self.fig_height = fig_height
            dimensions_changed = True

        # The 1200 here is effectively a dpi for the screen
        scale = 1200 * boards[0].units.increments_to_inches(1)
        self.window_width = int(scale * fig_width)
        self.window_height = int(scale * fig_height)

        return dimensions_changed

    def draw(self, template, boards, bit, spacing, woods, description):
        '''
        Draws the figure
        '''
        # Generate the new geometry layout
        self.set_fig_dimensions(template, boards)
        self.woods = woods
        self.description = description
        self.geom = router.Joint_Geometry(template, boards, bit, spacing, self.margins,
                                          self.config)
        self.current_background = self.background
        self.update()

    def print(self, template, boards, bit, spacing, woods, description):
        '''
        Prints the figure
        '''
        self.woods = woods
        self.current_background = None
        self.description = description

        # Generate the new geometry layout
        self.set_fig_dimensions(template, boards)
        self.geom = router.Joint_Geometry(template, boards, bit, spacing, self.margins,
                                          self.config)

        # Print through the preview dialog
        printer = QtGui.QPrinter(QtGui.QPrinter.HighResolution)
        printer.setOrientation(QtGui.QPrinter.Landscape)
        printer.setPageMargins(0, 0, 0, 0, QtGui.QPrinter.Inch)
        pdialog = QtGui.QPrintPreviewDialog(printer)
        pdialog.setModal(True)
        pdialog.paintRequested.connect(self.preview_requested)
        return pdialog.exec_()

    def image(self, template, boards, bit, spacing, woods, description):
        '''
        Prints the figure to a QImage object
        '''
        self.woods = woods
        self.description = description
        self.set_fig_dimensions(template, boards)
        self.geom = router.Joint_Geometry(template, boards, bit, spacing, self.margins,
                                          self.config)
        self.current_background = self.background

        s = self.size()
        window_ar = float(s.width()) / s.height()
        fig_ar = float(self.fig_width) / self.fig_height
        if window_ar < fig_ar:
            w = s.width()
        else:
            w = int(s.height() * fig_ar)
        w = max(self.config.min_image_width, min(self.config.max_image_width, w))
        h = utils.my_round(w / fig_ar)
        sNew = QtCore.QSize(w, h)

        im = QtGui.QImage(sNew, QtGui.QImage.Format_RGB32)
        painter = QtGui.QPainter()
        painter.begin(im)
        size = im.size()
        painter.fillRect(0, 0, size.width(), size.height(), self.background)
        self.paint_all(painter)
        painter.end()
        return im

    def preview_requested(self, printer):
        '''
        Handles the print preview action.
        '''
        dpi = printer.resolution() * self.config.print_scale_factor
        painter = QtGui.QPainter()
        painter.begin(printer)
        self.paint_all(painter, dpi)
        painter.end()

    def paintEvent(self, event):
        '''
        Handles the paint event, which draws to the screen
        '''
        if self.geom is None:
            return

        painter = QtGui.QPainter(self)
        size = self.size()
        # on the screen, we add a background color:
        painter.fillRect(0, 0, size.width(), size.height(), self.background)
        # paint all of the objects
        self.window_width, self.window_height = self.paint_all(painter)
        # on the screen, highlight the active cuts
        self.draw_active_cuts(painter)
        painter.end()

    def set_font_size(self, painter, param):
        '''
        Sets the font size for font type param
        '''
        font_inches = self.font_size[param] / 32.0 * self.geom.bit.units.increments_per_inch
        dx = self.transform.map(font_inches, 0)[0] - self.transform.dx()
        font = painter.font()
        font.setPixelSize(utils.my_round(dx))
        painter.setFont(font)

    def paint_all(self, painter, dpi=None):
        '''
        Paints all the objects.

        painter: A QPainter object
        dpi: The resolution of the painter, in dots-per-inch.  If None, then
             the image is maximized in the window, but maintaining aspect ratio.
        '''
        rw = painter.window()
        window_width = rw.width()
        window_height = rw.height()
        units = self.geom.bit.units

        if dpi is None:
            # transform the painter to maintain the figure aspect ratio in the current
            # window
            window_ar = float(window_width) / window_height
            fig_ar = float(self.fig_width) / self.fig_height
            if fig_ar < window_ar:
                w = utils.my_round(fig_ar * window_height)
                painter.translate((window_width - w) // 2, window_height)
                scale = float(window_height) / self.fig_height
            else:
                h = utils.my_round(window_width / fig_ar)
                painter.translate(0, (window_height + h) // 2)
                scale = float(window_width) / self.fig_width
        else:
            # Scale so that the image is the correct size on the page
            painter.translate(0, window_height)
            scale = float(dpi) / units.increments_per_inch
        painter.scale(scale, -scale)

        # Save the inverse of the un-zoomed transform
        (self.base_transform, invertable) = painter.transform().inverted()

        # Apply the zoom, zooming on the current figure center
        painter.scale(self.scaling, self.scaling)
        factor = 0.5 - 0.5 / self.scaling
        x = self.translate[0] - self.fig_width * factor
        y = self.translate[1] - self.fig_height * factor
        painter.translate(x, y)
        self.transform = painter.transform()

        # draw the objects
        painter.setPen(QtCore.Qt.black)
        self.draw_boards(painter)
        self.draw_template(painter)
        self.draw_title(painter)
        if self.config.show_finger_widths:
            self.draw_finger_sizes(painter)

        return (window_width, window_height)

    def draw_passes(self, painter, blabel, cuts, y1, y2, flags, xMid,
                    template=True):
        '''
        Draws and labels the router passes on a template or board.

        painter: The QPainter object
        blabel: The board label (A, B, C, ...)
        cuts: Array of router.Cut objects
        y1: y-location where pass label is placed
        y2: y-location where end of line is located
        flags: Horizontal alignment for label
        xMid: x-location of board center
        template: If true, then a template

        Returns the pass label if a pass matches xMid, None otherwise
        '''
        board_T = self.geom.board_T
        #brush = QtGui.QBrush(QtGui.QColor(255, 0, 0, 100))
        brush = None
        shift = (0, 0) # for adjustments of text
        passMid = None # location of board-center pass (return value)
        font_type = 'template'
        char_size = self.font_size[font_type]
        self.set_font_size(painter, font_type)
        # Collect the router pass locations in a single array by looping
        # through each cut and each pass for each cut, right-to-left.
        xp = []
        for c in cuts[::-1]:
            for p in lrange(len(c.passes) - 1, -1, -1):
                xp.append(c.passes[p])
        # Loop through the passes and do the labels
        np = len(xp)
        for i in lrange(np):
            # Determine vertical alignment, by checking the separation from adjacent passes.
            # If too close to an adjacent pass, then shift the alignment in the opposite
            # direction.
            flagsv = flags
            diffm = xp[max(0, i - 1)] - xp[i]
            diffp = xp[i] - xp[min(np - 1, i + 1)]
            if i == 0:
                if diffp < char_size:
                    flagsv |= QtCore.Qt.AlignTop
                else:
                    flagsv |= QtCore.Qt.AlignVCenter
            elif i == np - 1:
                if diffm < char_size:
                    flagsv |= QtCore.Qt.AlignBottom
                else:
                    flagsv |= QtCore.Qt.AlignVCenter
            elif diffp < char_size:
                if diffm < char_size:
                    flagsv |= QtCore.Qt.AlignVCenter
                else:
                    flagsv |= QtCore.Qt.AlignTop
            else:
                if diffm < char_size:
                    flagsv |= QtCore.Qt.AlignBottom
                else:
                    flagsv |= QtCore.Qt.AlignVCenter
            xpShift = xp[i] + board_T.xL()
            # Draw the text label for this pass
            label = ''
            if template or self.config.show_router_pass_identifiers:
                label = '%d%s' % (i + 1, blabel)
                if xpShift == xMid:
                    passMid = label
            if not template and self.config.show_router_pass_locations:
                if len(label) > 0:
                    label += ': '
                loc = self.geom.bit.units.increments_to_string(board_T.xR() - xpShift)
                label += loc
            r = paint_text(painter, label, (xpShift, y1), flagsv, shift, -90, fill=brush)
            # Determine the line starting point from the size of the text.
            # Create a small margin so that the starting point is not too
            # close to the text.
            y1text = y1
            if y1 > y2:
                y1text = r.y()
                if y1text > y2:
                    y1text += 0.05 * (y2 - y1text)
            else:
                y1text = r.y() + r.height()
                if y1text < y2:
                    y1text += 0.05 * (y2 - y1text)
            # If there is any room left, draw the line from the label to the base of cut
            if (y1 - y2) * (y1text - y2) > 0:
                p1 = QtCore.QPointF(xpShift, y1text)
                p2 = QtCore.QPointF(xpShift, y2)
                painter.drawLine(p1, p2)
        return passMid

    def draw_alignment(self, painter):
        '''
        Draws the alignment lines on all templates
        '''
        board_T = self.geom.board_T
        board_TDD = self.geom.board_TDD
        board_caul = self.geom.board_caul

        # draw the alignment lines on both templates
        #x = board_T.xL() + passes[iMax] - pMax // 2
        x = board_T.xR() + self.geom.bit.width // 2
        painter.setPen(QtCore.Qt.SolidLine)
        self.set_font_size(painter, 'template')
        label = 'ALIGN'
        flags = QtCore.Qt.AlignTop | QtCore.Qt.AlignHCenter
        for b in [board_T, board_TDD, board_caul]:
            if b is not None:
                y1 = b.yB()
                y2 = b.yT()
                painter.drawLine(x, y1, x, y2)
                paint_text(painter, label, (x, (y1 + y2) // 2), flags, (0, 0), -90)

    def draw_template_rectangle(self, painter, r, b):
        '''
        Draws the geometry of a template
        '''
        # Fill the entire template as white
        painter.fillRect(r.xL(), r.yB(), r.width, r.height, QtCore.Qt.white)

        # Fill the template margins with a grayshade
        brush = QtGui.QBrush(QtGui.QColor(220, 220, 220))
        painter.fillRect(r.xL(), r.yB(), b.xL() - r.xL(), r.height, brush)
        painter.fillRect(b.xR(), r.yB(), r.xR() - b.xR(), r.height, brush)

        # Draw the template bounding box
        painter.drawRect(r.xL(), r.yB(), r.width, r.height)

        # Label the template with a watermark
        if self.description is not None:
            painter.save()
            self.set_font_size(painter, 'watermark')
            color = QtGui.QColor(0, 0, 0, 75)
            painter.setPen(color)
            flags = QtCore.Qt.AlignVCenter | QtCore.Qt.AlignHCenter
            x = r.xL() + r.width // 2
            y = r.yB() + r.height // 2
            paint_text(painter, self.description, (x, y), flags)
            painter.restore()

    def draw_template(self, painter):
        '''
        Draws the Incra templates
        '''
        rect_T = self.geom.rect_T
        board_T = self.geom.board_T
        boards = self.geom.boards

        xMid = board_T.xMid()
        centerline = []
        centerline_TDD = []

        self.draw_template_rectangle(painter, rect_T, board_T)
        if boards[3].active:
            rect_TDD = self.geom.rect_TDD
            board_TDD = self.geom.board_TDD
            self.draw_template_rectangle(painter, rect_TDD, board_TDD)
            rect_top = rect_TDD
        else:
            rect_top = rect_T

        flagsL = QtCore.Qt.AlignLeft
        flagsR = QtCore.Qt.AlignRight
        show_passes = self.config.show_router_pass_identifiers | self.config.show_router_pass_locations

        frac_depth = 0.95 * self.geom.bit.depth
        sepOver2 = 0.5 * self.geom.margins.sep
        # Draw the router passes
        # ... do the top board passes
        y1 = boards[0].yB() - sepOver2
        y2 = boards[0].yB() + frac_depth
        pm = self.draw_passes(painter, 'A', boards[0].bottom_cuts, rect_top.yMid(),
                              rect_top.yT(), flagsR, xMid)
        if pm is not None:
            if boards[3].active:
                centerline_TDD.append(pm)
            else:
                centerline.append(pm)
        if show_passes:
            self.draw_passes(painter, 'A', boards[0].bottom_cuts, y1, y2,
                             flagsL, xMid, False)
        label_bottom = 'A,B'
        label_top = None
        i = 0
        # Do double-double passes
        if boards[3].active:
            painter.setPen(QtCore.Qt.DashLine)
            y1 = boards[3].yT() + sepOver2
            y2 = boards[3].yT() - frac_depth
            pm = self.draw_passes(painter, self.labels[i], boards[3].top_cuts, rect_TDD.yMid(),
                                  rect_TDD.yT(), flagsR, xMid)
            if pm is not None:
                centerline_TDD.append(pm)
            if show_passes:
                self.draw_passes(painter, self.labels[i], boards[3].top_cuts, y1, y2,
                                 flagsR, xMid, False)
            painter.setPen(QtCore.Qt.SolidLine)
            y1 = boards[3].yB() - sepOver2
            y2 = boards[3].yB() + frac_depth
            pm = self.draw_passes(painter, self.labels[i + 1], boards[3].bottom_cuts, rect_TDD.yMid(), \
                                  rect_TDD.yB(), flagsL, xMid) 
            if pm is not None:
                centerline_TDD.append(pm)
            if show_passes:
                self.draw_passes(painter, self.labels[i + 1], boards[3].bottom_cuts, y1, y2,
                                 flagsL, xMid, False)
            label_bottom = 'D,E,F'
            label_top = 'A,B,C'
            i += 2
        # Do double passes
        if boards[2].active:
            painter.setPen(QtCore.Qt.DashLine)
            y1 = boards[2].yT() + sepOver2
            y2 = boards[2].yT() - frac_depth
            pm = self.draw_passes(painter, self.labels[i], boards[2].top_cuts, rect_T.yMid(),
                                  rect_T.yT(), flagsR, xMid)
            if pm is not None:
                centerline.append(pm)
            if show_passes:
                self.draw_passes(painter, self.labels[i], boards[2].top_cuts, y1, y2,
                                 flagsR, xMid, False)
            y1 = boards[2].yB() - sepOver2
            y2 = boards[2].yB() + frac_depth
            pm = self.draw_passes(painter, self.labels[i + 1], boards[2].bottom_cuts, rect_T.yMid(),
                                  rect_T.yB(), flagsL, xMid)
            if pm is not None:
                centerline.append(pm)
            if show_passes:
                self.draw_passes(painter, self.labels[i + 1], boards[2].bottom_cuts, y1, y2,
                                 flagsL, xMid, False)
            painter.setPen(QtCore.Qt.SolidLine)
            if not boards[3].active:
                label_bottom = 'A,B,C,D'
            i += 2

        # ... do the bottom board passes
        y1 = boards[1].yT() + sepOver2
        y2 = boards[1].yT() - frac_depth
        pm = self.draw_passes(painter, self.labels[i], boards[1].top_cuts, rect_T.yMid(),
                              rect_T.yB(), flagsL, xMid)
        if pm is not None:
            centerline.append(pm)
        if show_passes:
            self.draw_passes(painter, self.labels[i], boards[1].top_cuts, y1, y2,
                             flagsR, xMid, False)

        flagsLC = QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter
        flagsRC = QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter

        # ... draw the caul template and do its passes.  Draw events may be
        # triggered before we have the ability to recreate the geom object,
        # so we have to ensure the caul_top object actually exists.
        datetime = time.strftime('\n%d %b %Y %H:%M', time.localtime())
        if self.config.show_caul and self.geom.caul_top is not None:
            rect_caul = self.geom.rect_caul
            board_caul = self.geom.board_caul
            top = self.geom.caul_top
            bottom = self.geom.caul_bottom
            self.draw_template_rectangle(painter, rect_caul, board_caul)
            centerline_caul = []
            pm = self.draw_passes(painter, 'A', top, rect_caul.yMid(), rect_caul.yT(), flagsR, xMid)
            if pm is not None:
                centerline_caul.append(pm)
            pm = self.draw_passes(painter, self.labels[i], bottom, rect_caul.yMid(),\
                                  rect_caul.yB(), flagsL, xMid)
            if pm is not None:
                centerline_caul.append(pm)
            self.set_font_size(painter, 'template_labels')
            label = 'Cauls'
            if len(centerline_caul) > 0:
                label += '\nCenter: ' + centerline_caul[0]
            else:
                painter.setPen(QtCore.Qt.DashLine)
                painter.drawLine(xMid, rect_caul.yB(), xMid, rect_caul.yT())
            paint_text(painter, label + datetime, (rect_caul.xL(), rect_caul.yMid()), flagsLC, (5, 0))
            paint_text(painter, label, (rect_caul.xR(), rect_caul.yMid()), flagsRC, (-5, 0))

        # Label the templates
        self.set_font_size(painter, 'template_labels')
        if len(centerline) > 0:
            label_bottom += '\nCenter: ' + centerline[0]
        else:
            painter.setPen(QtCore.Qt.DashLine)
            painter.drawLine(xMid, rect_T.yB(), xMid, rect_T.yT())
        paint_text(painter, label_bottom + datetime, (rect_T.xL(), rect_T.yMid()), flagsLC, (5, 0))
        paint_text(painter, label_bottom, (rect_T.xR(), rect_T.yMid()), flagsRC, (-5, 0))
        if label_top is not None:
            if len(centerline_TDD) > 0:
                label_top += '\nCenter: ' + centerline_TDD[0]
            else:
                painter.setPen(QtCore.Qt.DashLine)
                painter.drawLine(xMid, rect_TDD.yB(), xMid, rect_TDD.yT())
            paint_text(painter, label_top + datetime, (rect_TDD.xL(), rect_TDD.yMid()), flagsLC, (5, 0))
            paint_text(painter, label_top, (rect_TDD.xR(), rect_TDD.yMid()), flagsRC, (-5, 0))

        self.draw_alignment(painter)

    def draw_one_board(self, painter, board, bit, fill_color):
        '''
        Draws a single board
        '''
        if not board.active:
            return
        (x, y) = board.perimeter(bit)
        painter.save()
        pen = QtGui.QPen(QtCore.Qt.black)
        pen.setWidthF(0)
        painter.setPen(pen)
        icon = self.woods[board.wood]
        if icon is not None:
            if isinstance(icon, str):
                brush = QtGui.QBrush(QtGui.QPixmap(icon))
            else:
                if icon == QtCore.Qt.SolidPattern:
                    color = QtGui.QColor(*fill_color)
                else:
                    color = QtCore.Qt.black
                brush = QtGui.QBrush(color, icon)
            (inverted, invertable) = self.transform.inverted()
            brush.setMatrix(inverted.toAffine())
            painter.setBrush(brush)
        n = len(x)
        poly = QtGui.QPolygonF()
        for i in lrange(n):
            poly.append(QtCore.QPointF(x[i], y[i]))
        painter.drawPolygon(poly)
        painter.restore()

    def draw_boards(self, painter):
        '''
        Draws all the boards
        '''

        # Draw all of the boards
        for i in lrange(4):
            self.draw_one_board(painter, self.geom.boards[i], self.geom.bit,
                                self.config.board_fill_colors[i])

        # Label the boards
        if self.config.show_router_pass_identifiers or self.config.show_router_pass_locations:
            painter.setPen(QtCore.Qt.SolidLine)
            x1 = self.geom.boards[0].xL() - self.geom.bit.width // 2
            x2 = self.geom.boards[0].xL() - self.geom.bit.width // 4
            flags = QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter
            self.set_font_size(painter, 'boards')

            y = self.geom.boards[0].yB()
            p = (x1, y)
            paint_text(painter, 'A', p, flags, (-3, 0))
            painter.drawLine(x1, y, x2, y)

            i = 0 # index in self.labels

            if self.geom.boards[3].active:
                y = self.geom.boards[3].yT()
                p = (x1, y)
                paint_text(painter, 'B', p, flags, (-3, 0))
                painter.drawLine(x1, y, x2, y)
                y = self.geom.boards[3].yB()
                p = (x1, y)
                paint_text(painter, 'C', p, flags, (-3, 0))
                painter.drawLine(x1, y, x2, y)
                i = 2
            if self.geom.boards[2].active:
                y = self.geom.boards[2].yT()
                p = (x1, y)
                paint_text(painter, self.labels[i], p, flags, (-3, 0))
                painter.drawLine(x1, y, x2, y)
                y = self.geom.boards[2].yB()
                p = (x1, y)
                paint_text(painter, self.labels[i + 1], p, flags, (-3, 0))
                painter.drawLine(x1, y, x2, y)
                i += 2

            y = self.geom.boards[1].yT()
            p = (x1, y)
            paint_text(painter, self.labels[i], p, flags, (-3, 0))
            painter.drawLine(x1, y, x2, y)

    def cut_polygon(self, c):
        '''
        Forms the polygon for the cut corresponding to the cut c
        '''
        boards = self.geom.boards
        xLT = boards[0].xL() + c.xmin
        xRT = boards[0].xL() + c.xmax
        xLB = xLT
        xRB = xRT
        if c.xmin > 0:
            xLB += self.geom.bit.offset
        if c.xmax < self.geom.boards[0].width:
            xRB -= self.geom.bit.offset
        yB = boards[0].yB()
        yT = yB + self.geom.bit.depth
        poly = QtGui.QPolygonF()
        poly.append(QtCore.QPointF(xLT, yT))
        poly.append(QtCore.QPointF(xRT, yT))
        poly.append(QtCore.QPointF(xRB, yB))
        poly.append(QtCore.QPointF(xLB, yB))
        poly.append(QtCore.QPointF(xLT, yT))
        return poly

    def draw_active_cuts(self, painter):
        '''
        If the spacing supports it, highlight the active cuts and
        draw their limits
        '''
        # draw the perimeter of the cursor cut
        f = self.geom.spacing.cursor_cut
        if f is None:
            return
        poly = self.cut_polygon(self.geom.boards[0].bottom_cuts[f])
        painter.save()
        pen = QtGui.QPen(QtCore.Qt.blue)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawPolyline(poly)
        painter.restore()

        # initialize limits
        xminG = self.geom.boards[0].width
        xmaxG = 0

        # draw the active cuts filled, and track the limits
        painter.save()
        brush = QtGui.QBrush(QtGui.QColor(255, 0, 0, 75))
        painter.setBrush(brush)
        for f in self.geom.spacing.active_cuts:
            poly = self.cut_polygon(self.geom.boards[0].bottom_cuts[f])
            painter.drawPolygon(poly)
            # keep track of the limits
            (xmin, xmax) = self.geom.spacing.get_limits(f)
            xminG = min(xminG, xmin)
            xmaxG = max(xmaxG, xmax)
        painter.restore()

        # draw the limits
        painter.save()
        xminG += self.geom.boards[0].xL()
        xmaxG += self.geom.boards[0].xL()
        yB = self.geom.boards[0].yB()
        yT = self.geom.boards[0].yT()
        painter.setPen(QtCore.Qt.green)
        painter.drawLine(xminG, yB, xminG, yT)
        painter.drawLine(xmaxG, yB, xmaxG, yT)
        painter.restore()

    def draw_title(self, painter):
        '''
        Draws the title
        '''
        self.set_font_size(painter, 'title')
        title = router.create_title(self.geom.boards, self.geom.bit, self.geom.spacing)
        flags = QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop
        p = (self.geom.board_T.xMid(), self.margins.bottom)
        paint_text(painter, title, p, flags, (0, 5))

    def draw_finger_sizes(self, painter):
        '''
        Annotates the finger sizes on each board
        '''
        units = self.geom.bit.units
        self.set_font_size(painter, 'template')
        # Determine the cuts that are adjacent to board-A and board-B
        acuts = self.geom.boards[1].top_cuts
        bcuts = self.geom.boards[0].bottom_cuts
        if self.geom.boards[2].active:
            bcuts = self.geom.boards[2].bottom_cuts
            if self.geom.boards[3].active:
                acuts = self.geom.boards[3].top_cuts
            else:
                acuts = self.geom.boards[2].top_cuts
        # Draw the router passes
        # ... do the B cuts
        flags = QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop
        shift = (0, 8)
        for c in bcuts:
            x = self.geom.boards[1].xL() + (c.xmin + c.xmax) // 2
            y = self.geom.boards[1].yT()
            label = units.increments_to_string(c.xmax - c.xmin)
            p = (x, y)
            paint_text(painter, label, p, flags, shift, fill=self.current_background)
        # ... do the A cuts
        flags = QtCore.Qt.AlignHCenter | QtCore.Qt.AlignBottom
        shift = (0, -8)
        for c in acuts:
            x = self.geom.boards[0].xL() + (c.xmin + c.xmax) // 2
            y = self.geom.boards[0].yB()
            label = units.increments_to_string(c.xmax - c.xmin)
            p = (x, y)
            paint_text(painter, label, p, flags, shift, fill=self.current_background)

    def keyPressEvent(self, event):
        '''
        Handles key press events
        '''
        dx = 4.0 / self.scaling
        scale_factor = 1.1
        if event.key() == QtCore.Qt.Key_Left:
            if self.scaling > 1.0:
                self.translate[0] -= dx
                self.update()
        elif event.key() == QtCore.Qt.Key_Right:
            if self.scaling > 1.0:
                self.translate[0] += dx
                self.update()
        elif event.key() == QtCore.Qt.Key_Up:
            if self.scaling > 1.0:
                self.translate[1] += dx
                self.update()
        elif event.key() == QtCore.Qt.Key_Down:
            if self.scaling > 1.0:
                self.translate[1] -= dx
                self.update()
        elif event.key() == QtCore.Qt.Key_Z:
            self.scaling *= scale_factor
            self.update()
        elif event.key() == QtCore.Qt.Key_U:
            self.scaling /= scale_factor
            self.update()
        elif event.key() == QtCore.Qt.Key_Escape:
            self.scaling = 1.0
            self.translate = [0.0, 0.0]
            self.update()
        else:
            event.ignore()

    def wheelEvent(self, event):
        '''
        Handles mount wheel events
        '''
        if self.config.debug:
            print('qt_fig.wheelEvent', event.delta())
        self.scaling *= 1 + 0.05 * event.delta() / 120
        if self.scaling < 1.0:
            self.scaling = 1.0
            self.translate = [0.0, 0.0]
        self.update()

    def mousePressEvent(self, event):
        if event.button() != QtCore.Qt.LeftButton:
            event.ignore()
            return
        self.mouse_pos = self.base_transform.map(event.pos())
        if self.config.debug:
            print('mouse pressed here: {} {}'.format(self.mouse_pos.x(),
                                                     self.mouse_pos.y()))

    def mouseReleaseEvent(self, event):
        self.mouse_pos = None

    def mouseMoveEvent(self, event):
        if self.mouse_pos is None:
            event.ignore()
            return
        pos = self.base_transform.map(event.posF())
        if self.config.debug:
            print('mouse moved here: {} {}'.format(pos.x(), pos.y()))
        self.translate[0] += (pos.x() - self.mouse_pos.x()) / self.scaling
        self.translate[1] += (pos.y() - self.mouse_pos.y()) / self.scaling
        self.mouse_pos = pos
        self.update()
