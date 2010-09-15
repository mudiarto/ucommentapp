from django.contrib import admin
from conf import settings as conf
models = getattr(__import__(conf.app_dirname, None, None, ['models']),'models')

class CommentPosterAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'number_of_approved_comments',
                    'auto_approve_comments', 'opted_in')

class CommentReferenceAdmin(admin.ModelAdmin):
    list_per_page = 2000
    list_display = ('comment_root', 'comment_root_is_used',
                    'revision_changeset', 'node_type',  'line_number',)
    search_fields = ('comment_root', 'revision_changeset')
    list_filter = ('revision_changeset', 'comment_root', )
    exclude = ('revision_changeset', 'node_type',)

class CommentAdmin(admin.ModelAdmin):
    list_per_page = 2000
    list_display = ('parent', 'node', 'datetime_submitted', 'is_approved',
                    'is_rejected', 'poster', 'reference', 'short_comment')
    search_fields = ('parent', 'node', 'comment_RST',)
    list_filter = ('parent', 'node', )
    # The RST sources must also be changed when these are changed, so we can't
    # allow changing these fields from the admin interface.
    exclude = ('is_approved', 'is_rejected',)

class HitAdmin(admin.ModelAdmin):
    list_per_page = 2000
    list_display = ('page_hit', 'date_and_time', 'IP_address', 'referrer',)
    list_filter = ('IP_address', 'page_hit', )

class PageAdmin(admin.ModelAdmin):
    list_per_page = 2000
    list_display = ('link_name', 'number_of_HTML_visits', 'is_toc',
                    'html_title',)

admin.site.register(models.CommentPoster, CommentPosterAdmin)
admin.site.register(models.Link)
admin.site.register(models.Page, PageAdmin)
admin.site.register(models.Hit, HitAdmin)
admin.site.register(models.Tag)
admin.site.register(models.CommentReference, CommentReferenceAdmin)
admin.site.register(models.Comment, CommentAdmin)
