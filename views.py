"""
:copyright: Copyright 2010, by Kevin Dunn
:license: BSD, see LICENSE file for details.

TO ADD:
 ---------
 Add a time-out to comment compiling (5 seconds): then force a return
 Deferred processing of comments using a message queue:
    http://www.turnkeylinux.org/blog/django-celery-rabbitmq
    Why?  Because we have to do a repo checkout, update the files, commit

 CAPTCHA
 Use PostgreSQL instead
 Handle the case where commit fails because a user name is not present.

FUTURE
======
Create a web-interface to approve or reject comments; allowing the comment admin
to pick various reasons to reject comment and append extra info to the poster.
Also provide option NOT to send an email at all (simply reject the posting).
"""

# Standard library imports
import os, sys, random, subprocess, pickle, re, logging.handlers, datetime
import smtplib, time
from shutil import copyfile
from collections import defaultdict, namedtuple

# Settings for the ucomment application
from conf import settings as conf

# Django and Jinja import imports
from django import forms, template
from django.shortcuts import render_to_response
from django.contrib import auth as django_auth
from django.core import cache as django_cache
from django.core.context_processors import csrf
from django.core.mail import send_mail, BadHeaderError
from django.http import HttpResponse, HttpResponseRedirect
from django.core.urlresolvers import reverse as django_reverse
from django.utils import simplejson            # used for XHR returns
from django.utils import html as django_html   # used for clean search results

from jinja2 import Template  # Jinja2 is Sphinx dependency; should be available
from jinja2.exceptions import TemplateSyntaxError

# Sphinx import
from sphinx.util.osutil import ensuredir

if conf.repo_DVCS_type == 'hg':
    import hgwrapper as dvcs
    dvcs.executable = conf.repo_DVCS_exec
    dvcs.local_repo_physical_dir = conf.local_repo_physical_dir

# Import the application's models, without knowing the application name.
models = getattr(__import__(conf.app_dirname, None, None, ['models']),'models')

# The ucomment directive:
COMMENT_DIRECTIVE = '.. ucomment::'

# These words will be removed from any search
# Taken from: http://www.ranks.nl/resources/stopwords.html
STOP_WORDS = ['I', 'a', 'an', 'are', 'as', 'at', 'be', 'by', 'com', 'for',
              'from', 'how', 'in', 'is', 'it', 'of', 'on', 'that', 'the',
              'this', 'to', 'was', 'what', 'when', 'who', 'will', 'with',
              'www']

# Code begins from here
# ---------------------
log_file = logging.getLogger('ucomment')
log_file.setLevel(logging.INFO)
fh = logging.handlers.RotatingFileHandler(conf.log_filename,
                                          maxBytes=5000000,
                                          backupCount=10)
formatter = logging.Formatter(('%(asctime)s - %(name)s '
                               '- %(levelname)s - %(message)s'))
fh.setFormatter(formatter)
log_file.addHandler(fh)

class UcommentError(Exception):
    """ A generic error inside this Django application.  Will log the error,
    and email the site administrator.

    This class must be initiated an exception object:
        * UcommentError(exc_object)

    But an optional string can also be provided, to give the log and email
    message some extra information:
        * UcommentError(exc_object, err_msg)

    This will figure out where the error was raised and provide some
    source code lines in the email.

    An alternative way to call this class is to just with a string input
        * UcommentError(err_msg)

    But this will only email and log the given error message string.

    The exception will not be raised again here: it is the calling function's
    choise whether to reraise it (and possibly interrupt the user's experience),
    or whether to just let the application continue.
    """
    def __init__(self, error, extra=''):
        if isinstance(error, Exception):
            exc = sys.exc_info()
            from inspect import getframeinfo
            emsg = 'The error that was raised: ' + str(exc[1]) + '\n\n'
            if extra:
                emsg += 'This additional information was provided: "%s"' % extra
                emsg += '\n\n'
            emsg += self.format_frame(getframeinfo(exc[2], context=5))
        else:
            # Handles an older syntax
            emsg = 'The following error was raised: ' + error.__repr__()
        if isinstance(error, UcommentError) and error.raised:
            return
        self.raised = True  # prevent errors with emailing from cycling again.
        log_file.error(emsg)
        alert_system_admin(emsg)

    def format_frame(self, traceback):
        """ Receives a named tuple, ``traceback``, created by the ``inspect``
        module's ``getframeinfo()`` function.  Formats it to string output.
        """
        out =  '*\tfilename    = %s\n' % os.path.abspath(traceback.filename)
        out += '*\tline number = %s\n' % traceback.lineno
        out += '*\tfunction    = %s(...)\n' % traceback.function
        out += '*\tsource code where error occurred:\n'
        for idx, line in enumerate(traceback.code_context):
            out += '\t\t%s' % line.rstrip()
            if idx == traceback.index:
                out += '    <--- error occurred here\n'
            else:
                out += '\n'
        return out + '\n'


def create_codes_ID(num):
    """
    Creates a new comment identifier; these appear in the source code for
    each page; they must be short, not confusing, and low chance of collisions.

    Intentionally does not include "i", "I", "l" "D", "o", "O", "Z", "0" to
    avoid visual confusion with similar-looking characters.  We (ab)use this
    fact to create the orphan comment reference with name = '_ORFN_'.

    53 characters, N=4 combinations = 53^4 = many comment ID's
    """
    valid_letters = 'abcdefghjkmnpqrstuvwxyzABCEFGHJKLMNPQRSTUVWXY23456789'
    return ''.join([random.choice(valid_letters) for i in range(num)])

def convert_web_name_to_link_name(page_name, prefix=''):
    """
    Converts the web page name over to the ``link_name`` used in the Django
    model for ``Page``.

    If a prefix is provided (e.g. the fully web address), then this is stripped
    off first, then the rest is used as the page_name.
    """
    if prefix:
        page_name = page_name.split(prefix)[1]
    if '?' in page_name:
        page_name = page_name.split('?')[0]
    if conf.url_views_prefix:
        return page_name.split('/'+conf.url_views_prefix+'/')[1].rstrip('/')
    else:
        return page_name.lstrip('/').rstrip('/')

    # TODO(KGD): remove ``conf.url_views_prefix``, and the need for this
    #            function.  Can we not use the reverse(..) function?

def get_site_url(request, add_path=True, add_views_prefix=False):
    """
    Utility function: returns the URL from which this Django application is
    served.  E.g. when receiving a Django ``request`` object from the user
    on comment submission, their URL might be:
        https://site.example.com/document/_submit-comment/

    >>> get_site_url(request)
    'https://site.example.com/document/_submit-comment/'
    """
    # TODO(KGD): Consider using ``request.build_absolute_uri()`` instead
    out = 'http://'
    if request.is_secure():
        out = 'https://'
    out += request.get_host()
    if add_path:
        out += request.path
    if add_views_prefix:
        if conf.url_views_prefix:
            out += '/' + conf.url_views_prefix + '/'
        else:
            out += '/'
    return out

def get_IP_address(request):
    """
    Returns the visitor's IP address as a string.
    """
    # Catchs the case when the user is on a proxy
    try:
        ip = request.META['HTTP_X_FORWARDED_FOR']
    except KeyError:
        ip = ''
    else:
        # HTTP_X_FORWARDED_FOR is a comma-separated list; take first IP:
        ip = ip.split(',')[0]

    if ip == '' or ip.lower() == 'unkown':
        ip = request.META['REMOTE_ADDR']      # User is not on a proxy
    return ip

# Comment preview and submission functions
# ----------------------------------------
class CommentForm(forms.Form):
    """ Comment form as seen on the server """
    email = forms.EmailField(required=False)
    comment_raw = forms.CharField(min_length=conf.comment_min_length,
                                  max_length=conf.comment_max_length)

def valid_form(p_email, comment_raw):
    """ Verifies if a valid form was filled out.

    Returns an empty string if the form is valid.
    Returns a string, containing an HTML error message if the form is not valid.
    """
    # Ignore empty email addresses; email field is optional anyway, but we do
    # want to alert the user if the email is invalid.
    if p_email.strip() == '':
        p_email = 'no.email@example.com'
    user_form = CommentForm({'email': p_email,
                             'comment_raw': comment_raw})

    if not user_form.is_valid():
        error_dict = user_form.errors
        errors = ['<ul class="ucomment-error">']
        if 'email' in error_dict:
            errors.append(('<li> Your email address is not in the correct '
                           'format.</li>'))
        if 'comment_raw' in error_dict:
            errors.append(('<li> Comments must have between %i and %i '
                           'characters.</li>' % (conf.comment_min_length,
                                                 conf.comment_max_length)))
        errors.append('</ul>')
        log_file.info('Returning with these errors:' + str(errors))
        return ''.join(errors)
    else:
        return ''

def initial_comment_check(request):
    """
    Provides a preliminary check of the comment submission.
    * Must be a POST request not at a GET request.
    * Must have a valid email address.
    * Comment length must be appropriate (see conf/settings.py file).
    """

    if request.method == 'POST':
        c_comment_RST = request.POST['comment']
        p_email = request.POST['email']
        errors = valid_form(p_email, c_comment_RST)
        if errors:
            web_response = HttpResponse(errors, status=200)
            web_response['ucomment'] = 'Preview-Invalid input'
            return False, web_response
        else:
            return True, c_comment_RST
    elif request.method == 'GET':
        return False, HttpResponse('N/A', status=404)
    elif request.method == 'OPTIONS':
        # Handles a Firefox probe before the POST request is received.
        web_response = HttpResponse(status=404)
        web_response['Access-Control-Allow-Origin'] = '*'
        return False, web_response
    else:
        log_file.warn(request.method + ' received; not handled; return 400.')
        return False, HttpResponse(status=400)

def preview_comment(request):
    """
    User has clicked the "Preview comment" button in browser. Using XHR, the
    comment is POSTed here, extracted, and compiled.
    """
    # ``Success``: means the submission was validated, or was processed.
    # If it failed, then ``response`` will contain an appropriate HttpResponse
    # that can be returned right away.
    success, response = initial_comment_check(request)
    if success:
        web_response = HttpResponse(status=200)
        try:

            compiled_comment_HTML = compile_comment(response)
            web_response['ucomment'] = 'Preview-OK'
        except Exception as err:
            # Should an error occur while commenting, log it, but respond to
            # the user.
            UcommentError(err, ('An exception occurred while generating a  '
                                'comment preview for the user.'))
            compiled_comment_HTML = ('<p>An error occurred while processing '
                                     'your comment.  The error has been '
                                     'reported to the website administrator.'
                                     '<p>UTC time of error: %s' % \
                                     datetime.datetime.utcnow().ctime())
            web_response['ucomment'] = 'Preview-Exception'

        log_file.info('COMPILE: from IP=%s; comment: "%s"' % \
                        (get_IP_address(request), response))
        web_response.write(compiled_comment_HTML)
        return web_response
    else:
        return response

