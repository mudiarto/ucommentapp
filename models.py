"""
    :copyright: Copyright 2010, by Kevin Dunn
    :license: BSD, see LICENSE file for details.
"""
from django.db import models
from django.conf import settings
from django.utils import text
from conf import settings as conf
from django.contrib import admin

class CommentPosterManager(models.Manager):
    def get_by_natural_key(self, name, email):
        return self.get(first_name=name, last_name=email)

class CommentPoster(models.Model):
    """ Defines a person who has made one or more posts to the site """
    # Includes the IP numbers and UA of the user; used to ID anonymous users
    objects = CommentPosterManager()
    long_name = models.CharField(max_length=250)
    # The user's full name
    name = models.CharField(max_length=250)
    # Will not create a new user with the same email address as long as they
    # provide a ``name``.  Cannot be a unique field, because we allow comments
    # from anonymous users.
    email = models.EmailField(blank=True)
    number_of_approved_comments = models.PositiveIntegerField(default=0)
    avatar_link = models.CharField(max_length=250, blank=True, null=True)
    auto_approve_comments = models.BooleanField()
    opted_in = models.BooleanField()  # has allowed for more info to be sent to them

    def __unicode__(self):
        return u'[%s], [auto? %s], [opt? %s]: %s, %s,' % \
          (str(self.number_of_approved_comments), self.auto_approve_comments,
           self.opted_in, self.long_name, self.email)

    def natural_key(self):
        """ Used for exporting to fixtures."""
        return (self.name, self.email)

    class Meta:
        unique_together = (('name', 'email'),)

class Link(models.Model):
    """
    A generic HTML link; could be absolute or relative.
    """
    # The string version of the link (absolute or relative); usually relative.
    link = models.CharField(max_length=250)
    # The title for this link; used to create the alt=... part of the link
    title =  models.CharField(max_length=250, blank=True)
    def __unicode__(self):
        return u'%s for link=%s' % \
          (self.link, self.title)

class PageManager(models.Manager):
    def get_by_natural_key(self, link_name):
        return self.get(link_name=link_name)

class Page(models.Model):
    """
    Defines a single webpage for every section of the document.  Usually each
    chapter is on a webpage, but we often split long chapters up into sections,
    in which case each section of that chapter is also considered a page.

    The next and previous links are for the user's convenience.  Clicking these
    repeatedly should take the user sequentially through the entire document.
    """
    objects = PageManager()
    # Mercurial changeset from which the HTML was generated
    revision_changeset = models.CharField(max_length=50)
    # HTML link to the page.  For example: http://example.com/link_name/here
    # would have ``link_name`` of "link_name/here"
    link_name = models.CharField(max_length=255, unique=True)
    # Name of the page (used to show in the title field on the HTML header)
    html_title = models.CharField(max_length=500, null=True, blank=True)
    # Is this page the table of contents, or a TOC for a subsection of the doc?
    is_toc = models.BooleanField(default=False)
    # base RST file that created the HTML
    source_name = models.CharField(max_length=250)
    # For information only
    updated_on = models.DateTimeField(auto_now=False)
    # So that we can add it to the HTML (not used at the moment)
    PDF_file_name = models.CharField(max_length=250)
    # Number of page retrievals
    number_of_HTML_visits = models.PositiveIntegerField(default=0)
    # The HTML served to the user
    body = models.TextField()
    # Cleaner equivalent of the HTML (used for Sphinx Search)
    search_text = models.TextField()
    # Links related to this page
    parent_link = models.ForeignKey('Link', related_name='parent', blank=True,
                                    null=True,)
    # Either of these could be empty, but they usually are not
    next_link = models.ForeignKey('Link', blank=True, null=True,
                                  related_name='next')
    prev_link = models.ForeignKey('Link', blank=True, null=True,
                                  related_name='prev')
    # Local TOC: HTML that represents a small TOC for the current page, showing
    # the major sections/subsections, with hyperlinks to them.
    local_toc = models.TextField(null=True, blank=True)

    # Custom side-bar material
    sidebar = models.TextField()

    def __unicode__(self):
        return u'%s [%i visits]' %\
               (self.link_name, self.number_of_HTML_visits)

    def natural_key(self):
        """ Used for exporting to fixtures."""
        return (self.link_name,)

    class Meta:
        unique_together = (('link_name', ),)

class Hit(models.Model):
    """
    Tracks page hits
    """
    UA_string = models.CharField(max_length=500) # user agent of browser
    IP_address = models.IPAddressField()
    date_and_time = models.DateTimeField(auto_now=True)
    page_hit = models.TextField(max_length=500) # rather text than a ForeignKey
    referrer = models.TextField(max_length=500)

    def __unicode__(self):
        return u'%s: from IP=%s visited <<%s>> [refer: %s]' % \
                    (str(self.date_and_time)[0:19], self.IP_address,
                     self.page_hit, self.referrer)

