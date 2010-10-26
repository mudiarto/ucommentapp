"""
Subclasses Sphinx's HTML translator.
Prepares the RST documentation for the ucomment directive.

:copyright: Copyright 2010, by Kevin Dunn
:license: BSD, see LICENSE file for details.
"""
# FUTURE improvements
#
# TODO(KGD): handle compact list_items later on.  Right now, all lists are
#            rendered as <li><p>.....</p></li>, causing rather large gaps
#            between list entries.  Fixable with CSS?
#
# TODO(KGD): table entries are still being created inside <p> tags, leaving
#            too much room around them.  Use CSS to remove the space?

import os
import re
import sys
import time
import random
import shutil
import subprocess
import collections
try:
    from hashlib import md5
except ImportError:
    from md5 import md5

from docutils import nodes
from docutils.utils import new_document
from docutils.frontend import OptionParser
from docutils.parsers.rst import directives, Directive, Parser

from sphinx.directives import TocTree
from sphinx.util.osutil import ensuredir
from sphinx.util.compat import Directive
from sphinx.locale import admonitionlabels
from sphinx.application import ExtensionError
from sphinx.writers.html import SmartyPantsHTMLTranslator

ADMONITION_LABELS = admonitionlabels
ADMONITION_LABELS.update({'admonition':''})
NOT_PARAGRAPHS = (nodes.entry)
REPLACE_SOURCE_SUFFIX = '.ucomment'  # Do not use your usual RST file suffix.
# To find the toctree directive
TOCTREE_RE = re.compile(r'^(\s*)\.\. toctree::(\s*)$')
# All nodes that are commentable are labelled with this class.  This string
# must agree with the ``CLASS_NAME`` variables used in the Javascript file.
# Unless you are sure of what are doing, you should probably not change this.
CLASS_NAME = 'ucomment'

# A tuple version of the ``CommentReference`` model used in Django; except we
# omit fields that will be the same for every reference (date, revID, ..)
# Note: we use this data structure whether or not we are using Django.
CommentReference = collections.namedtuple('CommentReference',
                                          'source node line root link_name')

#-------------------------------------------------------------------------------
# Utility function
#-------------------------------------------------------------------------------
def make_title(line):
    """ Makes a suitable filename from the section's title (slugify).

    Change punctuation (dots, dashes, question marks, braces, brackets,
    colons etc) into underscores; spaces into dashes.
    Uses docutils.nodes.make_id() function to do the work
    """
    return nodes.make_id(line)

def create_codes_ID(num):
    """Creates a new comment identifier; these appear in the source code for
    each page; they must be short and not possible to cause confusion.

    53 characters, N=4 combinations = 53^4 = many comment ID's (prevents collisions)
    """
    valid_letters = 'abcdefghjkmnpqrstuvwxyzABCEFGHJKLMNPQRSTUVWXY23456789'
    return ''.join([random.choice(valid_letters) for i in range(num)])