def compile_comment(comment):
    """
    First scans the ``comment`` string, then compiles the RST to HTML.
    """
    # The Javascript XHR request have a timeout value (set to 5 seconds).
    # set a timer on the compile time?  If more than 5 seconds to
    # compile, then log the comment, return a response back to the user.
    start_time = time.time()
    comment = compile_RST_to_HTML(comment)
    end_time = time.time()
    if (end_time-start_time) > 3:
        log_file.warning(('Comment compile time exceeded 3 seconds; server'
                          'load too high?'))
    return comment

def call_sphinx_to_compile(working_dir):
    """
    Changes to the ``working_dir`` directory and compiles the RST files to
    pickle files, according to settings in the conf.py file.

    Returns nothing, but logs if an error occurred.
    """

    sphinx_command = ['sphinx-build', '-b', 'pickle', '-d',
                      '_build/doctrees', '.', '_build/pickle']
    try:
        subprocess.check_call(sphinx_command,
                              stdout=subprocess.PIPE,
                              cwd=working_dir)
    except subprocess.CalledProcessError as err:
        log_file.error('An error occurred when generating HTML from comment.')
        raise(err)
    log_file.debug('COMMENT: called Sphinx; pickled the HTML.')

def convert_raw_RST(raw_RST):
    """
    Performs any sanitizing of the user's input.

    Currently performs:
    * converts '\\' to '\\\\': i.e. single slash converted to double-slash,
                               because Sphinx converts is back to a single slash
    """
    out = raw_RST.replace('\\', '\\\\')
    # You can perform any other filtering here, if required.
    return out

def compile_RST_to_HTML(raw_RST):
    """ Compiles the RST string, ``raw_RST`, to HTML.  Performs no
    further checking on the RST string.

    If it is a comment, then we don't modify the HTML with extra class info.
    But we do filter comments to disable hyperlinks.

    Also copy over generated MATH media to the correct directory on the server.
    """

    ensuredir(conf.comment_compile_area)
    modified_RST = convert_raw_RST(raw_RST)
    with open(conf.comment_compile_area + os.sep + 'index.rst', 'w') as fhand:
        fhand.write(modified_RST)

    try:
        conf_file = conf.comment_compile_area + os.sep + 'conf.py'
        f = file(conf_file, 'r')
    except IOError:
        # Store a fresh copy of the "conf.py" file, found in
        # ../sphinx-extensions/ucomment-conf.py; copy it to comment destination.
        this_file = os.path.abspath(__file__).rstrip(os.sep)
        parent = this_file[0:this_file.rfind(os.sep)]
        src = os.sep.join([parent, 'sphinx-extensions', 'ucomment-conf.py'])
        copyfile(src, conf.comment_compile_area + os.sep + 'conf.py')
    else:
        f.close()

    # Compile the comment
    call_sphinx_to_compile(conf.comment_compile_area)

    pickle_f = ''.join([conf.comment_compile_area, os.sep, '_build', os.sep,
                        'pickle', os.sep, 'index.fpickle'])
    with open(pickle_f, 'r') as fhand:
        obj = pickle.load(fhand)

    html_body = obj['body'].encode('utf-8')

    # Any equations in the HTML?  Transfer these images to the media directory
    # and rewrite the URL's in the HTML.
    return transfer_html_media(html_body)

def transfer_html_media(html_body):
    """
    Any media files referred to in the HTML comment are transferred to a
    sub-directory on the webserver.

    The links are rewritten to refer to the updated location.
    """
    mathdir = ''.join([conf.comment_compile_area, os.sep, '_build', os.sep,
                       'pickle', os.sep, '_images', os.sep, 'math', os.sep])
    ensuredir(mathdir)
    dst_dir = conf.MEDIA_ROOT + 'comments' + os.sep
    ensuredir(dst_dir)

    for mathfile in os.listdir(mathdir):
        copyfile(mathdir + mathfile, dst_dir + mathfile)

    src_prefix = 'src="'
    math_prefix = '_images' + os.sep + 'math' + os.sep
    replacement_text = ''.join([src_prefix, conf.MEDIA_URL,
                                'comments', os.sep])
    html_body = re.sub(src_prefix + math_prefix, replacement_text, html_body)
    return html_body


def create_poster(request):
    """
    Creates a new ``CommentPoster`` object from a web submission, ``request``.
    """
    p_name = request.POST['name'].strip() or 'Anonymous contributor'
    p_email = request.POST['email'].strip()

    # The default (unchecked box) is for opt-in = False
    p_opted_in = True
    try:
        # Fails if unchecked (default); succeeds if checked: caught in "else"
        p_opted_in = request.POST['updates'] == 'get_updates'
    except KeyError:
        p_opted_in = False

    # Get the poster entry, or create a new one.  Always create a new poster
    # entry for anonymous posters.
    c_IP_address = get_IP_address(request)
    c_UA_string = request.META['HTTP_USER_AGENT'][0:499]  # avoid DB overflow
    p_default = {'name' : p_name,
                 'long_name': p_name + '__' + c_IP_address + '__' + c_UA_string,
                 'email': p_email,
                 'number_of_approved_comments': 0,
                 'avatar_link': '', # add this functionality later?
                 'auto_approve_comments': False,
                 'opted_in': False}

    if p_email:
        if p_name.lower() not in ('anonymous', 'anonymous contributor', ''):
            p_default['long_name'] = p_name
        poster, _ = models.CommentPoster.objects.get_or_create(email=p_email,
                                                        defaults=p_default)
        poster.opted_in = poster.opted_in or p_opted_in
        poster.save()
    else:
        poster, _ = models.CommentPoster.objects.get_or_create(\
                                                            defaults=p_default)

    # Change settings for all posters:
    if poster.number_of_approved_comments >= conf.number_before_auto_approval:
        poster.auto_approve_comments = True
        poster.number_of_approved_comments += 1
        poster.save()


    log_file.info('POSTER: Created/updated poster: ' + str(poster))
    return poster

def submit_and_store_comment(request):
    """
    The user has typed in a comment and previewed it. Now store it and queue
    it for approval.

    ``Comment`` objects have 3 ForeignKeys which must already exist prior:
    * ``page``: the page name on which the comment appears
    * ``poster``: an object representing the person making the comment
    * ``reference``: a comment reference that facilitates making the comment
    """

    start_time = time.time()

    # Response back to user, if everything goes OK
    response = HttpResponse(status=200)
    response['ucomment'] = 'Submission-OK'
    try:
        html_template = Template(conf.once_submitted_HTML_template)
    except TemplateSyntaxError as err:
        # Log the error, but don't disrupt the response to the user.
        html_template = Template('Thank you for your submission.')
        UcommentError(err, "Error in 'once_submitted_HTML_template'.")

    # Note about variable names: ``p_`` prefix refers to poster objects in the
    # database, while ``c_`` = refers to comment objects.

    # ForeignKey: comment object (setup only; will be created at the end)
    # --------------------------
    success, c_comment_RST = initial_comment_check(request)
    if not success:
        return c_comment_RST
    else:
        c_comment_HTML = compile_comment(c_comment_RST)

    # Only get the comment reference via its root:
    ref = models.CommentReference.objects.filter(\
                                     comment_root=request.POST['comment_root'])
    if len(ref):
        c_reference = ref[0]
    else:
        # One possibility to consider is to create the comment reference
        # right here.  However, it is quite hard to do this properly, because
        # do not know all the field properties for a CommentReference object:
        # such as the line number, page_link_name, node_type, and others.

        # This will only occur in the exceptional case when the document
        # has been republished, and the user still has a previous version in
        # their browser.  Hence the page reload request.
        response.write(('<p>A minor error occurred while processing your '
                        'comment.<p>The only way to correct it is to reload '
                        'the page you are on, and to resubmit your comment. '
                        '<p>Sorry for the inconvenience.'))
        log_file.warn('COMMENT: User posting a comment from an older page.')
        return response

    # Below the comment reference appears an unique node:
    used_nodes = []
    c_node = create_codes_ID(conf.short_node_length)
    for comment in c_reference.comment_set.all():
        used_nodes.append(comment.node)
    while c_node in used_nodes:
        c_node = create_codes_ID(conf.short_node_length)


    # ForeignKey: page object; get the page on which the comment appears
    # -----------------------
    link_name = convert_web_name_to_link_name(request.POST['page_name'])
    c_page = models.Page.objects.filter(link_name=link_name)[0]

    # ForeignKey: comment poster objects
    # -----------------------------------
    poster = create_poster(request)
    # We can update the response as soon as we have created the poster object
    response.write(html_template.render(settings=conf, poster=poster))

    if poster.number_of_approved_comments >= conf.number_before_auto_approval:
        c_is_approved = True
        c_node_for_RST = c_node
    else:
        c_node_for_RST = c_node + '*'    # indicates comment is not approved yet

    # Do all the work here of adding the comment to the RST sources
    revision_changeset, c_root = commit_comment_to_sources(\
                                                    c_reference,
                                                    c_node_for_RST,
                                                    update_RST_with_comment)

    # NOTE: the line numbers for any comment references that might appear below
    #       the current comment reference will be incorrect - they will be too
    #       low.  However, their line numbers will be rectified once the
    #       document is republished (comment references are updated).

    # An error occurred:
    if revision_changeset == False:
        # Technically the submission is NOT OK, but the comment admin has been
        # emailed about the problem and can manually enter the comment into
        # the database and RST source files.
        return response

    # Update the ``comment_root_is_used`` field in the comment reference, since
    # this root can never be used again.
    c_reference.comment_root_is_used = True
    # Also update the changeset information.  In the future we will update
    # comments for this node from this newer repository.
    c_reference.revision_changeset = revision_changeset
    c_reference.save()

    # Create the comment object
    c_datetime_submitted = c_datetime_approved = datetime.datetime.now()
    c_IP_address = get_IP_address(request)
    c_UA_string = request.META['HTTP_USER_AGENT'][0:499]  # avoid DB overflow
    c_approval_code = create_codes_ID(conf.approval_code_length)
    c_rejection_code = create_codes_ID(conf.approval_code_length)
    c_is_approved = c_is_rejected = False

    # For now all comments have no parent (they are descendents of the comment
    # root). Later, perhaps, we can add threading functionality, so that users
    # can respond to previous comments.  Then the parent of a new comment will
    # be given by:  ``c_root + ':' + parent_comment.node``
    c_parent = c_root

    the_comment, _ = models.Comment.objects.get_or_create(
        page = c_page,
        poster = poster,
        reference = c_reference,
        node = c_node,
        parent = c_parent,
        UA_string = c_UA_string,
        IP_address = c_IP_address,
        datetime_submitted = c_datetime_submitted,
        datetime_approved = c_datetime_approved,
        approval_code = c_approval_code,
        rejection_code = c_rejection_code,
        comment_HTML = c_comment_HTML,
        comment_RST = c_comment_RST,
        is_rejected = c_is_rejected,
        is_approved = c_is_approved)

    log_file.info('COMMENT: Submitted comment now saved in the database.')

    # Send emails to the poster and comment admin regarding the new comment
    # TODO(KGD): queue it
    emails_after_submission(poster, the_comment, request)

    total_time = str(round(time.time() - start_time, 1))
    log_file.info(('COMMENT: Emails to poster and admin sent successfully; '
                    "returning response back to user's browser.  Total time to "
                    ' process comment = %s secs.') % total_time)
    return response

