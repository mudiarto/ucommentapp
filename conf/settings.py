from django.conf import settings as DJANGO_SETTINGS
from os import getcwd, sep
from tempfile import mkdtemp
MEDIA_URL = DJANGO_SETTINGS.MEDIA_URL
MEDIA_ROOT = DJANGO_SETTINGS.MEDIA_ROOT
EMAIL_FROM = DJANGO_SETTINGS.EMAIL_FROM
ADMINS = DJANGO_SETTINGS.ADMINS
del DJANGO_SETTINGS  # Leads to recursion depth errors when unpickling by Sphinx

# <NOTE: Please do not import any modules here directly, only functions from
#        a module.  This file is pickled, and modules cannot be cPickled.>

# Application settings (do not edit these 3 settings)
# --------------------
application_path = __file__[0:__file__.find('conf' + sep + 'settings.py')]
app_dirname = application_path.split(sep)[-2]
ucomment_ver = getattr(__import__(app_dirname, None, None), '__version__')

# Comment settings
# ----------------

# Enable commenting?  Set to `False` and restart the Django server to instantly
# turn off commenting.  Existing comments will also not be displayed.
enable_comments = True
# Number of characters for the comment root (added to RST text file sources)
root_node_length = 6
# Number of characters identifying a comment on a page (unique within each root)
short_node_length = 2
# Minimum and maximum number of characters required for a user comment
comment_min_length = 10
comment_max_length = 5000
# Number of comments before the user's future comments are auto-approved
number_before_auto_approval = 3
# Approval code generation: number of characters for matching approval code
approval_code_length = 42

# Repository settings
# -------------------

# Which type of Distributed Version Control System (DVCS) are you using?
# Must be one of ['hg'].
#
# As you can see, we currently only support mercurial repositories.
# Future plans will extend this list to include 'svn' & 'git'.
# DEVELOPERS: The repository manipulation code is in a wrapper file, so that
# you can replace it with your preferred DVCS's code. Please use "hgwrapper.py"
# as a template to start from.
repo_DVCS_type = 'hg'

# The full path and file name to the executable command that runs the DVCS.
repo_DVCS_exec = '/usr/local/bin/hg'

# The source code for your document.  This must be a valid repository containing
# all the RST source files.  Also, when the repository is cloned from the
# remote repo (see the setting below) the Sphinx conf.py file, and
# ``master_doc`` file specified in that conf.py file should be in remote repo.
#
# Please used the fully qualified path, e.g. http://bitbucket.org/kevindunn/doc
# Type "hg help urls" to get help on Mercurial URLs.  Also, set your
# authentication information in the .hg/hgrc file to allow automatic pushing
# back to this remote repo.
remote_repo_URL = r'http://hg.connectmv.com/ucommentapp-documentation/'

# This is the local repository of the document. It is a clone of the full
# document's source, with all revisions.  It is also the location where the RST
# is converted to HTML, and where comments are added to the RST sources.
# Changes made to this repo are pushed back to the remote repo.
local_repo_physical_dir = application_path + 'document_compile_area/'

# Same as the above, but use the URL notation required for the version control
# system (in this case, Mercurial)
local_repo_URL = r'file://' + application_path + '/document_compile_area/'

# HTML settings
# -------------
# Web link to the stylesheet:
stylesheet_link = MEDIA_URL + 'ucomment.css' + '?' + ucomment_ver

# Web link to the Javascript file:
js_file = MEDIA_URL + 'ucomment.js' + '?' + ucomment_ver

# Do you mathematics in your documents?  Will your users want to write math
# in their comments?  Consider using MathJax for good looking math in HTML.
# http://www.mathjax.org/community/mathjax-in-use/
#
# Set this setting to the empty string ('') if you don't need math.
# Also, adjust the ``USE_MATHJAX`` setting at the top of the ucomment Javascript
# file, ``js_file``, to turn on MathJax.
mathjax_file = '' # or point to MathJax files: MEDIA_URL + 'MathJax/MathJax.js'