#-------------------------------------------------------------------------------
# Subclass the HTML translator to appropriately handle ``ucomment`` directives.
#-------------------------------------------------------------------------------
class ucomment_html_translator(SmartyPantsHTMLTranslator):
    """
    Subclasses the HTML translator, so that we can add a few custom methods
    to help with the commenting.
    """
    def __init__(self, *args, **kwds):
        SmartyPantsHTMLTranslator.__init__(self, *args, **kwds)
        parent = SmartyPantsHTMLTranslator
        self.visit_title_original = parent.visit_title
        self.visit_figure_original = parent.visit_figure
        self.visit_image_original = parent.visit_image
        self.visit_sidebar_original = parent.visit_sidebar
        self.visit_literal_block_original = parent.visit_literal_block
        self.visit_list_item_original = parent.visit_list_item
        self.visit_term_original = parent.visit_term
        self.visit_table_original = parent.visit_table
        self.depart_table_original = parent.depart_table
        self.in_admonition_title = False

        try:
            self.visit_displaymath_original = parent.visit_displaymath
        except AttributeError:
            from sphinx.ext.pngmath import html_visit_displaymath
            self.visit_displaymath_original = html_visit_displaymath

        # TODO(KGD): this code is being called for every document
        #            Find a signal that is emitted where this code can
        #            be called just once.
        self.ucomment = self.builder.app.env.config['ucomment']
        self.ucomment['skip_nodes_in'].add(u'<partial node>')
        self.ucomment['line_offset'] = {}
        self.ucomment['last_line'] = -1

        for srcname, fileoffsets in self.ucomment['split_files'].iteritems():
            if len(fileoffsets) > 1:
                new_files = dict((v, k) for k, v in fileoffsets.iteritems())
                self.ucomment['line_offset'].update(new_files)
            elif len(fileoffsets) == 1:
                self.ucomment['line_offset'][srcname] = fileoffsets.keys()[0]
            elif len(fileoffsets) == 0:
                self.ucomment['line_offset'][srcname] = 0


        # Is ``True`` when we are dealing with entries in a table
        self.within_table = False

    def discover_line_and_source(self, node, bias, bias_if_present):
        """
        Sometimes nodes do not have their line number (``node.line``), and
        other times they do not have a source (``node.source``).  This function
        tries to discover them, by looking around the rest of the document.
        If found, it will update those class attributes.

        The line number is not guaranteed to be found; this code will leave it
        as ``None`` if not found.

        ``bias`` is added if the ``node.line`` is None, while the
        ``bias_if_present`` is added if ``node.line`` is not None.

        KGD: Is absense of ``node.line`` and ``node.source`` a docutils glitch?
        """
        if node.line is None:

            # Let's try to find the line number ... look at our parent, then
            # let's find ``node`` in the parent, and look at our preceeding
            # sibling
            parent = node.parent
            while parent is not None:
                lower_bound = parent.line
                if parent.line is not None:
                    break
                else:
                    parent = parent.parent

            # Can we improve on the lower bound?  Check our immediate sibling.
            preceding_sibling = node.parent.index(node) - 1
            if preceding_sibling >= 0:
                if node.parent.children[preceding_sibling].line is not None:
                    lower_bound = node.parent.children[preceding_sibling].line

            lower_bound = max(self.ucomment['last_line'], lower_bound)

            # Last resort
            try:
                upper_bound = node.parent.children[preceding_sibling+2].line
            except IndexError:
                upper_bound = None

            node.line_lower = lower_bound
            node.line_upper = upper_bound

            if lower_bound is None:
                if upper_bound is not None:
                    node.line = upper_bound - bias
            else:
                node.line = lower_bound + bias
        else:
            node.line += bias_if_present

        # We must have a source file, so that we can calculate the offset later
        if node.source is None:
            if node.parent.source:
                node.source = node.parent.source

            # Parent doesn't contain source; sometimes the child node does:
            elif node.parent.source is None:
                if len(node.children) and node.children[0].source is not None:
                    node.source = node.children[0].source
                else:

                    # Last resort: try looking higher and higher up the document
                    parent = node.parent
                    while parent is not None:
                        node.source = parent.source
                        if parent.source is not None:
                            break
                        else:
                            parent = parent.parent

        # At this point we give up: this node won't be commentable

    def find_unusual_line_number(self, node, regex):
        """
        Do a bit more work in finding the line numbers for these nodes:
        open up the source file and search more carefully for the directive.

        The side effect of this function is that it will adjust ``node.line``.
        """
        with open(node.source, 'r') as filesrc:
            lines = filesrc.readlines()

        valid = re.compile(r'(\s*)\.\. (' + regex + r')::')
        for idx, line in enumerate(lines[node.line_lower-1:node.line_upper]):
            if valid.match(line):
                # Found the desired starting point for the node.
                node.line = idx + node.line_lower
                return True

        return False

    def discover_comment(self, node):
        """ Finds a comment close to the current node that refers to the content
        in ``node``. If a comment is found, this function will return that
        comment's root, else it will create a new comment_root to return.
        """
        # Special case: ``list_item`` nodes have their comment as children
        if node.tagname == 'list_item':
            for item in node.children:
                if item.tagname == 'ucomment':
                    return item.ucomment_root

        # All other nodes have their comments as the next sibling in the
        # parent node.
        try:
            comment = node.parent.children[node.parent.index(node)+1]
        except IndexError:
            comment = node

        if comment.tagname != CLASS_NAME:
            comment_root = create_codes_ID(self.ucomment['root_node_length'])
            while comment_root in self.ucomment['used_roots']:
                comment_root = create_codes_ID( \
                                            self.ucomment['root_node_length'])
            # Add it to the list of used roots
            self.ucomment['used_roots'].append(comment_root)
        else:
            comment_root = comment.ucomment_root
            comment.been_handled = True

        return comment_root

    def extend_node_attrs(self, node, bias=1, bias_if_present=0):
        """
        Adds `class` and `id` information to the node; these will be rendered
        in the HTML and used for the commenting functionality.

        We use the node's line number as the ID to comment against.
        If we don't have the line number and source then we are unable to
        add the information to create the comment.

        This function also collects the information required to generate all
        the comment references; once the HTML is successfully created.
        All nodes that are commentable must pass through this function
        """

        # We cannot comment entries within a table (no place to put ucomment
        # RST directive)
        if self.within_table or self.in_sidebar:
            return

        self.discover_line_and_source(node, bias, bias_if_present)
        if node.line is not None and node.source is not None:
            # Preliminary check, but it is not conclusive
            if node.source in self.ucomment['skip_nodes_in']:
                return

            src = node.source.partition(self.builder.app.srcdir + os.sep)[2]
            src = src.partition(self.builder.app.env.config.source_suffix)[0]
            if src not in self.ucomment['skip_nodes_in']:

                # Collect information about the comment reference.
                comment_root = self.discover_comment(node)
                self.ucomment['last_line'] = node.line
                line_number = node.line + self.ucomment['line_offset'][src]

                node.attributes['ids'] = [comment_root]
                node.attributes['classes'].extend([CLASS_NAME])

                # Append the info to later create the comment references in the
                # database.
                node_type = node.tagname
                if node.parent.tagname == 'list_item':
                    node_type = 'list_item'

                self.ucomment['comment_refs'].append(CommentReference(
                                self.ucomment['split_sources'][node.source],
                                node_type,
                                line_number,
                                comment_root,
                                node.source))

    def visit_image(self, node):
        """
        Adds class and id information so that figures and images can also be
        commented on.  (Note: figures are just an image node with some extra
        bits for captions, so figures will end up coming through this code.)
        """
        # NOTE: Figures should be commentable: cannot be done directly
        #       using the docutils line number for figure or image nodes
        #       at the moment (ver 0.7).  We will access it reading the source
        #       file ourselves and finding the image or figure directive.
        self.discover_line_and_source(node, bias=0, bias_if_present=0)
        self.find_unusual_line_number(node, regex = r'(image)|(figure)')
        self.extend_node_attrs(node, bias=0)
        self.visit_image_original(self, node)

    def visit_sidebar(self, node):
        """
        When visiting sidebars: we cannot comment on anything within a sidebar,
        because of the unusual way it is layed out.  But we will try to get
        the line number (maybe we can find a way to comment on them in future?)
        """
        self.discover_line_and_source(node, bias=0, bias_if_present=0)
        self.find_unusual_line_number(node, regex = r'sidebar')
        self.visit_sidebar_original(self, node)


    def visit_literal_block(self, node):
        """
        Adds class and and id information to source code-like <pre> blocks.
        """
        if 'line_number' in node.attributes:
            node.line = node.attributes['line_number']

        # NOTE: you should not use the ``find_unusual_line_number()`` function
        #       on this sort of node.  It could be misleading if there are
        #       source code lines that match the regular expressions searched
        #       for in that function.
        self.extend_node_attrs(node)
        self.visit_literal_block_original(self, node)

    def visit_title(self, node):
        """
        Titles are also commentable
        """
        # The titles of various admonitions are not commentable as titles.
        # These titles will represented as paragraphs, so there is code
        # in the ``visit_paragraph()`` method to prevent them from commenting.
        if node.parent.tagname in ADMONITION_LABELS:
            self.in_admonition_title = True
        else:
            self.extend_node_attrs(node, bias=0)
        self.visit_title_original(self, node)

    def depart_title(self, node):
        """Turn off the ``in_admonition_title`` flag; call the parent to do
        the work."""
        self.in_admonition_title = False
        SmartyPantsHTMLTranslator.depart_title(self, node)

    def visit_paragraph(self, node):
        """
        Adds class and id information to most text elements in the HTML.
        """
        # See comment in ``visit_title()`` that explains this.
        conditions = [node.parent.tagname in ADMONITION_LABELS,
                      node.parent.index(node) == 1,
                      len(node.parent.children) > 2]
        if all(conditions):
            pass
        else:
            self.extend_node_attrs(node)
        self.body.append(self.starttag(node, 'p', suffix=''))

    def depart_paragraph(self, node):
        """ Not everything node that enters this method is a paragraph that
        requires an ending </p> tag.
        """
        if not isinstance(node.parent, NOT_PARAGRAPHS):
            self.body.append('</p>\n')
        else:
            pass

    def visit_list_item(self, node):
        """
        Adds class and id information so that list items can also be commented
        on.  However, if the list item is only going to be a paragraph, then
        we don't add this info, because we will do it for the child paragraph
        later on.
        """
        if node.children[0].tagname not in ['paragraph', 'compact_paragraph']:
            self.extend_node_attrs(node, bias=0)

        self.visit_list_item_original(self, node)


    def visit_term(self, node):
        """
        <dl>
            <dt> Definition term</dt>
            <dd> Definition content is commentable, as usual.</dd>
        </dl>
        """
        self.visit_term_original(self, node)


    def visit_table(self, node):
        """
        Adds class and id information so that tables can be commented.
        """
        self.discover_line_and_source(node, bias=0, bias_if_present=0)

        # http://docutils.sourceforge.net/docs/ref/rst/directives.html#tables
        # ``tabularcolumns`` is a Sphinx directive: /sphinx/directives/other.py
        table_regex = r'(table)|(csv-table)|(list-table)'

        # Note: the logical test has a side effect: it sets ``node.line``
        if not self.find_unusual_line_number(node, regex = table_regex):
            # Search again: Maybe it is a simple table or a grid table.
            with open(node.source, 'r') as filesrc:
                sc = filesrc.readlines()

            # Search for: ===== or +----- :
            # http://docutils.sourceforge.net/docs/ref/rst/restructuredtext.html
            # See the "Grid tables" and "Simple tables" section
            table_row = re.compile(r'(={2,})|(\+-{2,})')
            for idx, line in enumerate(sc[node.line_lower-1:node.line_upper]):
                if table_row.match(line):
                    # Found the desired starting point for the node.
                    node.line = idx + node.line_lower
                    break

        self.extend_node_attrs(node, bias=0)
        self.within_table = True
        self.visit_table_original(self, node)

    def depart_table(self, node):
        """
        Unset the flag so that future nodes can be commented.
        """
        self.within_table = False
        self.depart_table_original(self, node)

    def visit_displaymath(self, node):
        """
        Calls ``html_visit_displaymath(...)`` in ``pngmath.py`` to do the
        work, after appending the ucomment attributes to the node.
        """
        # The bias_if_present can be set to 0, if the Sphinx patch is
        # accepted.
        self.extend_node_attrs(node, bias_if_present=0)
        self.visit_displaymath_original(self, node)

    def unknown_visit(self, node):
        """ Nothing to do here. """
        pass
    def unimplemented_visit(self, node):
        """ Nothing to do here. """
        pass