def approve_reject_comment(request, code):
    """
    Either approves or rejects the comment, depending on the code received.

    Approved comments:
    - The # part after the comment node is removed in the RST file
    - The comment is marked as approved in the database and will appear on
      the next page refresh.
    - The poster is notified by email (if an email was supplied)

    Rejected comments:
    - The # part after the comment node is changed to a * in the RST  file
    - The comment is marked as rejected in the database.
    - The poster is notified by email (if an email was supplied)
    """
    # Response back to user, if everything goes OK
    response = HttpResponse(status=200)
    approve = models.Comment.objects.filter(approval_code=code)
    reject = models.Comment.objects.filter(rejection_code=code)

    # Settings used to approve the comment: we remove the '*'
    if len(approve) == 1:
        verb = 'approved'
        symbol = '\*'  # escaped, because it will be used in a regular expressn
        replace = ''
        comment = approve[0]
        comment.is_approved = True
        comment.is_rejected = False
        email_func = email_poster_approved

    # Settings used to reject the comment: we change the '*' to a 	'#'
    elif len(reject) == 1:
        verb = 'rejected'
        symbol = '\*'
        replace = '#*'
        comment = reject[0]
        comment.is_approved = False
        comment.is_rejected = True
        email_func = email_poster_rejected

    # Bad approve/reject code given: don't mention anything; just return a 404.
    else:
        return HttpResponse('', status=404)

    revision_changeset, _ = commit_comment_to_sources(comment.reference,
                                                comment.node,
                                                update_RST_comment_status,
                                                additional={'search': symbol,
                                                            'replace': replace})

    if revision_changeset == False:
        # An error occurred while committing the comment.  An email has already
        # been sent.  Return a message to the user:
        response.write(('An error occurred while approving/rejecting the '
                        'comment.  Please check the log files and/or email for '
                        'the site administrator.'))
        return response

    comment.reference.comment_root_is_used = True
    # Also update the changeset information.  In the future we will update
    # comments for this node from this newer repository.
    comment.reference.revision_changeset = revision_changeset
    comment.reference.save()
    if verb == 'approved':
        comment.poster.number_of_approved_comments += 1
    elif verb == 'rejected':
        comment.poster.number_of_approved_comments -= 1
        comment.poster.number_of_approved_comments = max(0,
                                    comment.poster.number_of_approved_comments)
    comment.poster.save()
    comment.datetime_approved = datetime.datetime.now()
    comment.save()

    # Remove the comment count cache for the page on which this comment appears
    cache_key = 'counts_for__' + comment.page.link_name
    django_cache.cache.delete(cache_key)

    # Send an email the comment poster: rejected or approved
    email_func(comment.poster, comment)

    approve_reject_template = Template(('<pre>'
                        'The comment was {{action}}.\n\n'
                        '\t* Comment root = {{reference.comment_root}}\n'
                        '\t* Comment node = {{comment.node}}\n'
                        '\t* At line number = {{reference.line_number}}\n'
                        '\t* In file name = {{filename}}\n'
                        '\t* Committed as changeset = {{changeset}}\n\n</pre>'))
    output = approve_reject_template.render(action=verb.upper(),
                                            reference = comment.reference,
                                            comment = comment,
                                            filename = os.path.split(\
                                            comment.reference.file_name)[1],
                                            changeset = revision_changeset)
    response.write(output)

    return response


# Repository manipulation functions
# ---------------------------------
def update_local_repo(rev='tip'):
    """
    Updates the local repository from the remote repository and must be used
    before performing any write operations on files in the repo.

    If the local repository does not exist, it will first create a full clone
    from the remote repository.

    Then it does the equivalent of:
    * hg pull   (pulls in changes from the remote repository)
    * hg update (takes our repo up to tip)
    * hg merge  (merges any changes that might be required)

    Then if the optional input ``rev`` is provided, it will revert the
    repository to that revision, given by a string, containing the hexadecimal
    indicator for the required revision.

    This function returns the hexadecimal changeset for the local repo as
    it has been left after all this activity.
    """
    # First check if the local repo exists; if not, create a clone from
    # the remote repo.
    try:
        try:
            ensuredir(conf.local_repo_physical_dir)
        except OSError as err:
            msg = ('The local repository location does not exist, or cannot '
                   'be created.')
            raise UcommentError(err, msg)

        hex_str = dvcs.get_revision_info()
    except dvcs.DVCSError:
        try:
            dvcs.clone_repo(conf.remote_repo_URL, conf.local_repo_URL)
        except dvcs.DVCSError as error_remote:
            msg = ('The remote repository does not exist, or is '
                   'badly specified in the settings file.')
            raise UcommentError(error_remote, msg)

        log_file.info('Created a clone of the remote repo in the local path')

    # Update the local repository to rev='tip' from the source repo first
    try:
        dvcs.pull_update_and_merge()
    except dvcs.DVCSError as err:
        raise UcommentError(err, 'Repository update and merge error')

    hex_str = dvcs.get_revision_info()
    if rev != 'tip' and isinstance(rev, basestring):
        hex_str = dvcs.check_out(rev=rev)
    return hex_str

def commit_to_repo_and_push(commit_message):
    """
    Use this after performing any write operations on files.

    Commits to the local repository; pushes updates from the local repository
    to the remote repository.

    Optionally, it will also update the remote repository to the tip (the
    default is not to do this).

    Returns the changeset code for the local repo on completion.
    """
    hex_str = dvcs.commit_and_push_updates(commit_message)

    # Merge failed!  Log it and email the site admin
    if not(hex_str):
        raise UcommentError(('Repo merging failed (conflicts?) when trying to '
                             'commit. Commit message was: %s' % commit_message))

    # Check that changeset and revision matches the remote repo numbers
    return hex_str

def commit_comment_to_sources(reference, node, func, additional=None):
    """
    Commits or updates a comment in the RST sources.

    ``reference``: is a comment reference object from the database and tells
                   us how and where to add the comment
    ``node``: is the commment noded (string) that is added to the RST source.
    ``func``: does the work of either adding or updating the RST sources.
    ``additional``: named keywords and values in a dict that will be passed
                    to ``func``.

    On successful completion it will return:
    ``revision_changeset``: string identifier for the updated repository
    ``comment_root``: a string of the comment root that was added/updated
    """
    # This part is sensitive to errors occurring when writing to the
    # RST source files.
    try:

        # Get the RST file to the revision required for adding the comment:
        hex_str = update_local_repo(reference.revision_changeset)

        f_handle = file(reference.file_name, 'r')
        RST_source = f_handle.readlines()
        f_handle.close()

        # Add the comment to the RST source; send the comment reference
        # which has all the necessary input information in it.
        try:
            if additional == None:
                additional = {}
            c_root = func(comment_ref = reference,
                          comment_node = node,
                          RST_source = RST_source, **additional)
        except Exception as err:
            # will be caught in outer try-except
            # TODO(KGD): test that this works as expected: what happens after?
            raise UcommentError(err, ('General error while adding or updating '
                                      'comment in the RST sources.'))

        # Write the update list of strings, RST_source, back to the file
        f_handle = file(reference.file_name, 'w')
        f_handle.writelines(RST_source)
        f_handle.close()

        short_filename = os.path.split(reference.file_name)[1]
        commit_message = ('COMMIT: Automatic comment [comment_root=%s, '
                          'node=%s, line=%s, file=%s]; repo_id=%s') % \
                       (c_root, node, str(reference.line_number),
                        short_filename, hex_str)
        hex_str = commit_to_repo_and_push(commit_message)
        log_file.info(commit_message)
        return hex_str, c_root
    except (UcommentError, dvcs.DVCSError) as err:
        UcommentError(err)
        return False, False


