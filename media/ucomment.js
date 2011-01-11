//  :copyright: Copyright 2010, by Kevin Dunn
//  :license: BSD, see LICENSE file for details.

// =====================
//       SETTINGS
// =====================

// Please adjust these settings according to your requirements.

// Do you use the MathJax extension to render math with Sphinx?  If so, set
// this variable to ``true``; if you use Sphinx's pngmath extension, or have no
// mathematics in your documentation, please set it to ``false``.
var USE_MATHJAX = false;

// The same value as the ``url_views_prefix`` values in the Django application's
// "conf/settings.py" file.
var URL_VIEWS_PREFIX = 'document/';

// Turn off the expand/show accordion effect for the Table of Contents
var USE_TOC_ACCORDION = true;

// Message shown to user if a delay occurs on the server
POST_COMMENT_FAILURE  = 'A delay occurred on the server while processing your ';
POST_COMMENT_FAILURE += 'comment. Please try submitting it again.  If it still does ';
POST_COMMENT_FAILURE += 'not succeed, please contact us: "support@example.com"';

// =====================
//    End of SETTINGS
// =====================

/*
Attribution
===========

This code is heavily based on ideas from The Django Book.  Permission to use
their code was "granted" here:
http://www.mail-archive.com/sphinx-dev@googlegroups.com/msg02381.html

However, this code uses YUI3 instead of YUI2 and has a different layout.
Nevertheless, the conceptual idea is very much due to the Django Book site's source.

Minified code
=============
This file's size can be reduced by half when using minification.  I have used
YUI minifier, YUI Compressor: http://developer.yahoo.com/yui/compressor/

java -jar yuicompressor-2.4.2.jar --preserve-semi infile.js -o outfile.js


Improvements
============
JSLint shows many potential improvements (implied globals, and a few unused
variables).  I would appreciate any feedback for improvement; this is my first
major attempt at working on a Javascript file.
*/