# These line(s) of text will be placed in front of the HTML served by Django.
html_prefix_text = """
<script type="text/javascript" src="%sjquery-1.4.2.min.js"></script>
<script type="text/javascript" src="%sfancybox/jquery.mousewheel-3.0.2.pack.js"></script>
<script type="text/javascript" src="%sfancybox/jquery.fancybox-1.3.1.pack.js"></script>
<link rel="stylesheet" type="text/css" href="%sfancybox/jquery.fancybox-1.3.1.css" media="screen" />
<script type="text/javascript">
            $(document).ready(function() {
        $("a[rel=sphinx_image]").fancybox();
                    $("a.embed").fancybox({
                'hideOnContentClick': true
            });
            });
</script>
""" % (MEDIA_URL, MEDIA_URL, MEDIA_URL, MEDIA_URL)

# These line(s) of text will be placed at the end of the HTML served by Django.
html_suffix_text = ('<script type="text/javascript" '
                    'src="http://yui.yahooapis.com/3.2.0/build/yui/'
                    'yui-min.js"></script>\n'
                    '<script type="text/javascript" src="%s"></script>\n') % \
                    js_file

if mathjax_file:
    html_suffix_text += ('<script type="text/javascript" src="%s"></script>\n'
                         '<!-- Call the ucomment Javascript file AFTER calling '
                         'MathJax -->\n<script>MathJax.Hub.Queue(function () '
                         '{ ucomments() });</script>') % mathjax_file

# This is the place to append any Analytics codes, e.g. Google Analytics:
# html_suffix_text += "Analytics code from vendor."

# HTML templates
# --------------
# Create the navigation links, shown at the top and bottom of each page
# Valid template variables:
#  * prev.link and prev.title,    <- both are not always available
#  * parent.link and parent.title <- points one level up, not available on TOC
#  * home.link and home.title     <- points to TOC, not available on TOC
#  * next.link, next.title,       <- both are not always available

# Please note that the links are always relative HTML links, while the
# The home link is an absolute link.

# Note: this template requires that you use "{{" to obtain "{" in the output.
html_navigation_template = '''\
{{% if prev  %}}
   <a href="{{{{ prev.link }}}}" title="Back to: {{{{ prev.title }}}}"
   accesskey="p">
   <!--<img alt="Back: {{{{ prev.title }}}}" src="{media_url}prev-button.png"/>-->
   previous</a> <!--|-->
{{% endif %}}
{{% if parent %}}
   <a href="{{{{ parent.link }}}}" title="Up one section: {{{{ parent.title }}}}"
   accesskey="u">
   <!--<img alt="Up: {{{{ parent.title }}}}" src="{media_url}up-button.png"/>-->
   up one section</a> <!--|-->
   <a href="{{{{ home.link }}}}" title="Home: {{{{home.title}}}}" accesskey="h">
   <!--<img alt="Home: {{{{home.title}}}}" src="{media_url}TOC-button.png"/>-->
   contents</a>
   {{% if next %}} <!--|--> {{% endif %}}
{{% endif %}}
{{% if next %}}
   <a href="{{{{next.link}}}}" title="Step ahead to: {{{{ next.title }}}}"
   accesskey="n">
   <!--<img alt="Step ahead to: {{{{ next.title }}}}" src="{media_url}next-button.png"/>-->
   next</a>
{{% endif %}}'''.format(media_url=MEDIA_URL)

# Template for the local table of contents (TOC), displayed in the sidebar
side_bar_local_toc_template = '''
{% if (page.local_toc != '') and (not page.is_toc) %}
    <h2>Subsections on this page:</h2>
    {{page.local_toc}}
{% endif %}
'''


# Django settings
# ---------------