class Tag(models.Model):
    """
    A tag object: each node in the document can be tagged.  All tags must have
    a unique name.
    # TODO(KGD): add this in later.
    """
    name = models.SlugField(unique=True)
    description = models.CharField(max_length=500)

class CommentReferenceManager(models.Manager):
    def get_by_natural_key(self, comment_root):
        return self.get(comment_root=comment_root)

class CommentReference(models.Model):
    """
    A comment reference allows us to track the comment's history over multiple
    commits of the document.  It is also what handles the frequency difference
    between comments (commited much faster) and document updates (less changes).

    For example: a user might load a webpage, commenting on a certain paragraph.
    In the mean time, the author commits a new version of the page, which
    changes the paragraph the user is commenting on.  If the user submits the
    comment, there is a risk the comment will attach to the wrong paragraph.

    Comment references allow the comment to be successfully made to the correct
    paragraph, since we can always retrieve the state of the document at the
    time the user made the comment (we checkout an earlier revision_changeset),
    rather than the most up to date changeset.

    When the RST file is compiled to HTML, every single node in every page has
    a comment reference generated for it.  Obviously most comment references
    will be unused by the time the next commit is made by the author and the
    RST file compiled to HTML.  So they can be periodically removed (e.g once
    per year; which should lead to minimal breakage of the page functionality).
    """
    # Mercurial changeset from which the HTML was generated
    revision_changeset = models.CharField(max_length=50)
    # Full file name of the RST file from which the HTML was generated
    file_name = models.CharField(max_length=250)
    # ``link_name`` of the Page on which this reference appears.  We could
    # consider making it a ForeignKey later on.
    page_link_name = models.CharField(max_length=500)
    # The docutils node type that generated the comment
    node_type = models.CharField(max_length=250)
    # The line number at the time the comment was made.  Note that this will
    # always be accurate for the given ``file_name`` from the given
    # ``revision_changeset``
    line_number = models.PositiveIntegerField()  # Can it be zero?  Yes!
    # The date/time the RST file was successfully compiled (for info only)
    date_added = models.DateTimeField(auto_now=True)
    # The comment root
    comment_root = models.CharField(max_length=conf.root_node_length,
                                    unique=True)
    # Most comment references are never used, but if they are used in a file,
    # then they can never be reassigned.
    comment_root_is_used = models.BooleanField()

    def __unicode__(self):
        return u'%s[%s]: %s; %s; %s in %s' % (self.comment_root,
                                        str(self.comment_root_is_used==True),
                                        self.revision_changeset,
                                        self.node_type,
                                        str(self.line_number),
                                        self.file_name[-80:])

    def natural_key(self):
        """ Used for exporting to fixtures."""
        return (self.comment_root, )

    class Meta:
        unique_together = (('comment_root', ),)

class Comment(models.Model):
    """ Defines a single comment"""
    # Page on which the comment appears/appeared: do we require this?
    # It makes it harder to restore from fixture.
    page = models.ForeignKey(Page)
    # Who made the comment; how many comments have they posted?
    poster = models.ForeignKey(CommentPoster)
    # Reference to the line, revision, node and page where the comment was made
    reference = models.ForeignKey(CommentReference)
    # A short name, used in the RST files to indicate this comment
    node = models.CharField(max_length=conf.short_node_length)
    # Allows threaded comments; the first comment in a thread always has
    # its parent = comment_root; other comments are ``comment_root:node``
    thread_id_length = conf.root_node_length + conf.short_node_length + 1
    parent = models.CharField(max_length=thread_id_length)
    UA_string = models.CharField(max_length=500) # user agent string of browser
    IP_address = models.IPAddressField() # user's IP address
    datetime_submitted = models.DateTimeField(auto_now=True)
    datetime_approved = models.DateTimeField(auto_now=True)
    # Used by the comment admin to approve or reject comments
    approval_code = models.CharField(max_length=250)
    rejection_code = models.CharField(max_length=250)
    comment_HTML = models.TextField() # the generated HTML version of comment
    comment_RST = models.TextField() # raw text the user typed in on website

    # Comment's status               is_approved    is_rejected    symbol in RST
    # --------------------------------------------------------------------------
    # Submitted, not yet approved:   False          False          '*'
    # Submitted and approved:        True           False          ''
    # Comment was rejected:          False          True           '#*'
    # Was approved, but now removed: True           True           '#'
    is_approved = models.BooleanField()
    is_rejected = models.BooleanField()  # Given by symbol '#'
    comment_used = models.BooleanField()  # Future: True if comment is "used"

    class Meta:
        ordering = ("-datetime_submitted",)

    def short_comment(self):
        return text.truncate_words(self.comment_RST, 100)

    def __unicode__(self):
        return u'%s:%s, (Appvd: %s): %s' % (self.reference.comment_root,
                                         self.node,
                                         self.is_approved,
                                         self.short_comment())
