urlpatterns += patterns('',

    # Include URLs from the ucommentapp Django application.
    #
    # These URLS will be mounted on your webserver under the
    # ``document/`` sub-URL; but rename this, if required.
    #
    # If you rename ``document`` to something else, you must
    # make two other changes.
    #
    # 1. Edit the ``url_views_prefix`` setting in the 
    #    ``ucommentapp/conf/settings.py`` file to be the same.
    # 2. Edit the ``URL_VIEWS_PREFIX`` setting in the 
    #    ``ucommentapp/media/ucomment.js`` file to match.
    #
    # In this example, you would set both setting to be
    # ``document``.
    #
    (r'^document/', include('ucommentapp.urls')),
)