# Assume this Django application is mounted at http://example.com/ucomment-app/
# and that this application was stored in the directory called "ucommentapp".
#
# Then assuming you have added this line to the Django PROJECT's ``urls.py``:
#                                                      ---------
#     (r'^document/', include('ucommentapp.urls')),
#
# then users access your document at: http://example.com/ucomment-app/document/
# For example ``chapter-1``  is available at
#     http://example.com/ucomment-app/document/chapter-1
#

# When the ucomment application receives this URL, it must strip out the
# ``document`` part.  We call this this ``url_views_prefix``.  Do not add any
# leading or trailing slash.  If you mount the application at the server's
# root, then set this to the empty string, ''.
url_views_prefix = 'document'

# Full path to where you would like the fixtures (back-ups) written to:
# Alternative: use a directory from ``DJANGO_SETTINGS.FIXTURE_DIRS`` if you
# have set it in your application.
django_fixtures_dir = application_path + 'fixtures'

# Send Python logging to this file: you must specify a valid, writable file
log_filename = mkdtemp() + sep + 'ucomment-app.log'

# Caching comment counts.  Counting comments can be expensive.  If the counting
# takes longer than ``cache_count_duration`` seconds, then Django will cache
# the counted result for ``cache_count_timout`` seconds.
# There is no drawback to caching counts.  If a new comment is approved then
# the cache for page on which it appears is deleted.
# You can set the ``cache_count_timout`` to zero (0) for no caching at all.
#
# You may need to specify ``CACHE_BACKEND`` is your Django settings.py file,
# but if you haven't Django will use 'locmem://' as the cache.
cache_count_duration = 0.6
cache_count_timout = 60 * 60 * 6

# Document splitting (experimental !)
# ------------------

# Do you want to split up long RST files in the document ?  If ``section_div``
# below is non-empty, then we will split the source RST files into smaller
# sections, each on their own page, as defined by the heading label``section_div``

# Which character is used to identify major sections within a chapter.  Use
# section_div = '' to prevent any file splitting.
section_div = ''
# How many consecutive characters do we look for to consider it a divider?
# I.e. the default settings will split any title with '===' or more dividers.
min_length_div = 3

# NOTE: Any RST file that contains a .. toctree:: directive will NOT BE
# commentable.  These RST files will automatically be added to the
# ``skip_nodes_in`` list below.

# RST compiling settings
# ----------------------

# Do not allow commenting in these source files.
# Do not use file extensions, and ensure the entries are relative to the source
# directory. For example, skip_nodes_in = ['contents', 'chapter1/section-2']
skip_nodes_in = ['contents']


# Comment compiling settings
# ---------------------------
# Directory where Sphinx compiles the web visitor's comments; no trailing slash
# Usually this directory is placed inside the Django application.  Must be
# writable by the webserver.
comment_compile_area = application_path + 'comment_compile_area'

# Email and message settings
# ---------------------------

# Email server details:  please ensure the following 5 are set in your Django
# project's ``settings.py`` file.  Please visit
# http://docs.djangoproject.com/en/dev/ref/settings/ if you are unsure of what
# these mean.

# EMAIL_HOST
# EMAIL_PORT
# EMAIL_HOST_USER
# EMAIL_HOST_PASSWORD
# EMAIL_FROM

# Email address from which any email to users and admins is sent.
email_from = EMAIL_FROM or 'Comments <web.comments@example.com>'

# Comment administrator email address(es): these people are emailed a link to
# either approve or reject newly submitted comments.
email_comment_administrators_list = [email_from]

# Ucomment system administrators: the person/people that should receive emails
# if any serious errors are encountered by the comment system. For example, when
# a failed repository checkout or update occurs.
# By default, use all email address(es) from your Django ``settings.py`` file.
email_system_administrators = [email[1] for email in ADMINS]
email_system_administrators_subject = 'Serious error: ucomment website'

# Email the web user once their comment is submitted, but not approved yet.
# Use the template below to structure the email.
# You may set this to an empty string if you don't want an email sent.
once_submitted_subject = 'Your comment submission to http://example.com'