def update_RST_with_comment(comment_ref, comment_node, RST_source):
    """
    Appends the ``comment_node`` string (usually a 2-character string), to the
    appropriate line in the RST_source (a list of strings).

    ``comment_ref`` provides the line number and node type which will be
    commented.  We always use an existing comment root, if there is one,
    otherwise we create a new comment root according to these rules:

    Paragraphs, titles, literal_block (source code blocks), tables and figures
    will have their ucomment appended in the second blank line after the node.

    List items (bullet points and ordered lists) will have their ucomment
    appended in the very next line, always.

    In all cases, an existing ucomment directive for that node will be searched
    for and added to.

    The simplest example possible: comment_node='2s' and comment_root='sR4fa4':

    RST_source before (1 line)

        Here is a paragraph of text.

    RST_source after (3 lines):

        Here is a paragraph of text.

        .. ucomment:: sR4fa4: 2s

    Output and side effects:
        * Returns the comment_root as the only output.
        * Modifies the list of strings, ``RST_source`` in place.
    """
    # We can only handle these nodes: anything else will raise an error
    KNOWN_NODES = set(('paragraph', 'title', 'literal_block', 'table',
                       'image', 'list_item', 'displaymath'))

    # Regular expression, which when matched AT THE START OF A LINE, indicate
    # list items in the RST syntax. See the full RST specification:
    # http://docutils.sourceforge.net/docs/user/rst/quickstart.html
    RST_LIST_ITEMS_AS_RE = re.compile(r'''(\s*)
                        (                 # group all list item types
                        (\-)|(\*)|(\+)|   # any bullet list items
                        (\#\.)|           # auto-enumerate: "#."
                        (\w*\.)|          # enumerated: "12." or "A." or "i."
                        (\(\w*\))|        # enumerated: "(23)" or "(B)"
                        (\w\))            # enumerated: "12)" or "iii)"
                        )                 # end of all list item types
                        (?P<space>\s*)    # catch trailing spaces at end.''', \
                                                                        re.X)
    # Maps ``node_type`` to RST directives
    NODE_DIRECTIVE_MAP = {'displaymath': ['math'],
                          'image': ['image', 'figure'],
                          'table': ['table', 'csv-table', 'list_table'],
                          'literal_block': ['code-block', 'literalinclude'],}

    # Nodes given by the ``keys`` in NODE_DIRECTIVE_MAP allow blank lines
    # within in their content, so determining where to place the ucomment
    # directive cannot rely purely on finding the next blank line.  Example:
    #
    #   |Before                         |After
    #   |--------------------------------------------------------------
    # 1 |.. figure:: the_figure.png     |.. figure:: the_figure.png
    # 2 |    :scale: 100%               |    :scale: 100%
    # 3 |                               |
    # 4	|    Figure caption goes here.  |    Figure caption goes here.
    # 5 |                               |
    # 6 |Next paragraph begins here.    |..ucomment:: ABCDEF: 2b
    # 7 |                               |
    # 8 |                               |Next paragraph begins here.
    #
    # It would be wrong to place the ucomment directive at/around line 3
    # as this would cut of the figure's caption.  What we do instead is to
    # find the end of the node and insert the comment at that point.


    def wrap_return(RST_source, insert, prefix):
        """
        Adds the new ucomment directive and return the updated RST_source,
        or, appends to the existing comment.
        """

        if prefix is None:
            comment = RST_source[insert]
            c_root = comment.strip()[dir_len+1:dir_len+1+conf.root_node_length]
            # Always add a comma after the last comment
            if not comment.rstrip().endswith(','):
                suffix = ', '
            else:
                suffix = ' '
            RST_source[insert] = comment[0:-1] + suffix + comment_node + ',\n'

        else:
            c_root = comment_ref.comment_root
            line_to_add = prefix + COMMENT_DIRECTIVE + ' ' + c_root + ': ' + \
                        comment_node + ',\n'

            if comment_ref.node_type in KNOWN_NODES:
                RST_source.insert(insert, '\n')

            RST_source.insert(insert, line_to_add)

        # Pop off the last line of text that was artifically added.
        RST_source.pop()

        return c_root

    # A few corner cases are solved if we ensure the file ends with a blank line
    if RST_source[-1].strip() != '':
        RST_source.append('\n')
    # Force an unrelated line at the end of the file to avoid coding
    # specifically for end-effects.
    RST_source.extend(['___END__OF___FILE___\n'])

    # The comment reference line numbers are 1-based; we need 0-based numbers
    line_num = comment_ref.line_number - 1
    dir_len = len(COMMENT_DIRECTIVE)

    if comment_ref.node_type not in KNOWN_NODES:
        raise UcommentError('Unknown node type: "%s"' % str(comment_ref))

    # To find any spaces at the start of a line
    prefix_re = re.compile('^\s*')
    prefix_match = prefix_re.match(RST_source[line_num])
    prefix = prefix_match.group()

    # There is one exception though: source code blocks marked with '::'
    # While the node's line number refers to the first line of code, the correct
    # prefix is the amount of space at the start of the line containing the '
    # double colons.  Search backwards to find them.
    # If we can't find them, then this literal_block is assumed to be a
    # 'code-block', or 'literalinclude' node (i.e. no double colons).
    if comment_ref.node_type == 'literal_block':
        double_colon = re.compile(r'(?P<space>\s*)(.*)::(\s*)')
        directive_re = r'(\s*)\.\. '
        for directive in NODE_DIRECTIVE_MAP['literal_block']:
            directive_re += '(' + directive + ')|'
        directive_re = directive_re[0:-1] + r'::(\s*)'
        directive = re.compile(directive_re)

        for line in RST_source[line_num-1::-1]:
            if directive.match(line):
                break # it is one of the other directives
            if double_colon.match(line):
                prefix = double_colon.match(line).group('space')
                break

    # The point where the ucomment directive will be inserted
    insert = line_num + 1

    # We are *always* given the top line number of the node: so we only have to
    # search for the insertion point below that.  We will start examining from
    # the first line below that.
    finished = False
    next_line = ''
    idx_next = 0
    for idx, line in enumerate(RST_source[line_num+1:]):
        insert += 1  # insert = line_num + idx + 1
        bias = idx + 2
        if line.strip() == '' or comment_ref.node_type == 'list_item':
            if comment_ref.node_type == 'list_item':
                bias -= 1

            # Keep looking further down for an existing ucomment directive
            for idx_next, next_line in enumerate(RST_source[line_num+bias:]):
                if next_line.strip() != '':
                    if next_line.lstrip()[0:dir_len] == COMMENT_DIRECTIVE:
                        insert = line_num + bias + idx_next
                        prefix = None
                        return wrap_return(RST_source, insert, prefix)
                    finished = True
                    break

        if finished:
            next_prefix = prefix_re.match(next_line.rstrip('\n')).group()

            # Certain nodes cannot rely purely on blank lines to mark their end
            if comment_ref.node_type in NODE_DIRECTIVE_MAP.keys():
                # Break if a non-blank line has the same, or lower indentation
                # level than the environment's level (``prefix``)
                if len(next_prefix.expandtabs()) <= len(prefix.expandtabs()):
                    break
                else:
                    finished = False

            # ``list_item``s generally are commented on the very next line, but
            # first ensure the next line is in fact another list_item.
            # If the next line is a continuation of the current list_item, then
            # set ``finished`` to False, and keep searching.
            # blank or not, but
            elif comment_ref.node_type == 'list_item':
                cleaned = next_line[prefix_match.end():]


                # Most list items will break on this criterion (that the next
                # line contains a list item)
                if RST_LIST_ITEMS_AS_RE.match(cleaned):
                    insert = insert + (bias - 2) + idx_next

                    # Subtract off extra lines to handle multiline items
                    if bias > 1:
                        insert -= (bias -1)
                    break

                # but the final entry in a list will break on this criterion
                elif len(next_prefix.expandtabs()) <= len(prefix.expandtabs()):
                    #insert = insert - 1  # commented out: passes bullet_11
                    break

                # It wasn't really the end of the current item (the one being
                # commented on).  It's just that this item is written over
                # multiple lines.
                else:
                    finished = False

            else:
                break

    # Lastly, list items require a bit more work to handle.  What we want:
    #
    #   |Before                          |After
    #   |--------------------------------------------------------------
    #   |#.  This is a list item         |#.  This is a list item
    #   |<no blank line originally here> |    .. ucomment:: ABCDEF: 2a,
    #   |#.  Next list item              |#.  Next list item

    if comment_ref.node_type == 'list_item':
        # list_item's need to have a different level of indentation
        # If the ``RST_source[line_num]`` is  ``____#.\tTwo.\n``, then
        # (note that _ represents a space)
        # * remainder     = '#.\tTwo.\n'  i.e. removed upfront spaces
        # * the_list_item = '#.'          i.e. what defines the list
        # * prefix        = '______\t'    i.e. what to put before '.. ucomment'
        # * list_item.group('space')='\t' i.e. the tab that appears after '#.'
        remainder = RST_source[line_num][prefix_match.end():]
        list_item = RST_LIST_ITEMS_AS_RE.match(remainder)
        the_list_item = list_item.group().rstrip(list_item.group('space'))
        prefix = prefix + ' ' * len(the_list_item) + list_item.group('space')
        c_root = wrap_return(RST_source, insert, prefix)

        # There was no spaced between the list_items
        if idx_next == 0 and finished:
            RST_source.insert(insert, '\n')

        return c_root
    else:
        return wrap_return(RST_source, insert, prefix)


def update_RST_comment_status(comment_ref, comment_node, RST_source, \
                                  search, replace):
    """
    Searches for the existing ``comment_ref`` and ``comment_node`` in the list
    of strings given by ``RST_source``.  Finds the ``search`` character and
    replaces it with the ``replace`` character (indicating whether the comment
    was approved or rejected).

    The ``RST_source`` is a list of strings; this list will be updated in place.
    """
    comment_re = re.compile(r'(\s*)\.\. ' + COMMENT_DIRECTIVE.strip(' .:') + \
                            r'::(\s*)(?P<root>\w*)(\s*):(\s*)(?P<nodes>.+)')
    idx = -1
    line = ''
    for idx, line in enumerate(RST_source[comment_ref.line_number-1:]):
        rematch = comment_re.match(line)
        if rematch:
            if rematch.group('root') == comment_ref.comment_root:
                break

    if idx < 0:
        log_file.error(('Comment (%s) was to be changed, but was not found in'
                       'the RST_sources.') % str(comment_ref))
        return RST_source

    # We have the correct node.  Now edit the code.
    nodes = rematch.group('nodes')
    nodes = re.sub(comment_node + search, comment_node + replace, nodes)
    to_replace = line[0:rematch.start('nodes')] + nodes
    RST_source[comment_ref.line_number - 1 + idx] = to_replace + '\n'
    return comment_ref.comment_root

# Emailing functions
# ------------------
def send_email(from_address, to_addresses, subject, message):
    """
    Basic function to send email according to the four required string inputs.
    Let Django send the message; it takes care of opening and closing the
    connection, as well as locking for thread safety.
    """
    if subject and message and from_address:
        try:
            send_mail(subject, message, from_address, to_addresses,
                      fail_silently=True)
        except (BadHeaderError, smtplib.SMTPException) as err:
            # This will log the error, and hopefully email the admin
            UcommentError(err, 'When sending email')
        except Exception as err:
            # Only log the error, incase we are returned back here
            log_file.error('EMAIL ERROR: ' + str(err))

        log_file.info('EMAIL: sent to: ' + ', '.join(to_addresses))

def email_poster_pending(poster, comment):
    """ Sends an email to the poster to let them know their comment is in the
    queue for approval.  Give a time-frame, and tell them the number of comments
    left before their future comments are automatically approved.
    """
    try:
        pending_template = Template(conf.once_submitted_template)
    except TemplateSyntaxError as err:
        # Log the error, but don't email the poster.
        UcommentError(err, "Error in 'once_submitted_template'.")
        return

    message = pending_template.render(settings=conf, poster=poster,
                                      comment=comment)

    if conf.once_submitted_subject:
        send_email(from_address = conf.email_from,
                   to_addresses = [poster.email],
                   subject = conf.once_submitted_subject,
                   message = message)

def email_poster_approved(poster, comment):
    """ Sends an email to the poster to let them know their comment has been
    approved.  Give a link?
    """
    try:
        approved_template = Template(conf.once_approved_template)
    except TemplateSyntaxError as err:
        # Log the error, but don't email the poster.
        UcommentError(err, "Error in 'once_approved_template'.")
        return

    message = approved_template.render(settings = conf,
                                      poster = poster,
                                      comment = comment)

    send_email(from_address = conf.email_from,
               to_addresses = [poster.email],
               subject = conf.once_approved_template,
               message = message)


def email_approval_confirmation(poster, comment, web_root):
    """
    Sends email to the ``conf.email_comment_administrators_list`` with special
    links to either approve or reject a new comment.
    """
    try:
        approval_template = Template(conf.email_for_approval)
    except TemplateSyntaxError as err:
        # Log the error, but send a bare-bones email
        UcommentError(err, "Error in 'comment-approved' template")
        approval_template = Template(('THIS IS A DEFAULT EMAIL.\n\n'
            'A new comment was received on your '
            'ucomment-enabled website.\n\nHowever an error in your settings '
            'template ("email_for_approval" template) prevented a correctly '
            'formatted email from being sent to you.  Please check your '
            'template settings carefully.\n\nThe comment was '
            'recorded in the database.\n\nClick this link to ACCEPT the '
            'comment: {{comment.approval_code}}\nTo REJECT the comment, click '
            'here: {{comment.rejection_code}}\n'))

    comment.approval_code = web_root + '_approve-or-reject/' + \
                                                        comment.approval_code
    comment.rejection_code = web_root + '_approve-or-reject/' + \
                                                        comment.rejection_code

    msg = approval_template.render(email_from = conf.email_from,
                                   poster = poster,
                                   comment = comment,
                                   reference = comment.reference,
                                   webpage = web_root + comment.page.link_name,
                                   settings = conf)

    send_email(from_address = conf.email_from,
               to_addresses = conf.email_comment_administrators_list,
               subject = conf.email_for_approval_subject + ': %s, node %s' %\
                            (comment.reference.comment_root, comment.node),
               message = msg)

