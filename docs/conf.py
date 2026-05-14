import os
import sys

sys.path.insert(0, os.path.abspath('..'))

project = 'DRF API Logger'
copyright = '2020, Vishal Anand'
author = 'Vishal Anand'
release = '1.3.0'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
]

napoleon_google_docstring = False
napoleon_numpy_docstring = True
napoleon_use_ivar = True

html_theme = 'sphinx_rtd_theme'

pygments_style = 'sphinx'

exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
