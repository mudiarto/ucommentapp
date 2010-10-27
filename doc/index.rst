What does this application do?
==============================

The value of a document published to the web can benefit tremendously from
interaction with its readers. Their help with correcting typos, improving
clarity, or enhancing the document with their experiences and notes is helpful
for other readers, and the original author(s).

|ucomment| is a Django application that allows for web-based commenting on a
document. Unlike :ref:`other commenting systems <other-commenting-systems>`,
|ucomment| was developed specifically for commenting on evolving documentation.
In other words, the comments are to be integrated (directly, or modified), into
the document by the author, and then the revised document can be
published again to the web.  Comments can easily be moved to other
locations in the document, or simply removed by the author.

|ucomment| will work also with documents that are static.

|ucomment| requires the author write the document using `reStructuredText
<http://en.wikipedia.org/wiki/ReStructuredText>`_ in one or more text files.

The `Sphinx documentation generator <http://sphinx.pocoo.org/latest/>`_
is used to convert the reStructuredText to HTML output.  This allows other
powerful Sphinx enhancements to be used.  Sphinx can also be used to generate
PDF, ebook, and other output formats from your document.

A distributed version control system is used to track all revisions and comments
added to the document.  Currently only Mercurial is supported, others can
easily be added.

Finally, Django is used to store all comments, page visits, user statistics,
implement server-side search for the document, and comment administration, using
the Django admin interface.

Once the document is published to the web, visitors may comment on the document.
Comments must be approved by a site administrator (customizable), via a
single-click URL to either accept or reject the comment. Once approved,
comments will appear on the site with the next page refresh.

The Sphinx documentation generator already provides good-looking tabular output,
mathematical equations, and so forth.  But if you need further enhancements,
simply adjust the templates and cascading style sheets elements that come with
|ucomment|.

An example of |ucomment| in action is this website.  The source code for this
document is `available here
<http://hg.connectmv.com/hgweb.cgi/ucommentapp-documentation/>`_.
.. _other-commenting-systems:

Other web-based commenting systems
------------------------------------

Full credit for the idea of web-based commenting goes to various websites,
particularly `The Django Book <http://djangobook.com/>`_ which was the
strongest source of ideas for |ucomment|. That site shows comments in a
sidebar, with speech bubbles either containing a number (if there are existing
comments) or no number.  These bubbles invite the user to click on them to
view the existing comments, or add their own comment.

The site for the book called `Mercurial: The Definitive Guide
<http://hgbook.red-bean.com>`_ follows a similar idea, but uses inline
commenting.  A link appears after every paragraph, figure, source code snippet,
*etc*, that either shows "No comments" or "N comments", where N is some integer.

|ucomment| implements the type of comments as used on the Django Book website.
Inline commenting could be added to |ucomment|, but is not currently
implemented.  (I personally find inline commenting a bit distracting.)

Bullet point feature summary
-------------------------------

*	Visitors to the document website can turn comments on or off (sometimes its
	nice to just read the document, without extra visual distraction!).

*	The document can be updated and republished on the web, and the original
	comments will correctly move to the updated location.

*	Links for ``Next``, ``Previous`` and ``Table of Contents`` help the reader
	navigate the various sections of the document.

*	Comments are written in reStructuredText (allows for math, bullet points,
	tables, etc), and must be previewed by the reader before being submitted.

*	Once submitted, the comment administrator can approve or rejects new
	comments via email links; the comment submitter is informed of the decision
	by email also.

*	Email alerts are sent to the site administrator if any errors occurs.

*	The settings for comment acceptance are flexible. For example, the default
	settings will auto-approve future comments from a poster who has submitted
	3 or more approved comments in the past.

*	Any comments can always be removed from the document's web output by
	marking a checkbox in the Django admin site, or by deleting the comment
	from the Django database.

*	An option exists so that long tables of contents are can be shrunk and
	expanded using Javascript.  See the TOC for this website as an example.

*	When the user navigates back to the table of contents they are shown the
	page they came from; to help navigate large documents.

*	Support for mathematics and comments on equations: MathJax and ``pngmath``
	(a Sphinx extension) have been tested.

*	Simple, full text search of the document is available; a feature request
	is that other 3rd party search plugins can be used instead.

*	Search is accessible via a URL:

	``http://example.com/docs/-search/search Term/AND/case=False``

	will perform a case-insensitive search for the word ``search`` and
	``Term``. The ``AND`` can be replaced with ``OR``.