def email_poster_rejected(poster, extra_info=''):
    """
    Sends the poster an email saying their comment was not suitable.  If any
    extra text is provided in ``extra_info``, add that to the email.
    """
    # TODO(KGD): add function to reject posting
    pass

def alert_system_admin(error_msg):
    """ An error occurred: more information contained in the ``error`` string.
    Send an email to the comment administrator.
    """
    msg = ('The following error was logged on your ucomment-enabled '
           'website at %s: \n\n') % (str(datetime.datetime.now()))
    msg = msg + str(error_msg)

    send_email(conf.email_from, conf.email_system_administrators,
               conf.email_system_administrators_subject, msg)



def emails_after_submission(poster, comment, request):
    """ Email the poster once the comment has been submitted to the website,
    """
    # Don't bother if no email address
    if poster.email != '':

        # The comment was auto-approved
        if comment.is_approved:
            email_poster_approved(poster, comment)

        # The comment is waiting for approval
        else:
            email_poster_pending(poster, comment)

    # Let the comment administrator know
    email_approval_confirmation(poster, comment, get_site_url(request,
                                    add_path=False, add_views_prefix=True))





# Web output functions (HTTP and XHR)
# -----------------------------------
def render_page_for_web(page, request, search_value=''):
    """
    Renders a ``page`` object to be displayed in the user's browser.

    We must supply the original ``request`` object so we can add a CSRF token.

    The optional ``search_value`` gives a string with which to pre-fill the
    search box.
    """
    try:
        toc_page = models.Page.objects.filter(is_toc=True).filter(
                                                            prev_link=None)[0]
        # This is a clumsy way of finding the link to the TOC because it
        # is an absolute link, whereas all the other links are relative
        toc_link = models.Link(link=get_site_url(request, add_path=False,
                        add_views_prefix=True) + toc_page.link_name,
                        title='Table of contents')
    except IndexError:
        # We only reach here if there is no TOC page in the DB.
        toc_page = ''
        toc_link = models.Link()

    # Build up the navigation links: e.g. "Previous|Up|Table of Contents|Next"
    try:
        nav_template = Template(conf.html_navigation_template.replace('\n',''))
    except TemplateSyntaxError as err:
        # Log the error, but don't disrupt the response to the user.
        UcommentError(err, 'Error in the page navigation template.')
        nav_template = Template('')
    nav_links = nav_template.render(prev=page.prev_link, next=page.next_link,
                                    parent=page.parent_link, home=toc_link)
    root_link = models.Link.objects.filter(link = '___TOC___')[0]
    root_link.link = toc_link.link

    page_body = ''.join(['\n<!-- django-database output starts -->\n',
                         page.body,
                         '<!-- /#django-database output ends -->\n'])

    # If user is visiting TOC, but is being referred, show where they came from:
    full_referrer = request.META.get('HTTP_REFERER', '')
    referrer_str = ''
    if full_referrer:
        # First, make sure the referrer is hosted on the same website as ours
        if full_referrer.find(request.get_host()) > 0:
            current_URL = request.build_absolute_uri()
            referrer = full_referrer.split(current_URL)
            if len(referrer) > 1:
                referrer_str = referrer[1]
            else:
                referrer_str = referrer[0]
        else:
            referrer = []
    else:
        referrer = []

    if page.is_toc and referrer:
        if page == toc_page and len(referrer) == 1:
            # Strip off the last part of ``current_URL`` and the rest is the
            # base part of the hosting website.
            idx = 0
            for idx, part in enumerate(reversed(current_URL.split('/'))):
                if part != '':
                    break
            break_off = '/'.join(current_URL.split('/')[0:-idx-1])
            referrer_str = referrer_str.lstrip(break_off)

        # We are coming from a link "Up one level"
        elif len(referrer) == 2:
            pass
        try:
            # At most one split: parts of the referrer can appear multiple time,
            # so only split once.
            before, after = page_body.split(referrer_str, 1)
        except ValueError:
            # "referrer" not in the page_body (happens when going to the TOC
            # from the "Search" page.
            pass
        else:
            breakpoint = after.find('</a>')
            prefix = after[0:breakpoint]
            suffix = after[breakpoint+4:]
            to_add = ('</a><span id="ucomment-toc-referrer">&lArr; You arrived '
                      'from here</span>')
            page_body = before + referrer_str + prefix + to_add + suffix

    # Create a page hit entry in the database
    page_hit = models.Hit(UA_string = request.META['HTTP_USER_AGENT'],
                   IP_address = get_IP_address(request),
                   page_hit = page.html_title,   # was ``page.link_name``
                   referrer = referrer_str or full_referrer)
    page_hit.save()

    # Was highlighting requested?
    highlight = request.GET.get('highlight', '')
    if highlight:
        search_value = highlight
        # Apply highlighting, using <span> elements
        with_case = request.GET.get('with_case', 'False')
        with_case = with_case.lower() == 'true'
        highlight = [word for word in highlight.split() \
                                if (word not in STOP_WORDS and len(word)>3)]

        highlight = []
        # TODO(KGD): turn highlighting off, tentatively. Note that the
        # highlighting code below can break the HTML by inserting span
        # elements, especially if the search term is likely an HTML element
        # in the ``page_body``.  Mitigated somewhat by the fact that we search
        # only for whole words.
        for word in highlight:
            if with_case:
                word_re = re.compile(r'\b(%s)\b'%word, re.U + re.L)
            else:
                word_re = re.compile(r'\b(%s)\b'%word, re.I + re.U + re.L)
            page_body = word_re.sub(
                    r'<span id="ucomment-highlight-word">\1</span>', page_body)

     # Build up the navigation links: e.g. "Previous|Up|Table of Contents|Next"
    try:
        local_toc_template = Template(conf.side_bar_local_toc_template)
    except TemplateSyntaxError as err:
        # Log the error, but don't disrupt the response to the user.
        UcommentError(err, 'Error in the local sidebar TOC template.')
        local_toc_template = Template('')

    # Modify the page's local TOC to strip out the rendundant one-and-only <li>
    # Render this local TOC to display in the sidebar.
    if page.local_toc.strip() != '':
        local_toc = page.local_toc
        keepthis = re.match('^<ul>(.*?)<li>(.*?)<ul>(?P<keepthis>.*)',local_toc,
                                                                      re.DOTALL)
        cleanup = None
        if keepthis:
            keepthis = keepthis.group('keepthis')
            cleanup = re.match('(?P<keepthis>.*?)</ul></li></ul>$',
                                                    keepthis.replace('\n',''))
        if cleanup:
            # This additional cleanup only works on document where we are
            # splitting the major sections across multiple HTML pages.
            page.local_toc = cleanup.group('keepthis')
    sidebar_local_toc = local_toc_template.render(page=page)

    # If the page is the main TOC, and user option is set, then style the <li>
    # so they can expand (uses Javascript).  Will still display the page
    # properly even if there is no Javascript.
    if page == toc_page:
        page_body = re.sub('toctree-l1', 'ucomment-toctree-l1', page_body)


    # Finally, send this all off to the template for rendering.
    page_content = {'html_title': page.html_title,
                    'body_html': page_body,
                    'nav_links': nav_links,
                    'root_link': root_link,
                    'stylesheet_link': conf.stylesheet_link,
                    'prefix_html': conf.html_prefix_text,
                    'suffix_html': conf.html_suffix_text,
                    'search_value': search_value,
                    'local_TOC': sidebar_local_toc,
                    'sidebar_html': page.sidebar,
                    'about_commenting_system': conf.html_about_commenting}
    page_content.update(csrf(request))  # Handle the search form's CSRF

    # TODO(KGD): redirect to /_search/search terms/AND/True if required

    return render_to_response('document-page.html', page_content)


def display_page(page_requested):
    """
    Displays the HTML for a page, including all necessary navigation links.

    Must also handle the case of http://example.com/page#subsection to got
    to subsection links within a page.
    """
    start_time = time.time()
    link_name = convert_web_name_to_link_name(page_requested.path)
    ip_address = get_IP_address(page_requested)
    item = models.Page.objects.filter(link_name=link_name)
    if not item:
        # Requested the master_doc (main document)
        if link_name == '':
            toc_page = models.Page.objects.filter(is_toc=True).filter(\
                                                            prev_link=None)
            if toc_page:
                resp = django_reverse('ucomment-root') + toc_page[0].link_name
                return HttpResponseRedirect(resp)
            else:
                emsg = ('A master page does not exist in the ucomment database.'
                        '<p>Have you correctly specified the settings in this '
                        'file? <pre>%sconf/settings.py</pre>'
                        '<p>Also visit <a href="%s">the administration page</a>'
                        ' to start compiling your document.' % (
                                       conf.application_path,
                                       django_reverse('ucomment-admin-signin')))
                return HttpResponse(emsg)
        elif models.Page.objects.filter(link_name=link_name + '/index'):
            # To accommodate a peculiar Sphinx settings for PickleHTMLBuilder
            # It may lead to broken links for images that are included on
            # this page.
            item = models.Page.objects.filter(link_name=link_name + '/index')
        else:
            # TODO(KGD): return a 404 page template: how to do that?
            log_file.debug('Unknown page requested "%s" from %s' % (link_name,
                                                                ip_address))
            return HttpResponse('Page not found', status=404)

    page = item[0]
    page.number_of_HTML_visits += 1
    page.save()

    result = render_page_for_web(page, page_requested)
    log_file.info('REQUEST: page = %s from IP=%s; rendered in %f secs.' % (
        link_name, ip_address, time.time()-start_time))
    return result

def format_comments_for_web(comments):
    """
    Received a list of comment objects from the database; must format these
    comments into appropriate HTML string output to be rendered in the browser.
    """
    resp = ''
    for item in comments:
        if not(item.is_approved):
            continue

        date_str = item.datetime_submitted.strftime("%Y-%m-%d at %H:%M")
        resp += '<li id="%s"><dl><dt><span id="ucomment-author">%s</span>' \
             % (item.node, item.poster.name)
        resp += (('<span class="ucomment-meta">%s</span></dt>'
                 '<dd>%s</dd></dl></li>') % (date_str, item.comment_HTML))

    resp += '\n'
    return resp
def retrieve_comment_HTML(request):
    """
    Retrieves any comments associated with a comment root and returns the
    HTML in a JSON container back to the user.

    http://www.b-list.org/weblog/2006/jul/31/django-tips-simple-ajax-example-part-1/
    """
    if request.method == 'POST':
        # If comment reading/writing is disabled: return nothing
        if not(conf.enable_comments):
            return HttpResponse('', status=200)

        root = request.POST.get('comment_root', '')
        sort_order = request.POST.get('order', 'forward')
        response = ''
        ref = models.CommentReference.objects.filter(comment_root=root)
        if len(ref):
            ref = ref[0]
            associated_comments = ref.comment_set.order_by("datetime_submitted")
            if sort_order == 'reverse':
                associated_comments = reversed(associated_comments)

            response = format_comments_for_web(associated_comments)
            log_file.info('COMMENT: Request HTML for %s from IP=%s' %\
                          (root, get_IP_address(request)))
            return HttpResponse(response, status=200)
        else:
            log_file.warn(('A user requested comment reference = %s which did '
                           'exist; this is not too serious; you have probably '
                           'just updated the document and they are accessing '
                           'a prior version.') % root)
            return HttpResponse('', status=200)


    elif request.method == 'GET':
        return HttpResponse('N/A', status=404)
    else:
        log_file.warn((request.method + ' method for comment HTML received; '
                        'not handled; return 400.'))
        return HttpResponse(status=400)



