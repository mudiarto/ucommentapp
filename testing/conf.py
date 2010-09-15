# Minimal configuration
#sys.path.append(os.path.abspath('.'))

# -- General configuration -----------------------------------------------------

book_title = u'Testing document'

# Sphinx extensions
extensions = ['sphinx.ext.pngmath',]

# Custom extensions
import sys, os
sys.path.append(os.path.abspath(os.getcwd()))
extensions.append('ucomment-extension')
html_translator_class = 'ucomment-extension.ucomment_html_translator'

# The master toctree document.
master_doc = 'contents'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ['_build', '.hg']

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

rst_epilog = """
.. |z| replace:: :math:`\mathrm{z}`
"""

# -- Options for ucomments -----------------------------------------------------

# Don't remove this line
ucomment = {}
ucomment['django_application_path'] = __UNIT_TESTS_WILL_REPLACE_THIS__

# Override settings from the standard ``settings/conf.py`` file
ucomment['toc_doc'] = 'contents'
ucomment['section_div'] = ''

