import os
import sys

sys.path.insert(0, os.path.abspath('..'))

project = 'DRF API Logger'
copyright = '2020, Vishal Anand'
author = 'Vishal Anand'
release = '1.2.3'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
]

napoleon_google_docstring = False
napoleon_numpy_docstring = True
napoleon_use_ivar = True

html_theme = 'sphinx_rtd_theme'

html_baseurl = os.environ.get("READTHEDOCS_CANONICAL_URL", "/")
html_extra_path = ["../llms.txt"]

pygments_style = 'sphinx'

exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