def retrieve_comment_counts(request):
    """
    Given the list of nodes, it returns a list with the number of comments
    associated with each node.
    """
    start_time = time.time()
    response_dict = {}
    if request.method == 'POST':
        try:
            comment_roots = sorted(request.POST.keys())
            comment_roots.pop(comment_roots.index('_page_name_'))
            cache_key = 'counts_for__' + convert_web_name_to_link_name(
                                           request.POST.get('_page_name_', ''))

            if not conf.enable_comments:
                return HttpResponse(simplejson.dumps(response_dict),
                                            mimetype='application/javascript')

            if cache_key in django_cache.cache:
                log_file.info('COUNTS: returned cached result.')
                response_dict = django_cache.cache.get(cache_key)
            else:

                for key in comment_roots:
                    num = 0
                    ref = models.CommentReference.objects.filter(\
                                                            comment_root=key)
                    if len(ref) > 0:
                        ref = ref[0]
                        associated_comments = ref.comment_set.all()
                        for comment in associated_comments:
                            if comment.is_approved:
                                num += 1

                    # Every key must return a result, even if it is zero
                    response_dict[key] = num

                log_file.debug('COUNTS: for %d nodes retrieved in %f secs' %\
                           (len(request.POST.keys()), time.time()-start_time))

            # Should we cache the result for future?
            if (time.time()-start_time) > conf.cache_count_duration:
                django_cache.cache.set(cache_key, response_dict,
                                       timeout=conf.cache_count_timout)
                log_file.info('COUNTS: %s will be cached for %f secs.' % \
                                    (cache_key, conf.cache_count_timout))

            return HttpResponse(simplejson.dumps(response_dict),
                                mimetype='application/javascript')
        except Exception as err:
            # only log the error, don't break the app
            UcommentError(err, 'While retrieving comment counts')
            return HttpResponse(simplejson.dumps(response_dict),
                                 mimetype='application/javascript')
    elif request.method == 'GET':
        return HttpResponse('N/A', status=404)
    else:
        log_file.info((request.method + ' method for comment counts '
                        'received; not handled; return 400.'))
        return HttpResponse(status=400)

# Publishing update functions
# ----------------------------
def publish_update_document(request):
    """
    After pages have been remotely updated and checked back in; the author
    must trigger an update.  This compiles the code to HTML for the changed
    files, created database entries for each node, regenerates the PDF output.
    """
    if not request.user.is_authenticated():
        return HttpResponseRedirect(django_reverse('ucomment-admin-signin'))

    msg = call_sphinx_to_publish()

    # An empty message, msg, indicates no problems.  Any problems that may
    # have occurred have already been emailed and logged to the admin user.
    if msg:
        return HttpResponse(msg, status=404)

    # TODO(KGD):  Convert any changed images to JPG from PNG.
    #             Compile PDF here, or even earlier.
    #             Update search index tables in Sphinx search
    msg = 'PUBLISH: Update and publish operation successfully completed'
    log_file.info(msg)
    msg += ('<br><p>View your document <a href="%s">from this link</a>'
        '.</p>') % (django_reverse('ucomment-root'))
    return HttpResponse(msg, status=200)


def call_sphinx_to_publish():
    """ Does the work of publishing the latest version of the document.

    Pulls in the latest revision from the DVCS, publishes the document.
    """
    # TODO(KGD): can we show a list of changed files to the author before
    #            s/he clicks "Publish": you will have to dig into Sphinx's
    #            internals to see that.
    revision_changeset = update_local_repo()
    log_file.info('PUBLISH: the document with revision changeset = %s' % \
                   revision_changeset)

    # Copy over the ucomment extension to the local repo: that way the author
    # does not have to include it in his/her repo of the document.
    srcdir = os.path.join(conf.application_path, 'sphinx-extensions') + os.sep
    if os.name == 'posix':
        try:
            os.symlink(srcdir + 'ucomment-extension.py',
                   conf.local_repo_physical_dir+os.sep+'ucomment-extension.py')
        except OSError as err:
            if err.errno == 17: # File already exists
                pass
            else:
                UcommentError(err, ('When creating symlink for ucomment '
                                    'extension'))

    else:
        import shutil
        try:
            shutil.copy(srcdir + 'ucomment-extension.py',
                    conf.local_repo_physical_dir)
        except shutil.Error:
            UcommentError(err, ('When copying the ucomment extension - not '
                                'found'))

    # When Sphinx is called to compile the document, it is expected that the
    # document's ``conf.py`` has the correct path to the extensions.
    from sphinx.application import Sphinx, SphinxError

    from StringIO import StringIO
    status = StringIO()
    warning = StringIO()

    # TODO(KGD): can we send this to the logfile instead of status and warning?
    #            will allow us to track compiling of large documents via logfile

    # TODO(KGD): investigate using http://ajaxpatterns.org/Periodic_Refresh
    # also see: http://www.ajaxprojects.com/ajax/tutorialdetails.php?itemid=9

    # The code below simulates the command-line call
    # $ sphinx-build -a -b pickle -d _build/doctrees . _build/pickle

    # The ``conf.local_repo_physical_dir``  must not have a trailing slash,
    # and must be "clean", otherwise lookups later with ``file_linkname_map``
    # will fail.
    conf.local_repo_physical_dir = os.path.abspath(conf.local_repo_physical_dir)
    build_dir = os.path.abspath(conf.local_repo_physical_dir+os.sep + '_build')
    ensuredir(build_dir)

    # TODO(KGD): make this setting a choice in the web before publishing
    # Note: FRESHENV: if True: we must delete all previous comment references,
    # to avoid an accumulation of references in the database.
    conf.use_freshenv = False
    try:
        app = Sphinx(srcdir=conf.local_repo_physical_dir,
                     confdir=conf.local_repo_physical_dir,
                     outdir = build_dir + os.sep + 'pickle',
                     doctreedir = build_dir + os.sep + 'doctrees',
                     buildername = 'pickle',
                     status = status,
                     warning = warning,
                     freshenv = conf.use_freshenv,
                     warningiserror = False,
                     tags = [])

        if app.builder.name != 'pickle':
            emsg = ('Please use the Sphinx "pickle" builder to compile the '
                    'RST files.')
            log_file.error(emsg)
            # TODO(KGD): return HttpResponse object still
            return

        # We also want to compile the documents using the text builder (search).
        # But rather than calling Sphinx from the start, just create a text
        # builder and run it right after the pickle builder.  Any drawbacks?
        text_builder_cls = getattr(__import__('sphinx.builders.text', None,
                                    None, ['TextBuilder']), 'TextBuilder')
        text_builder = text_builder_cls(app)
        pickle_builder = app.builder

        if 'ucomment' not in app.env.config:
            emsg = ('Please ensure the `ucomment` dictionary appears in your '
                    '``conf.py`` file.')
            log_file.error(emsg)
            # TODO(KGD): return HttpResponse object still
            return

        # Call the ``pickle`` builder
        app.env.config.ucomment['revision_changeset'] = revision_changeset
        app.env.config.ucomment['skip-cleanup'] = True
        app.build()

        # Log any warnings to the logfile.
        log_file.info('PUBLISH: Sphinx compiling HTML (pickle) successfully.')
        if warning.tell():
            warning.seek(0)
            for line in warning.readlines():
                log_file.warn('PUBLISH: ' + line)

        # Now switch to the text builder (to create the search index)
        app.env.config.ucomment['skip-cleanup'] = False
        app.builder = text_builder

        try:
            app.build()
        except SphinxError as e:
            log_file.warn(('PUBLISH: could not successfully publish the text-'
                           'based version of the document (used for searching).'
                           'Error reported = %s') % str(e))
            # TODO(KGD): defer clean-up to after RST files are used as search

        log_file.debug('PUBLISH: Sphinx compiling TEXT version successfully.')
        if warning.tell():
            warning.seek(0)
            for line in warning.readlines():
                log_file.warn('PUBLISH WARNING: ' + line.strip())

        # Switch back to the pickle builder (we need this when doing the
        # database commits)
        app.builder = pickle_builder

    except SphinxError as e:
        msg = 'A Sphinx error occurred (error type = %s): %s'  % \
            (e.category, str(e))
        log_file.error(msg)
        alert_system_admin(msg)
        return msg

    if app.statuscode == 0:
        commit_updated_document_to_database(app)
    else:
        log_file.error(('The Sphinx status code was non-zero.  Please check '
                        'lines in the log file above this one for more info.'))
    return ''