*	A customizable template is provided so that you can render the page within
	your existing website and surround the document content with other content.
	Templated items include:

		* The main content area

		* Sidebar containing the search box and the local ToC

		* Page navigation elements

		* Emails sent to users and the site administrators

*	Basic tracking of page hits (visits) and page popularity can be followed in
	the Django admin interface. (see code in the application's ``admin.py``
	file to modify the admin interface).

*	A server setting exists to stop all commenting on the document, and to
	not display any existing comments.

*	*Experimental*: long chapters or sections in the document can be optionally
	split into smaller subsections that each appear on their own HTML page.

	For now, if you wish to split up a long document you must write the section
	in separate RST files.  The experimental features allows you to edit inside
	single RST files, but then automatically splits them up.

Installation
============

|ucomment| is not a standalone application.  It requires several other pieces
of software to work.

Dependencies
------------

|ucomment| must run on a web server.  The following programs are assumed to be
installed on that server:

* Python 2.6 or better (it may work with Python 2.5, but it has not been tested)
* Django 1.2.1, or better, and its dependencies (earlier versions may work also)
* Sphinx 1.1, or better, and its dependencies
* Mercurial 1.6.2, or better (earlier versions may work also)

Detailed installation instructions
-----------------------------------

1.	Create a Django project with ``django-admin.py startproject ucommentsite``
	or use an existing project.

2.	Inside the Django project, clone the latest version of the |ucomment|
	Django application:

	::

		hg clone http://bitbucket.org/kevindunn/ucommentapp

	After this step your Django project directory should like similar to:

	::

		/__init__.py
		/manage.py
		/settings.py
		/ucommentapp/   <--- subdirectory of files just cloned above
		/urls.py

3.	The next group of settings will change lines in your Django project's
	``settings.py`` file.

	*	Add the |ucomment| application to your Django project's
		``INSTALLED_APPS`` section. For example:
		::

			INSTALLED_APPS = (
				'django.contrib.auth',
				'django.contrib.contenttypes',
				....
				'ucommentapp',
				...
				)

	*	If this is a new Django project, then also edit the database settings.

	*	Ensure that you have a valid email address under the ``ADMINS``
		section.  |ucomment| will send an email to that address should
		anything go wrong with the application.

	*	The |ucomment| also requires that you set these 5 entries in the
		``settings.py`` file.  Examples are given so you can see what
		is expected.

		::

			EMAIL_HOST = 'smtp.example.com'
			EMAIL_PORT = 25
			EMAIL_HOST_USER = 'yourname'
			EMAIL_HOST_PASSWORD = 'your_password'
			EMAIL_FROM = 'Web comments <web.comments@example.net>'

	*	You should set your ``MEDIA_URL`` and ``MEDIA_ROOT`` settings to tell
		Django where your media files are served from.

4.	Cut and paste all lines from ``ucommentapp/project-urls-append.py`` into
 	the bottom of your Django project's ``urls.py`` file.  You can of course
	edit the URL where the document will be hosted.  The default setting is:

	::

		(r'^document/', include('ucommentapp.urls')),

	If you would like to host the document at ``mydoc``, then change this to:

	::

		(r'^mydoc/', include('ucommentapp.urls')),

	Then the document will be available at ``http://example.com/mydoc/``. If
	you prefer to host the documentation at the root of the website, such as
	``http://example.com/``, then use:

	::

		(r'', include('ucommentapp.urls')),

	in your Django project's ``urls.py`` file.

5.	If you changed the default settings in the previous step, then you **must**
 	also make these two changes:

	#.	In the Javascript  file, ``ucommentapp/media/ucomment.js``: look for
		the line that refers to ``URL_VIEWS_PREFIX``, and adjust it.

	#.	Also change the line in ``ucommentapp/conf/settings.py``: look for
		the line that refers to the ``url_views_prefix`` setting.

6.	Now it is time to create the database tables for this application.  Run
	the following command from the Django project directory:

	::

		manage.py syncdb


7.	Next, spend some time editing the |ucomment| settings in
	``ucommentapp/conf/settings.py``. There are several settings that you
	need to adjust to let the application know about your document and how
	you prefer users to interact with it.

	That settings file has many comments to help you along.