#-------------------------------------------------------------------------------
# Subclass the HTML translator to appropriately handle ``ucomment`` directives.
#-------------------------------------------------------------------------------
class ucomment(nodes.General, nodes.Element):
    """
    Inherit from the General node, because a comment doesn't do anything
    special.

    ``ucomment`` nodes have two attributes:
    * ucomment.ucomment_root: a string, indicating the comment root (used in DB)
    * ucomment.been_handled:  a boolean indicator: has comment be used in HTML
    """
    def shortrepr(self):
        """ Overwrite the shortrepr method to provide a more useful
        debugging representation. """
        return '<%s:%s>' % (self.tagname, self.ucomment_root)

def visit_ucomment_node(self, node):
    """
    General function for visiting a comment node.  Add nothing to the document's
    body.
    """
    if not node.been_handled and setup.app.builder.name == 'html':
        print '\n ERROR: Node "%s" was not handled yet' % node.ucomment_root

def depart_ucomment_node(self, node):
    """
    General function when departing a comment node.  Do nothing.
    """
    pass

class ucomment_directive(Directive):
    """
    The ``ucomment`` directive: subclasses Sphinx's Directive class.

    See http://docutils.sourceforge.net/docs/howto/rst-directives.html

    Sphinx also requires that the class be in the 0.5 docutils style, with
    attributes of

        * has_content
        * required_arguments
        * optional_arguments
        * final_argument_whitespace
        * option_spec
    """

    # has_content:  True if content is allowed below the directive
    has_content = True

    # The directive must contain the comment root, followed by the comment
    # nodes.  No additional arguments are allowed
    required_arguments = 0
    optional_arguments = 0
    final_argument_whitespace = False

    # Options (specified as :my_option:) are not handled
    option_spec = {}

    def run(self):
        """
        Simply return a list, with a single instance of our ucomment class.

        The ucomment node will only return the comment root, since that is what
        will be placed in the HTML.  The comments themselves are not of
        interest.
        """
        # self.lineno
        # self.content
        # self.block_text
        # self.arguments '
        # self.content
        # self.has_content
        # self.name
        # self.options
        # self.state
        # env = self.state.document.settings.env
        node = ucomment()
        comment_options = self.content.data[0]
        if not comment_options.index(':'):
            raise ExtensionError(('A malformed "ucomment" directive was found '
                                   'in %s at line number %i: %s.' %
                                   (self.src, self.lineno, comment_options)))
        node.ucomment_root = comment_options.split(':')[0]
        node.been_handled = False
        node.line = self.lineno

        return [node]

