import os
import sys

sys.path.insert(0, os.path.abspath('../../../'))
sys.path.insert(0, os.path.abspath('..'))

extensions = [
    'sphinx.ext.autodoc',  # To generate autodocs
    'sphinx.ext.mathjax',  # autodoc with maths
    'sphinx.ext.napoleon'  # For auto-doc configuration
]

napoleon_google_docstring = False  # Turn off googledoc strings
napoleon_numpy_docstring = True  # Turn on numpydoc strings
napoleon_use_ivar = True  # For maths symbology
html_theme = 'sphinx_rtd_theme'

project = u'DRF API Logger'
copyright = u'2020, Vishal Anand'
author = u'Vishal Anand'

googleanalytics_id = 'G-BVJJKEEBVZ'

pygments_style = 'sphinx'