def commit_updated_document_to_database(app):
    """
    Two types of objects must be commited to the database to complete the
    publishing of the document:
        1. Each (web)pages in the document
        2. All the comment references

    We need to take some extra care with the comment references: remove unused
    comment references, find and take care of references that were orphaned
    (see below), and add new comment references.
    """
    sphinx_settings = app.env.config.ucomment

    # Used to convert ``class="reference internal"`` to
    # ``class="ucomment-internal-reference"``
    local_toc_re = re.compile(r'class="reference internal"')
    replace_toc = 'class="ucomment-internal-reference"'

    # First, generate a dictionary of page_name -> next_page_name
    # The first page = TOC = app.env.config.master_doc
    # The last page  has no next page link.
    # E.g" {'toc': 'page1', 'page2': 'page3', 'page1': 'page2', 'page3': None}
    all_files = app.env.found_docs
    document_order = {}
    for fname in list(all_files):
        is_toc = False
        if fname == app.env.config.master_doc:
            is_toc = True

        name = app.builder.outdir + os.sep + fname + app.builder.out_suffix
        try:
            f = file(name, 'r')
            page_info = pickle.load(f)
        except IOError:
            raise IOError('An IOError occurred when processing %s' % name)
        finally:
            f.close()

        # What is the page's HTML title?
        link_name = page_info['current_page_name']
        has_next = False
        for item in page_info['rellinks']:
            if item[3] == 'next':
                has_next = True
                next_section = item[0]
                break
        if not has_next:
            next_section = None

        document_order[link_name] = next_section

    # Next, order the pages:
    page_names = document_order.keys()
    ordered_names = [app.env.config.master_doc]
    for idx in xrange(len(page_names)):
        if ordered_names[idx] is not None:
            ordered_names.append(document_order[ordered_names[idx]])
    # The last ``None`` element designates the end of the document
    ordered_names.pop()
    # Check if there were docs not included in the toctree: add them at the end
    ordered_names.extend(set(page_names) - set(ordered_names))


    # Now commit each (web)page to the DB in order
    # ---------------------------------------------
    prior_pages = models.Page.objects.all()
    file_linkname_map = {}
    for fname in reversed(ordered_names):
        is_toc = is_chapter_index = False
        if fname in app.env.config.ucomment['toc_docs']:
            is_chapter_index = True
        if fname == app.env.config.master_doc:
            is_toc = True
            is_chapter_index = False

        name = app.builder.outdir + os.sep + fname + app.builder.out_suffix
        try:
            f = file(name, 'r')
            page_info = pickle.load(f)
        except IOError:
            raise IOError('An IOError occurred when processing %s' % name)
        finally:
            f.close()

        # Aim: get a text version of each page to generate a search index
        # (Later on we will trigger an index refresh using sphinxsearch.com)
        # For now, get the RST source code and store that in the database.
        # TOC and chapter indicies are not to be indexed for the search engine.

        src = app.builder.srcdir + os.sep + fname + app.config.source_suffix
        try:
            unsplit_source_name = sphinx_settings['split_sources'][src]
        except KeyError:
            unsplit_source_name = src

        if is_toc or is_chapter_index:
            # Good side-effect: TOC pages will never show up in search results
            search_text = ''
        else:
            try:
                f = file(src, 'r')
                search_text = ''.join(f.readlines())
            except IOError:
                raise IOError(('An IOError occurred when processing RST '
                               'source: %s' % src))
            finally:
                f.close()

        # By what name will the HTML page be accessed?
        link_name = page_info['current_page_name']

        # Now get some link information to add to the page.  Not every
        # page has a parent; for those pages, set the parent to be the TOC.
        # The parent link for the TOC is the TOC
        try:
            parent_link, _ = models.Link.objects.get_or_create(
                link = page_info['parents'][0]['link'],
                title = page_info['parents'][0]['title'])
        except IndexError:
            # The highest level TOC does not have a parent: this is used
            # to correctly output the navigation bar.
            if is_toc:
                parent_link = None
            else:
                parent_link, _ = models.Link.objects.get_or_create(
                    link = u'../',
                    title = u'')

        try:
            next_link, _ = models.Link.objects.get_or_create(
                link = page_info['next']['link'],
                title = page_info['next']['title'])
        except TypeError:
            # Only the last section in the document won't have a next link
            next_link = None

        try:
            prev_link, _ = models.Link.objects.get_or_create(
                link = page_info['prev']['link'],
                title = page_info['prev']['title'])
        except TypeError:
            # Only the TOC won't have a previous link.  We rely on this fact to
            # filter the pages to locate the TOC.
            prev_link = None

            # While we are here, create a "root link" with the appropriate
            # title: use the ``project`` setting from the Sphinx conf.py file.
            # The actual link will be determined on page request.
            models.Link.objects.get_or_create(link = '___TOC___',
                                              title = app.env.config.project)

        # Generate a "local" table of contents: useful for long pages; will not
        # be generated if there is only one subsection on the page, nor will
        # it be generated for pages that are primarily an index page.
        if is_toc or is_chapter_index:
            # Good side-effect: TOC pages will never show up in search results
            local_toc = ''
        else:
            local_toc = page_info['toc']
            local_toc, number = local_toc_re.subn(replace_toc, local_toc)
            if number == 1:
                local_toc = ''

            # TODO(KGD): take a look at the ``app.env.resolve_toctree`` function
            #            in Sphinx.

        # Use the Project's name for the master_doc (i.e. the main TOC page)
        # for the document.
        if is_toc and not(is_chapter_index):
            page_info['title'] = app.env.config.project

        # If a page with the same link (an unique field) is found, then update
        # the page.  Do not delete the page, because that will remove any
        # associated comments.  See the ``models.py`` file for ``Comment``
        # definition -- the ``Page`` objects are a ForeignKey.

        existing_page = prior_pages.filter(link_name=link_name)
        if existing_page:
            page = existing_page[0]
            page.revision_changeset = sphinx_settings['revision_changeset']
            page.html_title = page_info['title']
            page.is_toc = is_toc or is_chapter_index
            page.source_name = unsplit_source_name
            page.updated_on = datetime.datetime.now()
            page.PDF_file_name = 'STILL_TO_COME.pdf'
            page.body = '\n' + page_info['body'] + '\n'
            page.search_text = search_text
            page.parent_link = parent_link
            page.next_link = next_link
            page.prev_link = prev_link
            page.local_toc = local_toc
            page.save()
        else:
            defaults = {'revision_changeset': \
                                        sphinx_settings['revision_changeset'],
                        'link_name': link_name,
                        'html_title': page_info['title'],
                        'is_toc': is_toc or is_chapter_index,
                        'source_name': unsplit_source_name,
                        'PDF_file_name': 'STILL_TO_COME.pdf',
                        'number_of_HTML_visits': 0,
                        'body': '\n' + page_info['body'] + '\n',
                        'search_text': search_text,
                        'parent_link': parent_link,
                        'next_link': next_link,
                        'prev_link': prev_link,
                        'local_toc': local_toc,}
            created = models.Page.objects.create(**defaults)

        file_linkname_map[app.srcdir + os.sep + fname + \
                                     app.env.config.source_suffix] = link_name

    log_file.info('PUBLISH: pages saved to the database.')

    # Next, deal with the comment references
    # ---------------------------------------------
    to_update = []
    to_remove = []
    orphans = []
    prior_references = models.CommentReference.objects.all()

    # Only if we used a fresh environment.  Because then all the comment
    # references are regenerated.
    if conf.use_freshenv:
        for item in prior_references:
            orphans.append(item.comment_root)

    for item in sphinx_settings['comment_refs']:
        # First check whether this comment reference exists in the database;
        # If not, add it.  If it does exist, add it to the list of references
        # to update next.
        defaults={'revision_changeset': sphinx_settings['revision_changeset'],
                  'file_name': item.source,
                  'page_link_name': file_linkname_map[item.link_name],
                  'node_type': item.node,
                  'line_number': item.line,
                  'comment_root': item.root,
                  'comment_root_is_used': False}
        ref, created = models.CommentReference.objects.get_or_create(
            comment_root=item.root,  # comment_root is a unique field
            defaults=defaults)
        if not created:
            try:
                orphans.remove(item.root)
            except ValueError:
                pass
            to_update.append(item)

    # Update the references that already exist in the DB.  In most cases these
    # references are used as ForeignKeys in ``Comment`` objects.
    # The (very unusual) case when they don't exist in the DB is when the RST
    # repo is processed the first time and there happen to be ucomment
    # directives in the RST source.  In this case we would have created a
    # comment reference in the code above (using ``get_or_create()``)

    for item in to_update:
        ref = prior_references.filter(comment_root=item.root)[0]
        ref.revision_changeset = sphinx_settings['revision_changeset']
        ref.file_name = item.source
        ref.node_type = item.node
        ref.line_number = item.line
        ref.date_added = datetime.datetime.now()
        ref.save()
        # The above code is quite useful: if the author ever happens to move the
        # ucomment directives around, even to a different file, the comments
        # associated with that reference will still appear at the new location.

    # Orphans occur if the user removed the ucomment directive from the RST
    # source.
    # They are problematic only if they happen to have an associated ``Comment``
    # object in the database (which is expected, since a CommentReference is
    # created the same time ).
    for item in orphans[:]:
        # Remove comment references from the list that don't have comments.
        ref = prior_references.filter(comment_root=item)[0]
        if ref.comment_set.exists() == False:
            orphans.remove(item)
            to_remove.append(item)

    # It is safe to remove these references, because they do not have any
    # comments associated with them (CommentReference objects only appear as
    # ForeignKeys in ``Comment`` objects.
    for remove_root in to_remove:
        to_remove = prior_references.filter(comment_root=remove_root)
        if to_remove:
            to_remove[0].delete()

    for orphan_id in orphans:
        # These arise when comment references are removed from the text by the
        # author.  But, these references still have comments associated with
        # them in the database, but are not made available on any page,
        # nor do they have a valid comment reference.

        orphan = prior_references.filter(comment_root = orphan_id)[0]

        # Create an unreachable page (starts with '_')
        defaults = {'revision_changeset': sphinx_settings['revision_changeset'],
                    'link_name': '_orphans_',
                    'html_title': '_orphans_',
                    'is_toc': False,
                    'source_name': '_orphans_',
                    'PDF_file_name': '_orphans_',
                    'number_of_HTML_visits': 0,
                    'body': '_orphans_',
                    'search_text': '',
                    'parent_link': None,
                    'next_link': None,
                    'prev_link': None,
                    'local_toc': '',}
        orphan_page, created = models.Page.objects.get_or_create(
                                                        link_name='_orphans_',
                                                        defaults=defaults)
        # Create an comment reference that would not normally be created
        defaults = {'revision_changeset': '-1',
                    'file_name': '_orphans_',
                    'node_type': '_orphan_',
                    'line_number': 0,
                    'comment_root': '_ORFN_',
                    'comment_root_is_used': True}
        orphan_ref, created = models.CommentReference.objects.get_or_create(
                                                        comment_root='_ORFN_',
                                                        defaults=defaults)

        # Try to de-orphan any comments on subsequent republishing (author may
        # have realized the mistake and brought the node back).
        if orphan_id == '_ORFN_':

            # It's a little hard to go back from the orphaned comment to find
            # its original reference.  But we will use the fact the re-created
            # reference's comment_root will be the same as the orphaned
            # comment's parent (or at least the first ``conf.root_node_length``
            # characters of the parent).
            for comment in orphan.comment_set.all():
                former_parent = comment.parent[0:conf.root_node_length]
                new_parent = prior_references.filter(comment_root=former_parent)
                if len(new_parent):
                    comment.reference = new_parent[0]

                    # Now find the page on which that comment reference is used
                    all_pages = models.Page.objects.filter(
                                        link_name=new_parent[0].page_link_name)
                    if len(all_pages):
                        comment.page = all_pages[0]

                    comment.save()

                    log_file.warn(('PUBLISH: re-parented the orphan comment '
                                   'reference %s; now appears on page "%s".')%\
                                    (comment.reference.comment_root,
                                     new_parent[0].page_link_name))

        n_orphans = 0
        for comment in orphan.comment_set.all():
            comment.reference = orphan_ref
            comment.page = orphan_page
            comment.save()
            n_orphans += 1

            log_file.warn(('PUBLISH: dealt with comment reference orphan: %s; '
                           'was orphaned between revision %s (last known use) '
                           'and revision %s (current).  Has %d associated '
                           'comments.') % (orphan_id, orphan.revision_changeset,
                           sphinx_settings['revision_changeset'], n_orphans))