def get_documents_in_toctree(toctree_lines, found_docs, docname):
    """
    Receives a list of strings, ``toctree_lines`` that contains the toctree
    directive and the lines included within the toctree.  The lines must contain
    \n newline endings.

    Also supply ``found_docs``, the set of all documents found by Sphinx and
    ``docname``, the entry in ``found_docs`` which we are currently processing.

    Returns the list of files, in the order of the toctree, that are used
    within the toctree.

    This code seems a bit of a hack, because it simulates a RST document with
    the Sphinx ``.. toctree::`` directive.  But it is better this way, because
    if Sphinx changes its toctree syntax, then we will still get the correct
    list of files.
    """
    directives.register_directive('toctree', TocTree)
    parser = Parser()
    source = ''.join(toctree_lines)

    # Simulate the Sphinx environment entries required
    config = collections.namedtuple('config', 'source_suffix')
    config.source_suffix = 'rst'
    fake_sphinx_env = collections.namedtuple('env', 'config found_docs docname')
    fake_sphinx_env.config = config
    fake_sphinx_env.found_docs = found_docs
    fake_sphinx_env.docname = docname

    # Create a settings variable for docutils.
    settings = OptionParser(defaults={
                    'tab_width': 8,
                    'pep_references': '',
                    'rfc_references': '',
                    'env': fake_sphinx_env}).get_default_values()

    document = new_document('<toctree directive>', settings)
    parser.parse(source, document)
    return document.children[0].children[0].attributes['includefiles']


def write_src_file(filename, content, app, srcfile=''):
    """
    Smartly writes the ``content`` (a list of strings) to the ``filename``.
    ``filename`` should be the (optional) directory and file name to be written,
    without the extension. For example: ``contents`` or ``about/software``.

    The "smarts" come from the fact that if the ``content`` is exactly the same
    as is currently in the ``filename``, then the file is not written at all,
    helping speed up compilation of the Sphinx document.

    If ``content`` is just a string path to an existing file, then a copy of
    ``content`` is made.

    The ``app`` input is the Sphinx application object.  And ``srcfile`` is the
    full name of the RST source file which this sub section was split from.
    """
    out_file = os.path.join(app.env.srcdir, filename + REPLACE_SOURCE_SUFFIX)
    hashdict = app.env.config.ucomment['split_file_hash']
    if isinstance(content, basestring):
        content_file = os.path.join(app.env.srcdir, content)
        if os.path.isfile(content_file):
            with open(content_file, 'r') as file_handle:
                lines = file_handle.readlines()
            hashdict[filename] = md5(''.join(lines)).hexdigest()
            shutil.copy2(content_file, out_file)
        else:
            raise ExtensionError(('The ``content`` file must be an existing '
                                  'file.'))
        app.env.config.ucomment['split_sources'][out_file] = content_file
        return

    file_hash = md5(''.join(content)).hexdigest()
    app.env.config.ucomment['split_sources'][out_file] = srcfile
    # If there is an existing file, get its hash also.
    if os.path.isfile(out_file):
        with open(out_file, 'r') as file_handle:
            lines = file_handle.readlines()
        hashdict[filename] = md5(''.join(lines)).hexdigest()

    # Now test if we really need to write the ``content`` to ``filename``:
    if (filename not in hashdict) or hashdict[filename] != file_hash or \
                                                  not os.path.isfile(out_file):
        hashdict[filename] = file_hash
        with open(out_file, 'w') as file_handle:
            file_handle.writelines(content)