8.	Now you should be ready to publish your document for the first time.

	*	Your document files must be a valid `Sphinx markup
		<http://sphinx.pocoo.org/latest/rest.html>`_.

	*	You will need the Sphinx-generated ``conf.py`` file for your document,
		that have likely customized.

	*	In addition, all other files, images, and other content that make up
		your document must be available.

	*	All the materials from the 3 previous points must be under version
		control in a single repository.  If you are unfamiliar with revision
		control, please visit `this helpful site
		<http://hginit.com/index.html>`_.

	*	|ucomment| (currently) supports the Mercurial distributed version
		control system (DVCS).  We definitely want to support other	DVCS's, and
		the code is set up to allow this to be added by interested developers.

	*	The repository containing your document can be on your webserver,
		or available remotely, from another server (though this will add some
		latency to your |ucomment| site, and should be avoided).

	*	You will need to adjust your ``conf.py`` file to add a custom
		Sphinx extension for |ucomment|.  Add the following lines, near the
		top of your ``conf.py`` file, anywhere after the ``extensions = [...]``
		list.  Please **only edit the last line** shown below, all other lines
		must be included exactly as-is.

		::

			# ucomment extension
			sys.path.append(os.path.abspath(os.getcwd()))
			extensions.append('ucomment-extension')
			html_translator_class = 'ucomment-extension.ucomment_html_translator'

			# Point to your Django application, which contains all
			# the other settings required.
			ucomment = {}
			ucomment['django_application_path'] = '/path/to/Django/project/ucommentapp'

		The last line points to your installation of |ucomment|, set in step 2
		above.  Once it knows this location, it will be able to use all other
		settings you specified earlier in your ``ucommentapp/conf/settings.py``
		file.

9.	To publish your document, start your Django server, or, if you are in
	development mode: run the built-in Django development server:

	::

		manage.py runserver

10.	Visit the publish/update page for this application. The link is
	``http://example.com/document/_admin``.  Obviously you should replace
	``example.com`` with you own site address, and also replace the ``document``
	part only if you adjusted settings in step 4 and 5 above.

	Click on the link to publish/update the document.  This step calls
	Sphinx, which should be installed on your webserver, to convert
	the RST source files to HTML.

	That HTML is added to the Django database, and served to the
	website visitors from Django.

11.	On your webserver, and only after you have published the document
 	for the first time (previous step), you should go check the local
	document repository.

	Go to the location on your webserver where you have the |ucomment|
	application; e.g. ``... /my-django-project/ucommentapp/``

	You will see a new directory was created by |ucomment| called
	``document_compile_area`` - this is the webserver's clone of your
	document, and the RST files are modified slightly when users comment
	on your document.

	These changes will be pushed back to the source repository automatically.
	But if your source repo is on a remote site, or requires credentials to
	push to, then you must add settings to allow this to occur without manual
	intervention.

	For Mercurial, this simply requires that you add a few lines in the
	``ucommentapp/document_compile_area/.hg/hgrc`` file.  Something
	similar to:

		::

			[auth]

			repo.prefix = hg.example.com/mercurial
			repo.username = foo
			repo.password = bar
			repo.schemes = https

			[paths]

			default = ......

		For more details see `the Mercurial website
		<http://www.selenic.com/mercurial/hgrc.5.html#auth>`_.

		If you use a remote server for your document's source,  please
		ensure that you can get reasonable response times for pulling
		and pushing changes.

	To test if your settings are correct, make a minor change to the local RST
	document files and commit the change.  Then at the command prompt write
	write ``hg push`` and that change should be pushed back to the source repo
	without any user intervention (e.g. entering usernames and passwords).

12.	Once your document is published, it will be available at
	``http://example.com/document/contents``

	unless you used a different setting for ``master_doc`` in
	your document's ``conf.py`` file.