var ucomments = function() {

YUI().use('node', 'tabview', 'event', 'dd-drag', 'dd-proxy', 'dd-scroll',
		  'io-base', 'io-form', 'event-key', 'querystring-stringify-simple',
		  'json', 'cookie',
		  function(Y) {
	// node: get and set properties on various HTML nodes
	// tabview: handles the comment dialog window (a set of 3 tabs)
    // event: for handling window resizing events
    // dd-drag: for drag-and-drop
    // dd-proxy: so that the frame of dialog box is dragged, not the box itself.
    // dd-scroll: to allow text to be selected within draggable frame
    // io-base: to allow communication with remote server
    // io-form: to submit comment form to remote server
	// event-key: to listen for a keypress in the text area
	// querystring-stringify-simple: to serialize Javascript object to string
	// json: to parse json objects returned from Django
	// cookie: to set and fetch the default settings for hiding/showing comments

// SETTINGS: these only need to be changed if you adjusted the application's "urls.py"

// The class="CLASS_NAME" that is added to commentable nodes in the HTML.  Must
// agree with the ``CLASS_NAME`` variable in the ucomment Sphinx extension.
var CLASS_NAME = 'ucomment';
// The location (last part of URL) used to preview comments (must match
// with the ``preview_comment`` function specific in Django's urls.py file)
var XHR_COMMENT_PREVIEW = URL_VIEWS_PREFIX + '_preview-comment/';
// The location (last part of URL) used to submit comments (must match with the
// ``submit_and_store_comment`` function specific in Django's urls.py file)
var XHR_COMMENT_SUBMIT = URL_VIEWS_PREFIX + '_submit-comment/';
// The location (last part of URL) used to retrieve comment counts when given
// a list of nodes for a page
var XHR_COMMENT_COUNTS = URL_VIEWS_PREFIX + '_retrieve-comment-counts/';
// The location (last part of URL) used to retrieve comment's HTML when given
// a comment root
var XHR_COMMENT_HTML = URL_VIEWS_PREFIX + '_retrieve-comments/';
// The location (last part of URL) used to search document (must match with the
// ``search_document`` function specific in Django's urls.py file)
var URL_SEARCH_DOCUMENT = URL_VIEWS_PREFIX + '_search/';


// Comment block: one block for each element that can be commented
var CommentBlock = function(el, comment_root, indicator) {
    // The actual node object (a node is any item with a class of CLASS_NAME)
    this.el = el;

    // Each CLASS_NAME node has an id, of the form "XXXXXX". The XXXXXX part is
	// a string reference to that paragraph, table, equation, or whatever that
	// ``node`` is.  The ``indicator`` part referred to here is a sibling
	// element in the HTML DOM:
	//     <span id="XXXXXX" " class="ucomment-indicator"></span>
	//
	// This ``indicator`` is used to contain the margin region displayed next
	// to each node.  The comment dialog box will popup when a user clicks in
	// the margin region.
	this.indicator = indicator;

    // Which node is this comment associated with?
    this.comment_root = comment_root;

    // The height of the paragraph/node/item: used to create a highlighter when
	// the user is commenting on it
    this.height = this.el.get('offsetHeight');

	// Seems that setting the style height is the only way to specify the height
    this.indicator.setStyle('height', this.height);
};


// Gets the CSS value for '#ucomment-border' margin-left
var COMMENT_BAR_WIDTH = parseInt(Y.one('#ucomment-border').getStyle('marginLeft'), 10);

//The URL of the XHR resource to which we're POSTing comment data to and from:
var sURI = '/';

// The horizontal bar that indicates to the user which node is being commented
var highlightFloater;

// Contains an instance of ``CommentBlock`` variable referring to the node being commented
var currentBlock;

// One and only instance of the ``CommentDialog`` class, the UI in which
// comments are written and displayed.
var commentDialog;

// A problem occurred when submitting form information.  Display an error
// to the user.
var handle_posting_failure = function(message) {
	commentDialog.showError(message);
};

// Two functions to hide or show the ucomments.
var show_ucomments = function(){
	// Q: is there a way to modify the CSS rather than the nodes?
	// If the above XHR and JSON do not complete, then we would still like
	// to show/hide the comment balloons.
	nodes = Y.all('.ucomment-indicator span');
	nodes.setStyle('display', 'block');
	Y.all('.ucomment-show-hide-ucomments').set('innerHTML', '<a href="#">Hide comments</a>');
	Y.Cookie.set("show-ucomments", "true", {path: "/"});
};
var hide_ucomments = function(){
	nodes = Y.all('.ucomment-indicator span');
	nodes.setStyle('display', 'none');
	Y.all('.ucomment-show-hide-ucomments').set('innerHTML', '<a href="#">Show comments</a>');
	Y.Cookie.set("show-ucomments", "", {path: "/"});
};

// Called once comment form posting is complete
var posting_complete = function(transactionid, response) {
	var id = transactionid;
	var data = response.responseText;

	Y.log("The 'IO-complete' handler was called.", "debug", "ucomment");
	Y.log("Id: " + transactionid, "debug", "ucomment");
	Y.log("HTTP status: " + response.status, "debug", "ucomment");
	Y.log("Status code message: " + response.statusText, "debug", "ucomment");

	submit_button = Y.one('#ucomment-submit-button');
	preview_or_edit_button = Y.one('#ucomment-preview-button');
	close_button  = Y.one('#ucomment-close-button');
	preview_block = Y.one('#ucomment-preview-box');
	preview_block.setStyle('height', Y.one('#ucomment-id_comment').get('offsetHeight'));

	// Did a timeout occur?
	if (response.status===0 && response.statusText==='timeout'){
		cfgform.timeout += 5000;
		handle_posting_failure(POST_COMMENT_FAILURE);
		return;
	}

	// The user's comment was processed
	if (response.getResponseHeader('Ucomment') == 'Preview-OK'){
		submit_button.set('disabled', false);
		preview_or_edit_button.set('disabled', true);

		// Event to listen for keypress or click in comment editing area
		var comment_changed = function(e)
		{
			submit_button.set('disabled', true);
			preview_or_edit_button.set('disabled', false);
			preview_block.set('innerHTML', '');

			// stopPropagation() and preventDefault()
			e.halt();

			// unsubscribe so this only happens once
			comment_key.detach();
			comment_click.detach();
		};

		// Attach to 'id_comment', any keydown or click will activate,
		var comment_key = Y.on('key', comment_changed, '#ucomment-id_comment', 'down:');
		var comment_click = Y.on('click', comment_changed, '#ucomment-id_comment');

		if(response.responseText !== undefined){
			preview_block.set('innerHTML', response.responseText);
			// Typeset any math that was in the comment.
			// See: http://www.mathjax.org/docs/synchronize.html
			if(USE_MATHJAX){
				MathJax.Hub.Queue(["Typeset", MathJax.Hub, "ucomment-preview-box"]);
			}
		}
	}

	// Error occurred converting comment to HTML
	else if (response.getResponseHeader('Ucomment')=='Preview-Invalid input'){
		Y.one('#ucomment-submit-button').set('disabled', true);
		handle_posting_failure(response.responseText);
	}
	else if (response.getResponseHeader('Ucomment')=='Preview-Exception'){
		Y.one('#ucomment-submit-button').set('disabled', true);
		handle_posting_failure(response.responseText);
	}
	else if (response.getResponseHeader('Ucomment')=='Submission-OK'){
		close_button.setStyle('visibility', 'visible');
		submit_button.setStyle('visibility', 'hidden');
		close_button.set('disabled', false);
		submit_button.set('disabled', true);
		preview_block.set('innerHTML', response.responseText);
		// Shows the user a message that the comment was successfully submitted.
	}
};

var close_comment_box = function(){
	currentBlock = null;
	highlightFloater.setStyle('display','none');
	commentDialog.hide_comment_dialog();
};

// Note the click event is only for the X in the top corner, but it hides the entire container.
Y.on('click', close_comment_box, '#ucomment-dialog-container .ucomment-close');

var comment_counts_complete = function(transactionid, response){
	// Parse the JSON response from Django.  For example, the response could
	// be '{"eVsYpM": 3, "QtxfuG": 1, "yA2fmq", 0}' indicating the number of
	// comments associated with each node.
	Y.log("response " + response.responseText, 'debug', 'ucomment');
	Y.log("The 'IO-complete' handler for counts called.", "debug", "ucomment");
	if (response.status===0 && response.statusText=='timeout'){ return;}
	var total_count = 0;
	var reviver = function (key,val) {
		if (key !== ""){
			comment_item = blocks[mapper[key]].indicator;
			if (val > 0){
				comment_item.addClass('ucomment-has-comments');
				child_node = Y.Node.create('<span>' + val + '</span>');
				comment_item.appendChild(child_node);
				total_count += val;
			}else{
				child_node = Y.Node.create('<span></span>');
				comment_item.appendChild(child_node);
			}
		}
	};
	var counts = Y.JSON.parse(response.responseText, reviver);
	if (total_count === 0){
		Y.all('.ucomment-show-hide-ucomments').setStyle('visibility', 'hidden');
	}
	// Check if a cookie exists for the user's preference to hide/show
	// the comments.  If not, create it with a default to show comments.
	// If it does exist, read the cookie, and act on it.
	ucomments_visible = Y.Cookie.get('show-ucomments', Boolean);
	if ((ucomments_visible === null) | ucomments_visible){
		show_ucomments();
	}else{
		hide_ucomments();
	}
};

// Create tabbed comment dialog.  Uses the HTML code inside
// <div id="comment-dialog">...</div> to determine the layout
var tabview_dialog = new Y.TabView({srcNode: '#ucomment-dialog'	});
tabview_dialog.render();

var change_tab_post_comments = function(){
	// Reset the comment GUI to a clean state
	all_buttons = Y.all('.ucomment-buttons');
	all_buttons.set('disabled', false);
	all_buttons.setStyle('visibility', 'visible');

	// Then make changes from that state
	Y.one('#ucomment-submit-button').set('disabled', true);
	Y.one('#ucomment-close-button').set('disabled', true);
	Y.one('#ucomment-close-button').setStyle('visibility', 'hidden');
	Y.one('#ucomment-preview-box').set('innerHTML', '');
	tabview_dialog.selectChild(0);
};

var change_tab_view_comments = function(){
	all_buttons = Y.all('.ucomment-buttons');
	all_buttons.set('disabled', true);
	all_buttons.setStyle('visibility', 'hidden');
	tabview_dialog.selectChild(1);
};

var change_tab_help_comments = function(){
	all_buttons = Y.all('.ucomment-buttons');
	all_buttons.set('disabled', true);
	all_buttons.setStyle('visibility', 'hidden');
	tabview_dialog.selectChild(2);
};

var make_XHR_submit_request = function() {
	form = Y.one('#ucomment-form');
	child_node = Y.Node.create('<input type="hidden" name="comment_root" value="' + currentBlock.comment_root + '">');
	form.appendChild(child_node);
	child_node = Y.Node.create('<input type="hidden" name="page_name" value="' + document.location.pathname + '">');
	form.appendChild(child_node);
	Y.log("XHR submit-comment request...");
	var request = Y.io(sURI + XHR_COMMENT_SUBMIT, cfgform);
	Y.log("XHR submit-comment request completed; Id: " + request.id + ".", "info", "example");
};

var make_XHR_preview_request = function(){
	Y.log("XHR preview-comment request...");
	var request = Y.io(sURI + XHR_COMMENT_PREVIEW, cfgform);
};

/* Settings for XHR POST form transactions */
var cfgform = {
	method:  'POST',
	form:    { id: Y.one('#ucomment-form'), useDisabled: true},
	on:      { complete: posting_complete },
	headers: { 'JS-comment-request': 'True'},
	timeout: 15000
};

var make_XHR_commment_count_request = function () {
	var cfgcounts = {
			method:  'POST',
			on:      {complete: comment_counts_complete},
			data:    comment_counts,
			timeout: 15000,
			// async is important, especially for long pages.
			sync:    false
		};
	Y.log("XHR comment_count_request...");
	var request = Y.io(sURI + XHR_COMMENT_COUNTS, cfgcounts);
};

var change_tabs = function (e){
	var tabref = e.target.get('href');
	var which_tab = tabref.substring(tabref.indexOf('#'));
	if (which_tab == '#post-comments'){change_tab_post_comments();}
	if (which_tab == '#view-comments'){change_tab_view_comments();}
	if (which_tab == '#help-comments'){change_tab_help_comments();}
	e.halt();
};

var show_hide_ucomments = function (e){
	if (e.target.get('innerHTML') == 'Hide comments'){
		hide_ucomments();
		return;
	}
	if (e.target.get('innerHTML') == 'Show comments'){
		show_ucomments();
	}
};

var onWindowResize = function(e) {
	// Does not work well in Safari4 on a Mac.
	// In particular, if you resize the window size, or zoom in or out.
	// Also, in zoomed more, the second click moves the floater to the
	// wrong location.
	highlightFloater = Y.one('#ucomment-highlight-floater');
	if (highlightFloater.getStyle('visibility')=='visible' && currentBlock)
	{
		highlightFloater.setXY([chapterWrapper.getX(), currentBlock.top]);
		highlightFloater.setStyle('height', currentBlock.el.get('offsetHeight'));
	}
};


// Comment "dialog" object: constructor
var CommentDialog = function(element) {

    this.el = Y.one(element);
	this.height = parseInt(Y.one('#ucomment-dialog-container').getStyle('height'), 10);
    this.width = parseInt(Y.one('#ucomment-dialog-container').getStyle('width'), 10);
    this.messageDiv = Y.one('#ucomment-preview-box');
    this.el.setStyle('display', 'none');

    // Make the dialog box dragabble
    this.dd = null;
    this.dd = new Y.DD.Drag({node: element}).plug(Y.Plugin.DDProxy).addHandle('#ucomment-dialog-header').plug(Y.Plugin.DDWinScroll);

    // Refresh various screen elements when dragging is finished
    this.dd.on('drag:end', function(e) {
        el = Y.one('#ucomment-dialog-container');
        el.setXY(el.getXY());
        onWindowResize();
    });
};

CommentDialog.prototype = {
    restoreState : function() {
        this.el.setStyles({
            height:  this.height,
            width:   this.width
        });
    },

    // Show the comment dialog: centered across the width of the page, and
	// up and down the page (we use the fact that we can access the amount
	// by which the window has been scrolled.
    show : function(block) {
		// This means the window is centered when it is first created
		if (this.el.getXY()[0] === 0){
			x = Math.max((Y.one('#ucomment-document-container').get('winWidth') - this.width)/2, 10);
		}else{
			x = this.el.getXY()[0]
		}
		offset1 = document.documentElement.scrollTop;
		offset2 = window.pageYOffset;
		offset3 = document.body.scrollTop;
		// One of these will work, given the different browser quirks
		offset = Math.max(offset1, offset2, offset3);
		y = (Math.max(0, Y.one('#ucomment-document-container').get('winHeight') - this.height))/2 + offset;
        this.el.setStyle('display', 'block');
        this.el.setXY([x, y]);
        this.el.setStyles({
            height:  this.height,
            width:   this.width
        });
    },

    hide_comment_dialog : function() {
        this.el.setStyle('display', 'none');
    },

    showMessage : function(message, className) {
        this.messageDiv.set('innerHTML', message);
        if (className) {
            this.messageDiv.addClass(className);
        }
    },

    showError : function(message) {
        this.showMessage(message, 'error');
    }
};


var initialize = function() {

	// Change the URL for the search form
	Y.one('#ucomment-search-form').set('action', sURI + URL_SEARCH_DOCUMENT);

	// We set the left edge according to this element
	chapterWrapper = Y.one('#ucomment-content-main');

	// Highlight floating element: marks which paragraph is being commented on
	highlightFloater = Y.one('#ucomment-highlight-floater');
	highlightFloater.setStyles({
		opacity:    0.4,
		display:    'none',
		visibility: 'hidden',
		width:      chapterWrapper.get('offsetWidth') - COMMENT_BAR_WIDTH
		// The width of the text part of the web page: the "-20px" is
		// to account for the 20px margin, set in the CSS:
	});

	// Create the comment dialog box object: mainly created for its
	// convenient method accessors.  The constructor must be called with the <div>
	// container that holds the entire dialog box
	commentDialog = new CommentDialog('#ucomment-dialog-container');
	commentDialog.el.setStyle('display', 'none');
	commentDialog.restoreState();

	// Find and remember all the commentable blocks: they are any div's belonging to class == CLASS_NAME
	comment_nodes = Y.all('.'+CLASS_NAME);
	n_nodes = comment_nodes.size();
	blocks = [];  // one block for each commentable node
	mapper = {};  // mapper['abcdef'] = 2 indicates blocks[2] is associated with node 'abcdef'
	comment_counts = {};  // Like mapper, except it tracks the number of comments associated with each node
	comment_margin_X = Y.one('#ucomment-border').getXY()[0] - COMMENT_BAR_WIDTH;

	// This function gets called when the user wants to start leaving a
	// comment, or start reading existing comments.
	start_comment_on_node = function(e){
		e.preventDefault();

		// Get the node number of the node that was clicked; if
		// a <span> tag was clicked, then get its parent first
		// (the actual node), then the node name.
		// The node name is an index into the ``blocks`` array.
		if (e.target.get('children').size() === 0) {
			t = e.target.get('parentNode');
			comment_root = t.get('id').substr(1);
		}else{
			comment_root = e.target.get('id').substr(1);
		}
		currentBlock = blocks[mapper[comment_root]];

		if (currentBlock === undefined){
			return;
		}

		// Mark a given block as currently focused, by setting the
		// "highlightFloater" div element across that node.
		// You must make the node visible first before adjusting
		// the height and location of the div.
		highlightFloater.setStyles({
			visibility:  'visible',
			height:      currentBlock.height,
			display:     'block'
		});
		// Note that chapterWrapper.getX(): represents the left edge of the main page
		highlightFloater.setXY([chapterWrapper.getX(), currentBlock.el.getY()]);

		// Make the comment box visible, related to the current node
		commentDialog.show(currentBlock);

		// If that node has comments already, set the tabview focus
		// to view the existing comments, rather than the tab to
		// add a new comment.
		if (currentBlock.indicator.hasClass('ucomment-has-comments')) {
			change_tab_view_comments();
		} else {
			// Go to the comment posting page (default page)
			change_tab_post_comments();
		}

		show_comment_HTML = function(transactionid, response){
			Y.log("The 'IO-complete' handler for getting comment HTML called.", "debug", "ucomment");
			if (response.status===0 && response.statusText=='timeout'){ return;}
			Y.one('#ucomment-view-comments-list').set('innerHTML', response.responseText);
			// Typeset any math that was in the comment.
			// See: http://www.mathjax.org/docs/synchronize.html
			if(USE_MATHJAX){
				MathJax.Hub.Queue(["Typeset", MathJax.Hub, "ucomment-view-comments-list"]);
			}
		};

		// TODO: Don't request comments for nodes that don't have them.
		Y.log("XHR requesting the comment HTML...");
		var cfg_get_html = {
			method: 'POST',
			on:  {complete: show_comment_HTML},
			data: {'comment_root': comment_root, order: 'forward'},
			timeout: 15000
		};
		var request = Y.io(sURI + XHR_COMMENT_HTML, cfg_get_html);
	};

	for (var i=0; i<n_nodes; i++){
		node = comment_nodes.item(i);
		comment_root = node.get('id');
		child_node = Y.Node.create('<span id="_' + comment_root + '" class="ucomment-indicator"></span>');
		// Special case: we cannot append a <SPAN> to an image.  Remove the
		// ucomment class and place it onto the parent node.  Do it after
		// creating the ``CommentBlock`` object - so we get the correct height.
		if (node.get('nodeName') === 'IMG'){
			img_node = node;
			img_node.set('id', '');
			img_node.removeClass(CLASS_NAME);
			//child_node = img_node.removeChild(img_node.one('span'));
			parent = node.get('parentNode');
			parent.set('id', comment_root);
			parent.addClass(CLASS_NAME);
			parent.appendChild(child_node);
		}
		else{
			node.appendChild(child_node);
		}
		mapper[comment_root] = i;
		comment_counts[comment_root] = 0;
		blocks[i] = new CommentBlock(node, comment_root, child_node);
		// Force ucomment-indicator span to same position on the X-axis
		child_node.setXY([comment_margin_X, node.getXY()[1]]);
		child_node.on('click', start_comment_on_node);
	}
	// Disable the "Submit" button: users are forced to Preview first
	Y.one('#ucomment-submit-button').set('disabled', true);

	// Fetch the comment counts right at the end: use an async request
	comment_counts._page_name_ = document.location.pathname;
	make_XHR_commment_count_request();

	// Replace the main TOC with expanding subsections.  Will still
	// show the TOC correctly, even if Javascript is not enabled, since
	// the source HTML is left unaffected.
	if (USE_TOC_ACCORDION){
		first_level_items = Y.all('.ucomment-toctree-l1');
		expand_li = function(e){
			sibling = e.target.get('parentNode').one('li');
			if (sibling.getStyle('display') === 'none'){
				sibling.setStyle('display', 'block');
				e.target.set('innerHTML', '(hide)')
			}else{
				sibling.setStyle('display', 'none');
				e.target.set('innerHTML', '(expand)')
			}
		}
		if (first_level_items.size() > 0){
			parent = first_level_items.item(0).get('parentNode')
			for (var i=0; i<first_level_items.size(); i++){
				main_item = first_level_items.item(i);
				ul_children = main_item.one('ul');
				if (ul_children != null)
				{
					sub_items = main_item.removeChild(ul_children);
					has_referrer = false;
					for (var j=0; j<sub_items.get('children').size(); j++){
						if (sub_items.get('children').item(j).one('span')){
							has_referrer = true;}
					}
					main_items = parent.get('children');
					replace = '<li class="ucomment-expander"';
					if (!has_referrer){replace += 'style="display: none;"'}
					replace += '><ul>' + sub_items.get('innerHTML') + '</ul>';
					new_child = Y.Node.create(replace);
					main_item.append(new_child);

					new_node = '<a class="ucomment-toc-expander" ';
					if (has_referrer){
						new_node += 'href="#">(hide)</a>';}
					else{
						new_node += 'href="#">(expand)</a>';}
					expander = Y.Node.create(new_node);
					main_item.insert(expander, 1);
					Y.on('click', expand_li, expander);
				}
			}
		};
	};

}; // end: initialize() function

Y.log("Log file output will be displayed here.", "info", "ucomment");

// When clicking the submit button
Y.on('click', make_XHR_submit_request, '#ucomment-submit-button');

// When clicking the preview button
Y.on('click', make_XHR_preview_request, '#ucomment-preview-button');

// The "help on commenting" text that appears in the comment dialog
Y.on('click', change_tabs, '#ucomment-help-with-ucomments');

// The "add to the discussion" link in the comment dialog
Y.on('click', change_tabs, '#ucomment-post-a-new-comment');

// The "Show/hide comments" text in the HTML
Y.on('click', show_hide_ucomments, '.ucomment-show-hide-ucomments');

// Resizing behaviour
Y.on('windowresize', onWindowResize, '#ucomment-highlight-floater');

// When the user clicks on any of the tabs in the comment dialog box
Y.all('.yui3-tab').on('click', change_tabs);

// Remove the height component from any Sphinx-compiled image to preserve aspect
// ratio
Y.all('img.ucomment').setStyle('height', '')

// Everything is initialized here
Y.on('domready', initialize);
});  // End of: YUI().use(... ,  function(Y) {... });

} // End of: var ucomments = function() {...}

// If you are using MathJax, then you must add ``ucomments()`` to the MathJax
// queue.  See http://www.mathjax.org/resources/docs/?queues.html for details.
// The default conf/settings.py file has this set already.

if (!USE_MATHJAX){ ucomments(); }