def split_non_toc_file(name, remove, app, conf):
    """
    For the given file ``name``, and the Sphinx settings in `app`` and the
    ucomment settings in ``conf``:

    * If the ``name`` file contains only zero or one major subsections,
      just return the file name.  Make a copy of the file to disk,
      with the same

    * If there are two or more major sections, split those sections into
      new files with an appropriate name, and return the list of split
      files to be added to the toctree.
    """
    # Cross references are ".. _label:"  - these must be maintained in the
    # same RST file to which the reference refers
    crossref_re = re.compile(r'^\s*\.\. _(.*?):\n')

    # Manipulate the file name into the various forms we require here:
    fullname = os.path.join(app.env.srcdir, name+app.env.config.source_suffix)

    to_process = conf['split_files'][name]
    # Clean up cross-referencing, then split the file
    if len(to_process) <= 1:
        if remove != '':
            short = ''.join(list(name.partition(remove)[2:]))
        else:
            short = name

        write_src_file(filename=short,
                       content = name + app.env.config.source_suffix, app=app)
        return [short]

    with open(fullname, 'r') as source_file:
        lines = source_file.readlines()

    file_list = []
    for section, entry in enumerate(sorted(to_process.keys())):
        # Work backwards, looking for cross referencing above header
        # Stop once you have encountered a non-blank line
        found = -1
        for idx in xrange(entry-1, -1, -1):
            if crossref_re.search(lines[idx]):
                found = idx
                break

            elif lines[idx].lstrip() != '':
                break

        if found > -1:
            # Remove the previous line, replace with new starting line
            del to_process[entry]
            to_process[found] = ''
        else:
            found = entry

        # The choice of ``sub_file`` name is important: it creates the
        # URL from which the page is accessed.
        sub_title = make_title(lines[entry])
        sub_file = remove + sub_title #+ app.env.config.source_suffix
        while os.path.isfile(os.path.join(app.env.srcdir, sub_file)):
            sub_file = ''.join([remove, make_title(lines[entry]),
                                '_', str(int(time.time()))])
        to_process[found] = sub_file

        # Ignore the header for now, put everything into 1st split
        if section == 0 and 0 not in to_process.keys():
            to_process[0] = to_process[entry]
            del to_process[entry]

        # Append this name to the list that we will output
        file_list.append(sub_title)

    # Finally, write the different sections to file
    startlines = sorted(to_process.keys())
    for section, entry in enumerate(startlines):
        try:
            part = lines[entry:startlines[section+1]]
        except IndexError:
            part = lines[entry:]

        # Also keep a record of the original file from which the subsection came
        write_src_file(to_process[entry].partition(
                                              app.env.config.source_suffix)[0],
                       content=part, app=app, srcfile = fullname)

    return file_list


