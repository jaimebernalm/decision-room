"""Full distinguishable labels in opt-in HTML/PDF, with generic synthetic series."""
from copy import deepcopy
from xml.etree import ElementTree
import unittest
from reportlab.graphics.shapes import String
from reportlab.graphics import renderSVG
from reportlab.pdfbase.pdfmetrics import stringWidth
from decision_room.report_pdf import line_drawing, WIDTH


def chart(owner=True):
    names = ['Nombre compartido suficientemente largo: ' + suffix for suffix in ['grupo primero', 'grupo segundo', 'grupo tercero']]
    points, coordinates = [], []
    for index, month in enumerate(['2026-01', '2026-02', '2026-03']):
        for j, name in enumerate(names):
            label=f'{month}|{j}'
            points.append(dict(label=label,value=str(index*10+j),formatted=str(index*10+j)))
            coordinates.append(dict(label=label,category=month,series=name))
    return dict(kind='line',title='Comparación de grupos',unit='unidades',owner_presentation=owner,
                points=points,panels=[dict(category_title='Mes',temporal_grain='month',series_order=names,coordinates=coordinates)])


class OwnerLegendTests(unittest.TestCase):
    def test_full_names_and_measured_bounds_do_not_overlap_or_change_data(self):
        data=chart(); before=deepcopy(data); drawing=line_drawing(data)
        names=data['panels'][0]['series_order']
        labels=[o for o in drawing.contents if isinstance(o,String) and o.text in names]
        self.assertEqual([o.text for o in labels],names)
        self.assertEqual(len({o.y for o in labels}),3)
        for o in labels:
            self.assertLessEqual(o.x+stringWidth(o.text,'Helvetica',o.fontSize),WIDTH-14)
            self.assertGreater(o.y,197) # all labels stay above the plotted values
        self.assertEqual(data,before)
        ElementTree.fromstring(renderSVG.drawToString(drawing))

    def test_long_label_wraps_without_losing_its_distinguishing_suffix(self):
        data=chart(); panel=data['panels'][0]
        old=panel['series_order'][0]; new='W'*110+' grupo único'
        panel['series_order'][0]=new
        for point in panel['coordinates']:
            if point['series']==old:point['series']=new
        drawing=line_drawing(data)
        labels=[o for o in drawing.contents if isinstance(o,String) and o.x==76]
        self.assertIn(new,''.join(o.text for o in labels))
        for label in labels:self.assertLessEqual(label.x+stringWidth(label.text,'Helvetica',9),WIDTH-14)

    def test_control_keeps_existing_geometry_and_labels(self):
        data=chart(False); drawing=line_drawing(data)
        self.assertEqual(drawing.height,250)
        labels=[o.text for o in drawing.contents if isinstance(o,String)]
        for name in data['panels'][0]['series_order']:
            self.assertIn(name[:28],labels)
            self.assertNotIn(name,labels)