13.	If you HTML looks "ugly", it is because we haven't yet added the CSS
 	and Javascript styling elements. Copy, or symlink, these files to
	the ``MEDIA_ROOT`` directory you specified in your Django
	``settings.py`` file.

	::

		ucommentapp/media/ucomment.js
		ucommentapp/media/ucomment.css
		ucommentapp/media/*.png

	Feel free to adjust any of the settings in the CSS or Javascript
	files to match your sites' appearance.

14.	If are running |ucomment| at the root of your website, i.e. you adjusted
	the ``url_views_prefix`` setting in step 4 and 5; then you will also want
	to set your webserver to serve the ``favicon.ico`` and ``robots.txt`` files.
	See `the Django documentation
	<http://docs.djangoproject.com/en/1.0/howto/deployment/modwsgi/>`_ for
	details.

15.	Now your web visitors should be able to view your document, and
	comment on any paragraph, figure, source code, tables, in other
	words, every node in your document is commentable.

Some extra steps
----------------

Currently, there are a few extra steps you must take to get accurate
comments in your document related to source code listing, mathematical
equations and tables.  If your document does not include these,
then you may skip this step.

**Note**: a request has been made to the Sphinx mailing list to have
these changes made to the Sphinx source code.  For now though you
must make them manually.

You can view the `complete Mercurial changeset here
<https://bitbucket.org/kevindunn/sphinx/changeset/e8db58170475>`_.

*	``sphinx/directives/code.py``, around line 64, add the line with
	the ``+`` symbol:

	::

		         literal = nodes.literal_block(code, code)
		         literal['language'] = self.arguments[0]
		         literal['linenos'] = 'linenos' in self.options
		+        literal.line = self.lineno
		         return [literal]



*	``sphinx/directives/code.py``, around line 169, add the line with
	the ``+`` symbol:

	::

				retnode = nodes.literal_block(text, text, source=filename)
		        retnode.line = 1
		+       retnode.attributes['line_number'] = self.lineno
		        if self.options.get('language', ''):
		            retnode['language'] = self.options['language']
		        if 'linenos' in self.options:
		            retnode['linenos'] = True
		        env.note_dependency(rel_filename)

*	``sphinx/directives/other.py``, around line 239 add the line with
	the ``+`` symbol:

	::

		     def run(self):
		         node = addnodes.tabular_col_spec()
		         node['spec'] = self.arguments[0]
		+        node.line = self.lineno
		         return [node]

*	``sphinx/ext/mathbase.py``, around line 73, add the 2 lines marked with
	the ``+`` symbol:

	::

				ret = [node]
		        if node['label']:
		            tnode = nodes.target('', '', ids=['equation-' + node['label']])
		            self.state.document.note_explicit_target(tnode)
		            ret.insert(0, tnode)
		+		node.line = self.lineno
		+		node.source = self.src
		        return ret


How the comment system works
============================

.. note::

	It is highly recommended that you use the built-in Django admin interface
	to view and understand how |ucomment| works.  You can see all comments,
	document pages, people making the comments, etc.

	You will need to edit your Django **project** (not application) ``urls.py``
	and ``settings.py`` files to enable the admin interface.

Detailed comments on how |ucomment| works will be coming soon.  The notes below
here are just a rough draft of ideas that I will expand on.

*	What happens to the RST source files when a comment is added, approved, or
	rejected.

*	Why/how to update the document frequently.

*	Moving comments around the document.

*	How the Javascript code interacts with the HTML to display the comments;
	and how the Django server on the backend serves the comments.


Comment references
------------------

*	Comment references are created again when the site is republished.  To avoid
	accumulation of references in the DB, the previous references are deleted.

	However, if FRESHENV is False, then we should not delete the references.
	What this implies however, is that from time-to-time, the author should do
	a republish with a freshenv, so that unused comment references are cleaned.

Orphaned comments
-----------------

A comment is not removed from the Django database when the comment reference
is simply removed in the RST source code by the author (since the author could
have made a mistake).  Further, keeping the comment in the database allows one
to bring the comment back, or at the least, it is there for historical purposes.

But all comments must have a valid comment reference.  So if comments without

This is intended.

The removed comment reference in the RST file could be a mistake, or intentiona

However these comments

# These arise when comment references are removed from the text by the
        # author.  But, these references still have comments associated with
        # them in the database, but are not made available on any page,
        # nor do they have a valid comment reference.


Comments (more specifically, comment references) that appear in the database,
but which are not used in the document are called orphaned comments, or
orphaned comment references.

Future features
===============

*	Nodes that show source code, ending in a double-colon ``::`` cannot
	be commented on at the moment.  This is the highest priority next feature.

*	Rejecting comments is still to be handled, coupled with a web-based tool
	to send a reason along with the rejection email to the comment submitter.

*	Mostly implemented already: Update a published document using the exiting
	pickle files (i.e. faster republishing).  Still needs some testing.

*	Ability for reader to add notes to the document and resume adding/editing
	the notes when returning.

*	Allow for 3rd party search tools to be used instead of the built-in simple
	search: e.g. http://haystacksearch.org/, or Whoosh.

*	Add support for other distributed revision control systems (currently only
	Mercurial is supported).  DVCS wrappers for SVN, Bazaar and Git.

*	Real-time preview of comments while the user is typing (via AJAX).  E.g.
	see the mathoverflow.net site.

*	Comment administration interface where the comment admin can approve/reject
	accumulated comments in one go.

*	Add a Sphinx extension to enable a directive that generates Beamer slides
	inline in the RST.

*	Add inline comments as an option (e.g. see Mercurial book website).