def split_rst_files(app, conf, remaining_files):
    """
    We will split the RST files up into smaller pieces, just before they are
    read in and their corresponding doctree files are created.

    The file is split into sections, according to ``section_div``, where
    3 or more of these characters must appear, at the start of line, and
    nothing else may appear in the line, in order to qualify for a section.

    Furthermore, we look for cross-referencing that might appear just above the
    section, and ensure that it is maintained in the correct RST file.

    NOT DONE YET: (for now, rather put substitutions in the index.rst file):
    Lastly, any material, other than a cross-reference, that appears above the
    first section is kept and pasted at the top of every split.  This allows the
    author to put substitutions at the top of the RST, and they will be used
    for the entire file.

    Example, assuming that master_doc = 'contents' in your ``conf.py`` file
    =======

    Consider these 5 files:

      contents.rst
      def.rst
      abc/
         /idx.rst
         /pqr.rst
         /tuv.rst

    +-------------------+-----------------------+------------+--------+--------+
    |contents.rst       |def.rst                |abc/idx.rst |pqr.rst |tuv.rst |
    |-------------------|-----------------------|------------|--------|--------+
    |                   |                       |            |        |        |
    |.. toctree::       |Major Section          |.. toctree::|Stuff.  | More   |
    |                   |=============          |            |        | text   |
    |    abc/idx        |                       |    pqr     |        |        |
    |    def            |Text, figures, etc,    |    tuv     |        |        |
    |                   |in this long section.  |            |        |        |
    |                   |                       |            |        |        |
    |                   |.. _cross-reference-B: |            |        |        |
    |                   |                       |            |        |        |
    |                   |Section B              |            |        |        |
    |                   |=========              |            |        |        |
    |                   |                       |            |        |        |
    |                   |More text, figures,    |            |        |        |
    |                   |in this long section.  |            |        |        |
    +-------------------+-----------------------+------------+--------+--------+

    If you set ``section_div = '='`` in your conf/settings.py file, then the
    ``def.rst`` file will be split into two pieces, and the files will appear
    as shown below, after this function is finished.

      contents.rst       (will be left untouched, but added to unused_docs list)
      contents.ucomment
      def.rst            (will be left untouched, but added to unused_docs list)
      def.ucomment       (just a copy of def.rst)
      major-section..ucomment
      section-b..ucomment
      abc/
         /idx.rst        (will be left untouched, but added to unused_docs list)
         /pqr.rst        (will be left untouched, but added to unused_docs list)
         /tuv.rst        (will be left untouched, but added to unused_docs list)
         /idx.ucomment   (just a copy of idx.rst)
         /pqr.ucomment   (just a copy of idx.rst)
         /tuv.ucomment   (just a copy of idx.rst)

    +-------------------+-----------------------+----------------------+
    |contents.ucomment  |major-section.ucomment |section-b.ucomment    |
    |-------------------|-----------------------|----------------------+
    |                   |                       |                      |
    |.. toctree::       |Section A              |.. _cross-reference-B:|
    |                   |=========              |                      |
    |    abc/idx        |                       |Section B             |
    |    major-section  |Text, figures, etc,    |=========             |
    |    section-b      |in this long section.  |                      |
    |                   |                       |More text, figures,   |
    |                   |.. _cross-reference:   |in this long section. |
    |                   |                       |                      |
    +-------------------+-----------------------+----------------------+

    The default suffix will be changed to ``.ucomment``.  This ensures that we
    never touch the original files, yet we get the same document structure,
    but with large files split up.    """



    space = re.compile('^(\s*)')

    # Now ``toc_docs`` files all contain and include other files, while
    # ``remaining_files`` is the complement of that set.

    # For every file that contains one or more toctree directives, scan the
    # directive and for every file inside the directive
    #
    #  * if that file contains a toctree also, just leave that line in place
    #  * if that file needs splitting up, then expand that line into two or
    #    more lines that contain the major sections.
    #
    # At the end, write the file out to ``name.ucomment``.

    for name in list(conf['toc_docs']):
        fullname = os.path.join(app.env.srcdir,
                                name + app.env.config.source_suffix)

        with open(fullname, 'r') as source_file:
            lines = source_file.readlines()

        # Which files are included by the toctree?   Replace every entry in the
        # toctree with

        for idx, line in enumerate(lines):
            if TOCTREE_RE.match(line):
                toctree_lines = [line]
                pre = TOCTREE_RE.match(line).group(1).expandtabs()
                for sub_idx, sub in enumerate(lines[idx+1:]):
                    if len(space.match(sub).group(1).expandtabs())<=len(pre):
                        break
                    else:
                        toctree_lines.append(sub)
                        lines[idx + sub_idx + 1] = ''

                toctree_files = get_documents_in_toctree(toctree_lines,
                                                found_docs = app.env.found_docs,
                                                docname = name)
                lines[idx] = (toctree_files, toctree_lines)

        # We have a toctree for every tuple that appears in lines.  Usually
        # there will be only one, but there's no reason why there can't be more.
        #
        # Replace the entries in the toctree with the found documents depending
        # on 3 scenarios:
        #
        # 1. The found document contains another toctree: just write that
        #    found document as-is in the toctree.  (Corresponds to the case
        #    of ``abc/idx.rst`` in the above example)
        # 2. The found documents contains only one or less major subsections.
        #    Just copy those lines over to a .ucomment file, the text is left
        #    the same.  See ``abc/pqr.rst`` and ``abc/tuv.rst`` in the example.
        # 3. The found document contains two or more major sections.  Split
        #    those sections up and add them in the appropriate order in the
        #    existing toctree.

        outlines = []
        for entry in lines:
            if not isinstance(entry, tuple):
                outlines.append(entry)
                continue

            stop_adding = False
            for tocline in entry[1]:
                if tocline.lstrip().startswith(':'):
                    outlines.append(pre + '\t' + tocline.lstrip() + '\n')
                if tocline.strip() == '':
                    outlines.append(pre + '\n')
                    stop_adding = True
                if tocline.strip().find('toctree') > 0:
                    outlines.append(pre + '.. toctree::\n')
                if tocline.strip() != '' and stop_adding:
                    # No more lines worth processing in this toctree
                    break

                # Now append all the found files contained in ``entry[0]``
                if not stop_adding:
                    continue

                #base = posixpath.normpath(posixpath.join('/' + name, '..'))[1:]
                for src_file in entry[0]:
                    remove = os.path.commonprefix([name, src_file])
                    if remove != '':
                        short = ''.join(list(src_file.partition(remove)[2:]))
                    else:
                        short = src_file

                    # Case 1
                    if src_file in conf['toc_docs']:
                        outlines.append(pre + '\t' + short + '\n')

                    # Case 2 and 3: ``split_non_toc_file`` will split the file
                    #               and return a list of new file names
                    else:
                        sub_file_list = split_non_toc_file(src_file, remove,
                                                           app, conf)
                        for sub_file in sub_file_list:
                            outlines.append(pre + '\t' + sub_file + '\n')
                        remaining_files.remove(src_file)

            outlines.append('\n\n')

        write_src_file(name, outlines, app, srcfile=fullname)

        # Lastly, any file with a toctree directive in it cannot be commented on
        # Especially if the toctree entry expands into multiple lines.  Maybe
        # we can fix this later. But for now its not that big of a deal.
        conf['skip_nodes_in'].add(name)

    # Check if there are any files left in ``remaining_files``.
    # These are files that Sphinx would have warned about.
    if len(remaining_files) > 0:
        app.warn(('There were files in the document directory that were '
                  'not included in any toctree directive: %s') % \
                    str(remaining_files), location='ucomment-extension')