# This email will be sent (if user provided an email).
once_submitted_template = '''\
{{poster.name}},

Thank you for submitting your comment to http://example.com - they are a \
valuable contribution to the site.  A copy of your comment appears below.

Comments are typically approved within 24 hours.  After posting \
{{settings.number_before_auto_approval}} approved comments, any future \
comment you post will be automatically approved.

Thanks again -- the http://example.com team.
---
Your comment:
{{comment.comment_RST}}
---
Please note: If you did not submit this comment, then some one else used your \
email address on our website.  Please reply to this email and let us know - we \
will remove the comment right away.  Please quote reference number: {{comment.parent}}:{{comment.node}}
'''

# This is the same version of the above message, except it is shown to the user
# as HTML in the browser right after they submitted a comment.
# Only ``settings`` and ``poster`` are available as template elements.
# The ``comment`` object is not available.
once_submitted_HTML_template = '''\
<p>Thank you for submitting your comment to example.com - they are a
valuable contribution to the site.

<p>Comments are typically approved within 24 hours.  After posting
{{settings.number_before_auto_approval}} approved comments, any future comments
you post will be automatically approved.

<p>Thanks again, from <a href="http://example.com">Example, Inc.</a>.
'''

# Email web user once their comment is approved (mentions number of approved
# comments they have to make before future comments are auto-approved).
email_number_remaining = True
once_approved_subject = 'Your comment on http://example.com is approved'
once_approved_template = '''\
Your recent comment made on the http://example.com website was approved.

{% if settings.email_number_remaining %}
You have now posted {{poster.number_of_approved_comments}} comments.  After
you post {{settings.number_before_auto_approval}} approved comments, all your \
future comments will be automatically approved.

{% endif %}
Thanks for your contribution - the http://example.com team.
'''

email_when_rejected_subject = 'Your comment on http://example.com was not approved'
email_when_rejected = '''\
Your recent comment made on the http://example.com website was not approved for
the following reason(s):

{{reason_rejected}}

{% if rejected_extra_info %}
{{rejected_extra_info}}
{% endif %}

The http://example.com team.
'''

# The web-based rejection interface will allow you to select one or more of the
# these reasons.
rejection_reasons = (
    'The comment was unrelated to the content of that page.',
    'The comment appears to be spam or commercial in nature.',
    'The comment contains inappropriate language for this website.',
    'Other reason: please see the additional notes below.',
    )

# Template for email sent to comment admin to approve to reject a comment.
# You may modify it as required, but you must at least include
# ``comment.approval_code`` and ``comment.rejection_code`` in the message.
email_for_approval_subject = 'Approve or reject new comment'
email_for_approval = '''\
A new comment was received from:

* Name = {{poster.name}}
* email = {{poster.email}}
* opted in for mailings = {{poster.opted_in}}
* number previously approved = {{poster.number_of_approved_comments}}
* IP number = {{comment.IP_address}}

Their comment was related to content in:

* file: {{reference.file_name}}
* around line number: {{reference.line_number}}
* with comment root: {{reference.comment_root}}
* and comment node: {{comment.node}}
* appearing on this page: {{webpage}}

Their comment was:
{{comment.comment_HTML}}

Original RST for their comment:
{{comment.comment_RST}}

Click this link to ACCEPT the comment: {{comment.approval_code}}
To REJECT the comment, click here: {{comment.rejection_code}}
'''

# Create a ``local_settings.py`` file that overrides settings in this file.
# This is useful if you update ucommentapp from revision control and don't want
# to loose your settings everytime.  Be sure to check for diffs against
# this file (conf/settings.py).
this_dir = __file__[0:__file__.find('settings.py')]
try:
    execfile(this_dir + sep + 'local_settings.py')
except IOError:
    pass

del this_dir, sep, getcwd, mkdtemp