# Dumping and loading fixtures
# ----------------------------
def dump_relevent_fixtures(request):
    """
    Dumps certain model types to fixture files.
    """
    if not request.user.is_authenticated():
        return HttpResponseRedirect(django_reverse('ucomment-admin-signin'))

    style = 'xml'
    from django.core import serializers
    fixtures = (    (models.Comment, 'Comment.'+style),
                    (models.CommentReference, 'CommentReference.'+style),
                    (models.CommentPoster, 'CommentPoster.'+style),
                    (models.Hit, 'Hit.'+style),
                )
    log_file.debug('FIXTURES: About to dump fixtures to file.')
    for model, filename in fixtures:
        data = serializers.serialize(style, model.objects.all(), indent=2,
                                     use_natural_keys = True)

        try:
            ensuredir(conf.django_fixtures_dir)
            full_filename = os.path.join(conf.django_fixtures_dir, filename)
            f = file(full_filename, 'w')
            try:
                f.write(data)
            finally:
                f.close()
            log_file.info('FIXTURES: Dumped %s objects to %s' %\
                           (model, full_filename))
        except IOError:
            return HttpResponse(('An IOError occurred while writing %s '
                                 'objects to the fixture file: %s' % \
                                 (model, filename)), status=200)

    return HttpResponse(('All fixtures successfully saved to %s.' % \
                         conf.django_fixtures_dir), status=200)

def load_from_fixtures(request):
    pass
    #TODO(KGD): still to come

# Searching the document text
# ---------------------------
def format_search_pages_for_web(pages, context, with_case):
    """
    Receives a dictionary.  The keys are ``Page`` objects, and the corresponding
    values are the list of words that appear on that page.

    Will format these into appropriate HTML string output that is sent to the
    user.

    Uses ``context`` number of characters around the search word to display
    in the results.

    The ``with_case`` input will either ``True`` (indicating case-sensitive
    search was requested), or ``False``.
    """
    def common_span(spanA, spanB):
        """
        Takes two tuples (containing 2 integers) and returns the largest region
        spanned, provided they overlap.  If no overlap, then return two spans
        exactly as they were received.

        Can be improved later on to avoid really large spans by taking
        some sort of compromised span.
        """
        # First sort them
        swapped = False
        if spanA[0] > spanB[0]:
            spanA, spanB = spanB, spanA
            swapped = True
        # If they overlap, return the intersection of the spans
        if spanA[1] > spanB[0]:
            return ((spanA[0], max(spanA[1], spanB[1])), )
        elif swapped:
            return (spanB, spanA)
        else:
            return (spanA, spanB)

    def clean_search_output_for_web(text):
        """
        Returns a cleaned version of ``text`` suitable for display in a browser.
        * Removes newline markers
        * Converts the string to web-safe output
        """
        text = re.sub('\n', ' ', text)
        #text = html.strip_tags(text)
        text = django_html.escape(text)
        # replace('&', '&amp;')
        #.replace('<', '&lt;')
        #.replace('>', '&gt;')
        #.replace('"', '&quot;')
        #.replace("'", '&#39;'))
        return text


    results = defaultdict(list)
    page_counts = {}
    n_pages = 0
    for page, search_words in pages.iteritems():
        # For each word, find the first N (use N=3) appearances in the text.
        # Get the context to the left and right of the word, store the ranges
        # in a list.
        page_text = page.search_text
        maxlen = len(page_text)
        N_instances = 3
        all_spans = []
        page_counts[page] = 0
        for word in search_words:
            # Find these words, ensuring they are whole words only, where the
            # definition is locale (re.L) and unicode (re.U) dependent.
            if with_case:
                word_iter = re.finditer(r'\b' + word + r'\b', page_text,
                                        re.L + re.U)
            else:
                word_iter = re.finditer(r'\b' + word + r'\b' , page_text,
                                        re.I + re.L + re.U)
            for idx, reobj in enumerate(word_iter):
                if idx >= N_instances:
                    # How many entries were there ?
                    page_counts[page] += len(list(word_iter)) + 1
                    break
                span = reobj.span()
                span = (max(0, span[0]-context), min(maxlen, span[1]+context))
                all_spans.append(span)
                page_counts[page] += 1

        # We don't always find the text (i.e. a false result) when using sqlite
        # databases and requesting a case-sensitive search. Just skip over these
        # pages.
        if len(all_spans) == 0:
            continue

        # Now combine all the ranges together, consolidating overlapping regions
        final_spans = {all_spans[0]: None}  # Use a dict to ensure unique spans
        for span in all_spans[1:]:
            keys = final_spans.keys()
            for key in keys:
                overlap = common_span(key, span)
                if len(overlap) == 1:
                    del final_spans[key]
                    final_spans[overlap[0]] = None
                else:
                    final_spans[overlap[1]] = None

        # Extract the text within the range
        display = ''
        startend = '...'
        for span in sorted(final_spans.keys()):
            display += startend + page_text[span[0]:span[1]]
        display += startend

        # Clean-up the text for web rendering
        display = clean_search_output_for_web(display)

        # Finally, highlight the search terms inside ``<span>`` brackets
        for word in search_words:
            if with_case:
                word_re = re.compile(r'(%s)'%word)
            else:
                word_re = re.compile(r'(%s)'%word, re.I)
            display = word_re.sub(\
                          r'<span id="ucomment-search-term">\1</span>', display)


        results[page].append('<li><a href="%s">%s</a>' % (\
                            django_reverse('ucomment-root') + page.link_name +\
                            '?highlight=' + ' '.join(search_words) + \
                            '&with_case=' + str(with_case), page.html_title))
        if page_counts[page] > 1:
            results[page].append(('<span id="ucomment-search-count">'
                                '[%d hits]</span>') % page_counts[page])
        else:
            results[page].append(('<span id="ucomment-search-count">'
                                '[%d hit]</span>') % page_counts[page])
        results[page].append('<div id="ucomment-search-result-context">')
        results[page].append('%s</div></li>' % display)
        n_pages += 1

    resp = ['<div id=ucomment-search-results>\n<h2>Search results</h2>']
    if n_pages == 0:
        resp.append('<p>There were no pages matching your query.</p></div>')
        return ''.join(resp)
    elif n_pages == 1:
        resp.append(('Found 1 page matching your search query.'))
    else:
        resp.append(('Found %d pages matching your search query.')%len(pages))

    # How to sort by relevance: crude metric is to sort the pages in order
    # of number of counts from high to low.
    out = sorted(zip(page_counts.values(), page_counts.keys()), reverse=True)
    entries = []
    for item in out:
        # access the dictionary by ``page`` and get the contextual output string
        entries.append('\n'.join(results[item[1]]))

    resp.append('\n\t<ul>\n' + '\t\t\n'.join(entries) + '\t</ul>\n</div>')
    return ''.join(resp)

def search_document(request, search_terms='', search_type='AND',
                       with_case=False):
    """ Will search the document for words within the string ``search_terms``.

    The results will be returned as hyperlinks containing ``CONTEXT`` number of
    characters around the search terms.

    By default and "OR"-based search is performed, so that pages containing
    one or more of the search terms will be returned.  The other alternative is
    to use ``search_type`` as "AND", requiring that all search terms must
    appear on the page.

    By default the search is case-insensitive (``with_case`` is False).
    """
    CONTEXT = 90
    if request.method == 'GET':
        search = str(search_terms)
        search_type = str(search_type).strip('/').upper()
        if search_type == '':
            search_type = 'AND'
        with_case = str(with_case).strip('/').lower()=='true'
        if with_case == '':
            with_case = False

    elif request.method == 'POST':
        # This seemingly messy code redirects back to a GET request so that
        # the user can see how the search URL is formed.  Search can be done
        # from the URL: e.g. ``_search/python guido/AND/case=False`` at the end
        # of the URL will search for "python" AND "guido" ignoring case.
        search = request.POST['search_terms']
        search_type = str(request.POST.get('search_type', search_type)).upper()
        with_case = str(request.POST.get('with_case',
                                                   with_case)).lower()=='true'
        return HttpResponseRedirect(\
                    django_reverse('ucomment-search-document') + \
                    search +'/'+ search_type +'/'+ 'case=' + str(with_case))

    start_time = time.time()
    search_for = search.split()

    results = defaultdict(list)
    n_search_words = 0
    for word in search_for:
        # Filter out certain stop words
        if word not in STOP_WORDS:
            if with_case:
                pages = models.Page.objects.filter(search_text__icontains=word)
            else:
                pages = models.Page.objects.filter(
                                           search_text__icontains=word.lower())
            n_search_words += 1
            for page in pages:
                results[page].append(word)

    # If it's an "or" search then we simply display all pages that appear as
    # keys in ``results``.  For an "AND" search, we only display pages that
    # have ``n_search_words`` entries in the corresponding dictionary value.
    if search_type == 'AND':
        out = {}
        for page, found_words in results.iteritems():
            if len(found_words) == n_search_words:
                out[page] = found_words
        results = out

    web_output = format_search_pages_for_web(results, CONTEXT, with_case)

    # Create a psuedo-"Page" object containing the search results and return
    # that to the user.  It is infact a named tuple, which has the same
    # behaviour as a ``Page`` object
    page = namedtuple('Page', ('revision_changeset next_link prev_link sidebar '
                      'parent_link html_title body local_toc link_name is_toc'))
    search_output = page(revision_changeset='',
                         next_link = None,
                         prev_link = None,
                         parent_link = models.Link(),
                         html_title = 'Search results',
                         body = web_output,
                         local_toc = '',
                         is_toc = True, # prevents sidebar
                         sidebar = '',  # but still set it to empty
                         link_name = request.path.lstrip(\
                                       django_reverse('ucomment-root')[0:-1]))

    log_file.info('SEARCH: "%s" :: took %f secs' % (search,
                                                     time.time() - start_time))
    return render_page_for_web(search_output, request, search)

def admin_signin(request):
    """
    Perform administrator/author features for the application.

    * (Re)publish the document to the web
    * Dump all fixtures to disk - for backup purposes.
    """
    if request.user.is_authenticated():
        msg = ('<ul>'
               '<li><a href="%s">The Django admin page for your site</a>'
               '<li><a href="%s">Publish or update the document</a>'
               '<li>Backup your application by <a href="%s">dumping objects '
               'to fixtures</a>') % \
               (django_reverse('admin:index'),
                django_reverse('ucomment-publish-update-document'),
                django_reverse('ucomment-dump-fixtures'))
        return HttpResponse(msg, status=200)
    elif request.method == 'GET':
        log_file.info('Entering the admin section; IP = %s' % \
                                                (get_IP_address(request)))
        context = {}
        context.update(csrf(request))
        msg = ( '<p>Please sign-in first with your Django (admin) credentials:'
                r'<form action="%s" method="POST">{%% csrf_token %%}'
                '<label for="username">Username:</label>'
                '    <input type="text" name="username" /><br />'
                '<label for="password">Password:</label>'
                '    <input type="password" name="password" />'
                '<input type="submit" value="Log in"></form>') % (request.path)
        resp = template.Template(msg)
        html_body = resp.render(template.Context(context))
        return HttpResponse(html_body, status=200)

    elif request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        user = django_auth.authenticate(username=username, password=password)
        if user is not None and user.is_active:
            django_auth.login(request, user)
            return HttpResponseRedirect(request.path)
        else:
            # TODO(KGD): respond that user does not exist, or that password
            #            is incorrect;  redirect to log in page again.
            return HttpResponseRedirect(request.path)