def copy_static_content(app, exception):
    """
    Move all static content to the webserver.
    """
    conf = app.env.config.ucomment
    if exception is not None:
        return

    src = os.path.join(app.builder.outdir, '_images')
    ensuredir(src)
    ensuredir(conf['MEDIA_ROOT']) # destination

    copy_command = ['cp', '-ru', src+os.sep+'.', conf['MEDIA_ROOT']]
    try:
        subprocess.check_call(copy_command, stdout=subprocess.PIPE, cwd='.')
    except subprocess.CalledProcessError as e:
        app.builder.warn('Unable to copy over the image data to the '
                        'static web-directory: return code = %s' % \
                        str(e.returncode))
        return

    # TODO(KGD): consider converting images from PNG to JPG; rewrite URL's also
    # There is a builder variable that contains all images (that variable is
    # used to copy the images to _images/ dir.

def ucomment_builder_init_function(app):
    """
    Prepares the compile area:
    * adds the ucomment options to the ``app.env.config`` variable
    * (optionally) splits large RST source files into smaller sections.
    """

    # This conf dict is the one that is loaded from the last saved session
    conf = app.env.config.ucomment
    # This conf dict is the one specified in the user's ``conf.py`` file; we
    # will give settings in this dictionary preference.
    user_conf = app.config.ucomment


    # Get the settings from the Django application
    # --------------------------------------------
    if 'django_application_path' in user_conf:

        os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

        parent_name, app_name = os.path.split(\
                           user_conf['django_application_path'].rstrip(os.sep))
        sys.path.extend([parent_name])

        ## Import the ``settings/conf.py`` settings file (Django-like settings)
        #temp = __import__(app_name + '.conf.settings', None, None,
                                   #['conf.settings'])
        #for key, value in temp.__dict__.iteritems():
            ## First, load all settings from ``settings/conf.py`` file
            #if key[0:2] != '__':
                #conf[key] = value

            ## Setting is in user's conf.py file take preference:
            #if key in user_conf:
                #conf[key] = user_conf[key]
    else:
        raise ExtensionError(('The ucomment extension requires that you specify'
                               " the ``ucomment['django_application_path']`` "
                               'setting in your Sphinx ``conf.py`` file.'))

    # Create some additional settings
    # -------------------------------
    # Given the name of the split chapter file as the key, allows us to lookup
    # the source RST file in the value.
    conf['split_sources'] = {}

    # keys=name of original RST source, values are another dict, where the keys
    # are the line offsets and the values are the split chapter RST file names.
    conf['split_files'] = {}

    # Stores info used to create the comment references in the Django DB
    # after we have compiled the HTML to pickle files.
    conf['comment_refs'] = []

    # List of comment roots that have been used already
    conf['used_roots'] = []

    # Internal setting used by Django, but must be set, in case Sphinx is called
    # in stand-alone mode.
    if 'skip-cleanup' not in conf:
        conf['skip-cleanup'] = False

    # Internal setting used by this extension: saves the hashes to disk, to
    # avoid creating the split files everytime.
    if 'split_file_hash' not in conf:
        conf['split_file_hash'] = {}

    # Reset this back to empty every time:
    conf['toc_docs'] = set()

    # Ensure these settings exist, otherwise put default values
    # ----------------------------------------------------------
    # This allows us to compile the RST document from the command line using
    # ``sphinx-build -b html . _build``, or something similar: used in debugging
    if 'skip_nodes_in' not in conf:
        conf['skip_nodes_in'] = ['']
    if 'section_div' not in conf:
        conf['section_div'] = ''
    if 'min_length_div' not in conf:
        conf['min_length_div'] = 3
    if 'root_node_length' not in conf:
        conf['root_node_length'] = 6
    if 'MEDIA_ROOT' not in conf:
        conf['MEDIA_ROOT'] = os.path.join(app.builder.outdir, '_images')

    conf['skip_nodes_in'] = set(conf['skip_nodes_in'])

    # Regular expression for ucomment lines: adds them to the list of used nodes
    ucomment_lines = re.compile(r'^\s*\.\. ucomment::\s*(.*?):')
    # Regular expression that picks up the main section dividers
    try:
        div_re = re.compile(r'^' + conf['section_div'] + \
                            '{' + str(conf['min_length_div']) + r',}$')
    except re.error:
        # From: http://stackoverflow.com/questions/1845078
        div_re = re.compile(r'(?!x)x')

    # Reload the list of files.  You must use ``app.config`` (do not use
    # ``app.env.config`` - that was loaded from the pickle file).
    app.env.find_files(app.config)
    remaining_files = app.env.found_docs.copy()
    toc_docs = set()

    # Preliminary scan of the documents to find those that contain .. toctree::
    # directives, or the file that is the main TOC.  Also, initializes the
    # 'split_sources' and 'split_files' settings to useful values
    for name in list(app.env.found_docs):

        # Use app.config.source_suffix: i.e. use the original suffix for
        # the document's files.
        fullname = os.path.join(app.env.srcdir,
                                           name + app.config.source_suffix)

        conf['split_sources'][fullname] = fullname

        with open(fullname, 'r') as source_file:
            lines = source_file.readlines()

        # This dict has keys="line offset in the RST file for each section",
        # while the corresponding value="file name to which that subsection
        # will be written".
        to_process = {}
        has_toctree = False
        for idx, line in enumerate(lines):
            if div_re.search(line.rstrip()):
                to_process[idx-1] = ''
            if TOCTREE_RE.match(line):
                has_toctree = True

        if has_toctree:
            toc_docs.add(name)
            remaining_files.remove(name)

        conf['split_files'][name] = to_process

    # Store the files which contain toctree directive. These files are not
    # commentable.
    conf['toc_docs'] = toc_docs


    if conf['section_div']:
        VALID_TITLES = ['!', '"', '#', '$', '%', "'", '(', ')', '*', '+',
                        ',', '-', '.', '/', ':', ';', '<', '=', '>', '?',
                        '@', '[', '\\', ']', '^', '_', '`', r'{', '|',
                        '}', '~']

        if isinstance(conf['section_div'], basestring) and \
                                       len(conf['section_div']) == 1 and \
                                      conf['section_div'] in VALID_TITLES:
            # Ensure a valid regular expression is created
            if conf['section_div'] in ['^', '*', '+', '$', '(', ')', '-',
                                       '.', '?', '[', ']', '\\', '{', '}',
                                       '|']:
                conf['section_div'] = '\\' + conf['section_div']

            # Set the source suffix to the one requested by the user.
            app.env.config.source_suffix = app.config.source_suffix

            # Reset any previous record of the file splitting:
            conf['split_sources'] = {}

            # Also reset the list of file hashes.  We also use this to determine
            # if any old .ucomment files should be deleted.
            conf['split_file_hash'] = {}

            # Do the work.
            split_rst_files(app, conf, remaining_files)

            # Change the source suffix to the new extension: note: it must be
            # ``app.config``, not ``app.env.config``.
            conf['original_source_suffix'] = app.config.source_suffix
            app.env.config.source_suffix = REPLACE_SOURCE_SUFFIX
            app.config.source_suffix = REPLACE_SOURCE_SUFFIX

            # Trick Sphinx into believing the config file has not changed.
            # Note that if files did change due to changes in the settings,
            # Sphinx will pick up their new file times and recompile them.
            app.config.ucomment = app.env.config.ucomment

            # Are there any old files with ``REPLACE_SOURCE_SUFFIX`` lying
            # around?  If so, delete them. Update the list of files to process:
            # Sphinx will now find the new extensions and redo its file list.
            app.env.find_files(app.env.config)
            to_del = app.env.found_docs - set(conf['split_file_hash'].keys())
            for entry in to_del:
                fullname = os.path.join(app.env.srcdir,
                                entry + app.env.config.source_suffix)
                if os.path.exists(fullname):
                    os.remove(fullname)

            # Clean the list up again.
            app.env.find_files(app.env.config)

            # TODO(KGD): there will be failure later if the document's
            # structure has changed and we use the saved environment.  In these
            # cases we must rebuild the entire doc structure to be safe.  See
            # code in views.py, in the ``commit_updated_document_to_database``
            # function on how to determine the document's structure.

            # In the clean-up section, check for the document structure. If
            # it has changed, then rebuild with a freshenv.
    else:
        # Ensure that the suffix setting is what the user has specified in the
        # conf.py file, and not a setting that was loaded from the pickle file.
        app.env.config.source_suffix = app.config.source_suffix
        app.env.find_files(app.env.config)


        # Like in the ``if conf['section_div']`` section above, trick Sphinx
        # into believing the loaded config file is the same as the given config.
        # Note that if files did change due to changes in the settings,
        # Sphinx will pick up their new file times and recompile them.
        app.config.ucomment = app.env.config.ucomment

    # Scan for any ucomment directives in the source files
    all_files = app.env.found_docs
    for fname in list(all_files):
        name = os.path.join(app.env.srcdir, fname+app.env.config.source_suffix)

        with open(name, 'r') as f_handle:
            lines = f_handle.readlines()

        for line in lines:
            has_ucomment =  ucomment_lines.match(line)
            if has_ucomment:
                conf['used_roots'].append(has_ucomment.groups()[0])

