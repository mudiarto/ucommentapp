"""
Maps web URLS to functions in the ``views.py`` file.
"""
from django.conf import settings
from django.conf.urls.defaults import patterns, url
from ucommentapp import views

urlpatterns = patterns('',

    # Match any page with valid URL characters (including underscores),
    # as long as the page name does not start with an underscore.
    url(r'^[^_]{1}[\w"$-_.+!*(),\']*?/$', views.display_page,
                                                  name='ucomment-display-page'),
    url(r'^$', views.display_page, name='ucomment-display-page-root'),

    # --------------------------------------------------------------------------
    # NOTE: all other URL's that start with underscores perform functions
    #       that are not normally accessed directly by the user.
    # --------------------------------------------------------------------------

    # User initiated via the search box (more common): using a "POST" query
    url(r'^_search/$', views.search_document, name='ucomment-search-document'),
    # User initiated via the URL (not expected to be used): using a "GET" query
    url(r'^_search/(?P<search_terms>.*?)(?P<search_type>/+.*?){0,1}(?P<with_case>/+case=.*?){0,1}$',
     views.search_document, name='ucomment-search-document-GET'),

    # XHR path to the server: Javascript uses this to preview user's comment
    # before allowing it to be submitted.
    url(r'^_preview-comment/$', views.preview_comment, name='ucomment-preview-comment'),

    # Javascript uses this to submit user's comment; XHR response back with the
    # confirmation code.
    url(r'^_submit-comment/$', views.submit_and_store_comment, name='ucomment-submit-store-comment'),

    # XHR (Javascript): to return number of comments associated with each node
    url(r'^_retrieve-comment-counts/$', views.retrieve_comment_counts, name='ucomment-comment-counts'),

    # XHR (Javascript): to return the comment's HTML for a given comment root
    url(r'^_retrieve-comments/$', views.retrieve_comment_HTML, name='ucomment-retrieve-comment-HTML'),

    # Comment admin uses this to approve/disapprove a pending comment.
    url(r'^_approve-or-reject/(?P<code>\w*)$', views.approve_reject_comment, name='ucomment-approve-reject'),

    # --------------------------------------------------------------------------
    # NOTE: these functions require an admin login before they can be completed
    # --------------------------------------------------------------------------

    # Login to the author/admin section of the application
    url(r'^_admin/$', views.admin_signin, name='ucomment-admin-signin'),

    # Author uses this to publish a new version to the web
    url(r'^_publish-update-document/$', views.publish_update_document, name='ucomment-publish-update-document'),

    # Dump fixtures to file for backups
    url(r'^_dump_fixtures/$', views.dump_relevent_fixtures, name='ucomment-dump-fixtures'),
)

if settings.DEBUG:

    urlpatterns += patterns('',
        # For example, files under _images/file.jpg will be retrieved from
        # settings.MEDIA_ROOT/file.jpg
        (r'^_images/(?P<path>.*)$', 'django.views.static.serve',
         {'document_root': views.conf.MEDIA_ROOT, 'show_indexes': True}),
        )