def ucomment_build_finished_function(app, exception):
    """ Clean up after finished building. Must be done in order. """
    conf = app.env.config.ucomment
    if conf['skip-cleanup']:
        return

    try:
        copy_static_content(app, exception)
    except Exception as e:
        print('An exception (%s) occurred while using the ucomment '
              'extension' % e.__class__.__name__)
        raise(e)

    # Remove any .ucomment files  that should have been deleted.
    set(app.env.all_docs) - app.env.found_docs
    app.env.find_files(app.config)

def setup(app):
    """ Setup the extension"""

    # Allows for access to some data structures we need through compiling
    setup.app = app

    app.add_config_value('ucomment', {}, 'env')
    app.add_directive('ucomment', ucomment_directive)

    # How to modify the HTML when a ``ucomment`` node is encountered
    app.add_node(ucomment,
                 html=(visit_ucomment_node, depart_ucomment_node),
                 latex=(visit_ucomment_node, depart_ucomment_node),
                 text=(visit_ucomment_node, depart_ucomment_node),
                 man=(visit_ucomment_node, depart_ucomment_node),
                 )

    # After the builder has been initialized, but before the RST files are read
    # in, we split the RST files apart according to their main sections.
    # Once the builder is finished, before Sphinx terminates, we undo the split.
    app.connect('builder-inited', ucomment_builder_init_function)
    app.connect('build-finished', ucomment_build_finished_function)



