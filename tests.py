""" Tests for the document application. """

import os, shutil, tempfile, collections, re
from django.test import TestCase
from sphinx.util import ensuredir
from models import CommentReference
from conf import settings as conf
import views as views

if conf.repo_DVCS_type == 'hg':
    import hgwrapper as dvcs
    dvcs.executable = conf.repo_DVCS_exec
    dvcs.local_repo_physical_dir = conf.local_repo_physical_dir
    dvcs.testing = True

conf.TESTING = True

try:
    import wingdbstub
except ImportError:
    pass

# A named tuple behaves exactly link a Django object for the purpose of
# these tests; Rather use StringIO objects instead of actual files.
CommentRef = collections.namedtuple('CommentReference',
                                    'node_type line_number comment_root')

class CompileTests(TestCase):
    """ Use a document that has all the properties we would like to test.
    Compile that document and ensure the node tagname and line numbers are
    what we expect.
    """

    def setUp(self):
        """ Use a known testing file; write it to a temporary location for
        the test.
        """
        self.tempdir = tempfile.mkdtemp() + os.sep
        conf.local_repo_physical_dir = self.tempdir + 'local_repo'
        conf.local_repo_URL = 'file://' + conf.local_repo_physical_dir
        dvcs.local_repo_physical_dir = conf.local_repo_physical_dir
        srcdir = os.path.join(os.getcwd(), conf.app_dirname, 'testing')


        # Create the remote repository from scratch; copy files to it and
        # add and commit.
        remote_repo = self.tempdir + 'remote_repo'
        shutil.copytree(srcdir, remote_repo)
        dvcs.init(dest=remote_repo)
        conf.remote_repo_URL = 'file://' + remote_repo.replace(os.sep, '/')
        dvcs.add(remote_repo)

        f = open(remote_repo + os.sep + 'conf.py', 'r')
        lines = f.readlines()
        for idx, line in enumerate(lines):
            if line.strip().endswith('__UNIT_TESTS_WILL_REPLACE_THIS__'):
                lines[idx] = "ucomment['django_application_path'] = '%s'" %\
                     conf.application_path
                break
        f = open(remote_repo + os.sep + 'conf.py', 'w')
        f.writelines(lines)
        f.close()
        dvcs.commit(override_dir=remote_repo, message='Commit; unit testing.')

    def tearDown(self):
        """ Remove temporary files. """
        shutil.rmtree(self.tempdir)

    def test_compiling_line_numbers(self):
        """ Calls Sphinx to publish this document; writes to the database.
        """
        out = views.call_sphinx_to_publish()
        self.assertTrue(out == '')

        source_lines = collections.defaultdict(list)
        for root, dirs, files in os.walk(conf.local_repo_physical_dir):
            if root.endswith('local_repo'):
                for source_file in files:
                    if source_file.lower().endswith('rst'):
                        filename = os.path.join(root, source_file)
                        with open(filename) as f1:
                            source_lines[filename].extend(f1.readlines())

        # Now we check the line numbers that were found
        c_refs = CommentReference.objects.all()


        # SYNTAX: ['node type',
        #          line number where it appears in source file,
        #          line number where the ucomment directive should be added,
        #          'any text that should preceed the ucomment directive']
        #
        # Line numbers are 1-based, to maintain consistency with text editors

        expected = [['title', 3, 5, ''],
                    ['paragraph', 7, 12, ''],
                    ['title', 13,  15, ''],
                    ['paragraph', 17, 19, ''],
                    ['title', 22, 24, ''],
                    ['paragraph', 26, 28, ''],
                    ['title', 29, 31, ''],
                    ['paragraph', 31, 33, ''],
                    ['paragraph', 33, 35, ''],
                    ['paragraph', 35, 37, ''],
                    ['paragraph', 39, 41, ''],
                    ['paragraph', 41, 43, ''],
                    ['paragraph', 47, 49, ''],
                    ['paragraph', 51, 53, ''],
                    ['title', 54, 56, ''],
                    ['paragraph', 56, 63, ''],
                    ['literal_block', 58, 63, ''],  # First line of code
                    ['paragraph', 63, 65, ''],
                    ['literal_block', 67, 74, ''],  # First line of code
                    ['paragraph', 74],
                    ['literal_block', 76, 79, ''],  # First line of code
                    ['paragraph', 79],
                    ['literal_block', 81, 105, ''],  # See "2503:b8d79f586011"
                    ['paragraph', 105],
                    ['literal_block', 107, 109, ''],
                    ['title', 111, 113, ''],
                    ['paragraph', 113],
                    ['list_item', 115, 117, '\t \t'],
                    ['list_item', 116, 118, '\t \t'],
                    ['list_item', 117, 119, '\t \t'],
                    ['paragraph', 119],
                    ['list_item', 121, 123, ' \t'],
                    ['list_item', 122, 124, ' \t'],
                    ['list_item', 123, 125, ' \t'],
                    ['paragraph', 125],
                    ['list_item', 127, 129, ' \t'],
                    ['list_item', 129, 131, ' \t'],
                    ['list_item', 131, 133, ' \t'],
                    ['paragraph', 134],
                    ['list_item', 136, 138, '   '],
                    ['list_item', 137, 139, '   '],
                    ['list_item', 138, 141, '   '],
                    ['list_item', 140, 145, '   '],
                    ['list_item', 144, 146, '   '],
                    ['paragraph', 146, 148, ''],
                    ['list_item', 148, 150, '   '],
                    ['list_item', 150, 152, '      '],
                    ['list_item', 151, 153, '      '],
                    ['paragraph', 153, 155, ''],
                    ['paragraph', 156, 159, '  '],
                    ['paragraph', 160, 166, '  '],
                    ['paragraph', 166],
                    ['list_item', 168, 170, '\t  '],
                    ['list_item', 169, 171, '\t  '],
                    ['list_item', 170, 172, '\t  '],
                    ['paragraph', 172, 174, ''],
                    ['list_item', 174, 176, '  '],
                    ['list_item', 175, 177, '  '],
                    ['list_item', 176, 178, '  '],
                    ['title', 179, 181, ''],
                    ['literal_block', 181, 187, ''],]
        for item in expected:
            item.insert(0, conf.local_repo_physical_dir+os.sep+'chapter01.rst')

        section_2 = [['title', 2, 4, ''],
                    ['paragraph', 4, 6, ''],
                    ['paragraph', 6, 8, '    '],
                    ['list_item', 8, 10, '      '],
                    ['list_item', 10, 12, '          '],
                    ['paragraph', 12, 14, '\t'],
                    ['paragraph', 15, 17, ''],
                    ['paragraph', 17, 19, '    '],
                    ['paragraph', 19, 21, '        '],
                    ['title', 23, 25, ''],
                    ['paragraph', 25, 27, ''],
                    ['displaymath', 27, 35, ''], # See ``4c1ded2e90fb``
                    ['paragraph', 35, 37, ''],
                    ['paragraph', 65, 67, ''],
                    ['title', 83, 85, ''],
                    ['paragraph', 85, 87, ''],
                    ['image', 87, 95, ''],
                    ['paragraph', 95, 97, ''],
                    ['image', 97, 100, ''],
                    ['title', 102, 104, ''],
                    ['paragraph', 104, 106, ''],
                    ['title', 110, 112, ''],
                    # The entire sidebar is not commentable
                    # Note titles are not commentable ['paragraph', 116, 118, ],
                    ['paragraph', 118, 120, '    '],
                    ['paragraph', 122, 124, '\t'],
                    ['paragraph', 124, 126, ''],
                    ['paragraph', 128, 130, '    '],
                    ['paragraph', 130, 132, ''],
                    ['title', 133, 135, ''],
                    ['paragraph', 135, 137, ''],
                    ['paragraph', 137],
                    ['paragraph', 139],
                    ['paragraph', 141],
                    ['table', 143],
                    ]

        for item in section_2:
            item.insert(0, conf.local_repo_physical_dir+os.sep+'chapter02.rst')
        expected.extend(section_2)
        section_3 = [['title',    2, 4, ''],
                    ['paragraph', 4, 6, ''],
                    ['table',     8, 16, ''],  # Fixed in ``60c33ed1dd8d``
                    ['paragraph', 16, 18, ''],
                    ['table',     18, 26, '    '],
                    ['paragraph', 34, 36, ''],
                    ['table',     36, 49, ''],
                    ]

        for item in section_3:
            item.insert(0, conf.local_repo_physical_dir+os.sep+'chapter03.rst')
        expected.extend(section_3)

        # For the document's title.
        expected.append([conf.local_repo_physical_dir+os.sep+'contents.rst',
                         'title', 3])

        ucomment = re.compile(r'^(\s*)\.\. ucomment::\s*(.*?):\s*(.*?),')
        for idx, item in enumerate(c_refs):
            exp = expected[idx]
            self.assertEqual(item.file_name, exp[0])
            self.assertEqual(item.node_type, exp[1])
            self.assertEqual(item.line_number, exp[2])
            if len(exp)>3:
                # Use a copy of the source code to make the changes on.
                source = source_lines[item.file_name][:]
                c_root = views.update_RST_with_comment(item, 'A1', source)
                self.assertEqual(c_root, item.comment_root)
                try:
                    prefix, root, node = ucomment.match(\
                        source[exp[3]-1]).groups()
                except AttributeError:
                    print('FAILED: %s: %s' % (item.file_name, str(item)))
                    # DEBUGGING CODE
                    source = source_lines[item.file_name][:]
                    c_root = views.update_RST_with_comment(item, 'A1', source)
                    #prefix,root,node=ucomment.match(source[exp[3]-1]).groups()
                else:
                    if prefix != exp[4]:
                        # DEBUGGING CODE
                        source = source_lines[item.file_name][:]
                        _ = views.update_RST_with_comment(item, 'A1', source)

                    self.assertEqual(prefix, exp[4])
                    self.assertEqual(root, c_root)
                    self.assertEqual(node, 'A1')


class Test_DVCS(TestCase):
    def setUp(self):
        """ Use a known testing file; write it to a temporary location for
        the test.
        """
        self.tempdir = tempfile.mkdtemp()
        self.local_path = self.tempdir + os.sep + 'local' + os.sep
        self.remote_path = self.tempdir + os.sep + 'remote' + os.sep

        ensuredir(self.tempdir)
        ensuredir(self.local_path)
        ensuredir(self.remote_path)

        f = open(self.remote_path + 'index.rst', 'w')
        f.writelines(['Header\n','======\n', '\n', 'Paragraph 1\n', '\n',
                      'Paragraph 2\n', '\n', 'Paragraph 3\n'])
        f.close()

        self.local_repo = 'file://' + self.local_path
        self.remote_repo = 'file://' + self.remote_path
        dvcs.local_repo_physical_dir = self.local_path


    def tearDown(self):
        """ Remove temporary files. """
        shutil.rmtree(self.tempdir)

    def test_hg_dvcs(self):

        # Create, add and commit to the remote repo
        dvcs.init(dest=self.remote_repo)
        dvcs.add(self.remote_path, 'index.rst')
        dvcs.commit(message='First commit', override_dir=self.remote_path)

        # Verify that we cannot expect to query the source repo:
        self.assertRaises(dvcs.DVCSError, dvcs.get_revision_info, remote=True)

        # Clone the remote repo to the local repo
        r_hex = dvcs.clone_repo(source=self.remote_repo, dest=self.local_repo)
        # Redundant, but tests the code in this file
        rev0 = dvcs.check_out(rev='tip')
        self.assertEqual(rev0, r_hex)

        # Now, in the local repo, make some changes to test the commenting workflow

        # Add a comment for paragraph 2; commit
        f = open(self.local_path + 'index.rst', 'w')
        f.writelines(['Header\n','======\n', '\n', 'Paragraph 1\n', '\n',
                      'Paragraph 2\n', '\n', '.. ucomment:: aaaaaa: 11,\n', '\n'
                      'Paragraph 3\n'])
        f.close()
        rev1 = dvcs.commit_and_push_updates(message='Auto comment on para 2')

        # Check out an old revision to modify, rather than the latest revision
        hex_str = dvcs.check_out(rev=rev0)
        self.assertEqual(hex_str, rev0)
        # Note, we don't really care about the checked out file above here, but in
        # the ucomment views.py code we do actually use the checked out files.

        # Now add a comment to paragraph 3, but from the initial revision
        f = open(self.local_path + 'index.rst', 'w')
        f.writelines(['Header\n','======\n', '\n', 'Paragraph 1\n', '\n',
                      'Paragraph 2\n', '\n', 'Paragraph 3\n', '\n',
                      '.. ucomment:: bbbbbb: 22,\n'])
        f.close()
        rev2 = dvcs.commit_and_push_updates(message='Auto comment on para 3')

        # Add a comment above on the local repo, again starting from an old version.
        hex_str = dvcs.check_out(rev=rev0)
        # Now add a comment to paragraph 1
        f = open(self.local_path + 'index.rst', 'w')
        f.writelines(['Header\n','======\n', '\n', 'Paragraph 1\n', '\n',
                      '.. ucomment:: cccccc: 33,\n', '\n', 'Paragraph 2\n', '\n',
                      'Paragraph 3\n'])
        f.close()
        hex_str = dvcs.commit_and_push_updates(message='Auto comment on para 1')

        f = open(self.local_path + 'index.rst', 'r')
        lines = f.readlines()
        f.close()
        final_result = ['Header\n', '======\n', '\n', 'Paragraph 1\n',
                                 '\n', '.. ucomment:: cccccc: 33,\n', '\n',
                                 'Paragraph 2\n', '\n',
                                 '.. ucomment:: aaaaaa: 11,\n', '\n',
                                 'Paragraph 3\n', '\n',
                                 '.. ucomment:: bbbbbb: 22,\n']
        self.assertEqual(lines, final_result)


        # Now test the code in dvcs.pull_update_and_merge(...).
        # Handles the basic case when the author makes changes (they are pushed
        # to the remote repo) and they should be imported imported into the
        # local repo without requiring a merge.
        final_result.insert(3, 'A new paragraph.\n')
        final_result.insert(4, '\n')
        with open(self.remote_path + 'index.rst', 'w') as f_handle:
            f_handle.writelines(final_result)

        dvcs.commit(override_dir = self.remote_path, message='Remote update.')
        dvcs.pull_update_and_merge()

        with open(self.local_path + 'index.rst', 'r') as f_handle:
            local_lines = f_handle.readlines()
        self.assertEqual(local_lines, final_result)

class Test_RST_File_Changes(TestCase):
    """
    Snippets of RST file contents are presented and commented on.
    Ensures that the ucomment directive is added at the correct location.
    """

    # A named tuple behaves exactly link a Django object for the purpose of
    # these tests; Rather use StringIO objects instead of actual files.
    CommentRef = collections.namedtuple('CommentReference',
                                        'node_type line_number comment_root')

    # Test paragraph with no previous comments
    testP1 = ['Heading\n', '===========\n', '\n', 'This paragraph, or node.\n',
              '\n', 'Next paragraph or node.\n']
    test_ref = CommentRef('paragraph', 4, 'ABCDEF')
    c_root = views.update_RST_with_comment(test_ref, 'ab', testP1)
    outP1 = ['Heading\n', '===========\n', '\n', 'This paragraph, or node.\n',
             '\n', '.. ucomment:: ABCDEF: ab,\n', '\n',
             'Next paragraph or node.\n', '\n']
    assert(testP1 == outP1)
    assert(c_root == 'ABCDEF')

    # Test paragraph with an existing ucomment reference
    testP2 = ['Heading\n', '===========\n', '\n', 'This paragraph, or node.\n',
              '\n', '.. ucomment:: ZBCDEF: ab,\n', '\n',
              'Next paragraph or node.\n']
    test_ref = CommentRef('paragraph', 4, 'ABCDEF')
    c_root = views.update_RST_with_comment(test_ref, 'cd', testP2)
    outP2 = ['Heading\n', '===========\n', '\n', 'This paragraph, or node.\n',
             '\n', '.. ucomment:: ZBCDEF: ab, cd,\n', '\n',
             'Next paragraph or node.\n', '\n']
    assert(testP2 == outP2)
    assert(c_root == 'ZBCDEF')

    # Test paragraph with multiple lines
    testP3 = ['Heading\n', '===========\n', '\n', 'This paragraph, or node.\n',
              'Has two lines, but is one paragraph.\n', '\n',
              'Next paragraph or node.\n']
    test_ref = CommentRef('paragraph', 4, 'ABCDEF')
    c_root = views.update_RST_with_comment(test_ref, 'ef', testP3)
    outP3 = ['Heading\n', '===========\n', '\n', 'This paragraph, or node.\n',
             'Has two lines, but is one paragraph.\n', '\n',
             '.. ucomment:: ABCDEF: ef,\n', '\n',
             'Next paragraph or node.\n', '\n']
    assert(testP3 == outP3)
    assert(c_root == 'ABCDEF')

    # Bullets with spaces between each line.
    test_bullet_1 = ['Heading\n', '===========\n', '\n', '* Item one.\n',
                     '\n', '* Next item.\n', '\n', 'Paragraph of text.\n']
    test_ref = CommentRef('list_item', 4, 'BCDEFG')
    c_root = views.update_RST_with_comment(test_ref, '34', test_bullet_1)
    out_bullet_1 = ['Heading\n', '===========\n', '\n', '* Item one.\n', '\n',
                    '  .. ucomment:: BCDEFG: 34,\n', '\n', '* Next item.\n',
                    '\n', 'Paragraph of text.\n', '\n']
    assert(test_bullet_1 == out_bullet_1)
    assert(c_root == 'BCDEFG')

    # Bullets without spaces between each item, tabs after the bullet item
    test_bullet_2 = ['Heading\n', '===========\n', '\n', '*\tItem one.\n',
                     '*\tNext item.\n', '\n']
    test_ref = CommentRef('list_item', 4, 'CDEFGH')
    c_root = views.update_RST_with_comment(test_ref, '56', test_bullet_2)
    out_bullet_2 = ['Heading\n', '===========\n', '\n', '*\tItem one.\n', '\n',
                    ' \t.. ucomment:: CDEFGH: 56,\n', '\n', '*\tNext item.\n',
                    '\n']
    assert(test_bullet_2 == out_bullet_2)
    assert(c_root == 'CDEFGH')

    # Enumerated list item character, no spaces between each item
    test_bullet_3 = ['Heading\n', '===========\n', '\n', '#.\tItem one.\n',
                     '#.\tNext item.\n']
    test_ref = CommentRef('list_item', 4, 'DEFGHJ')
    c_root = views.update_RST_with_comment(test_ref, '78', test_bullet_3)
    out_bullet_3 = ['Heading\n', '===========\n', '\n', '#.\tItem one.\n',
                    '\n', '  \t.. ucomment:: DEFGHJ: 78,\n', '\n',
                    '#.\tNext item.\n', '\n']
    assert(test_bullet_3 == out_bullet_3)
    assert(c_root == 'DEFGHJ')

    # Bracketed enumerated items, no spaces between each item
    test_bullet_4 = ['Heading\n', '===========\n', '\n', '(1)\tItem one.\n',
                     '2)\tNext item.\n', '\n']
    test_ref = CommentRef('list_item', 5, 'EFGHJK')
    c_root = views.update_RST_with_comment(test_ref, '90', test_bullet_4)
    out_bullet_4 = ['Heading\n', '===========\n', '\n', '(1)\tItem one.\n',
                    '2)\tNext item.\n', '\n', '  \t.. ucomment:: EFGHJK: 90,\n',
                    '\n']
    assert(test_bullet_4 == out_bullet_4)
    assert(c_root == 'EFGHJK')

    # Indented bullet list, no spaces between each item
    test_bullet_5 = ['**Notes**\n', '\n', '\t#.\tOne.\n', '\t#.\tTwo.\n']
    test_ref = CommentRef('list_item', 3, 'FGHJKL')
    c_root = views.update_RST_with_comment(test_ref, '91', test_bullet_5)
    out_bullet_5 = ['**Notes**\n', '\n', '\t#.\tOne.\n', '\n',
                    '\t  \t.. ucomment:: FGHJKL: 91,\n', '\n',
                    '\t#.\tTwo.\n', '\n']
    assert(test_bullet_5 == out_bullet_5)
    assert(c_root == 'FGHJKL')

    # Indented bullet list, no spaces between each item, existing ucomment
    test_bullet_6 = ['**Notes**\n', '\n', '\t#.\tOne.\n', '\n',
                     '\t\t.. ucomment:: DEFGHJ: 45,\n', '\n', '\t#.\tTwo.\n']
    test_ref = CommentRef('list_item', 3, 'EGHJKL')
    c_root = views.update_RST_with_comment(test_ref, '91', test_bullet_6)
    out_bullet_6 = ['**Notes**\n', '\n', '\t#.\tOne.\n', '\n',
                    '\t\t.. ucomment:: DEFGHJ: 45, 91,\n', '\n', '\t#.\tTwo.\n',
                    '\n']
    assert(test_bullet_6 == out_bullet_6)
    assert(c_root == 'DEFGHJ')

    # Multi-line bullet
    test_bullet_7 = ['5. Enumerators are arabic numbers,\n',
                     '   single letters, or roman numerals.\n',
                     '6. List items should be sequentially.\n',]
    test_ref = CommentRef('list_item', 1, 'AHJKLM')
    c_root = views.update_RST_with_comment(test_ref, '93', test_bullet_7)
    out_bullet_7 = ['5. Enumerators are arabic numbers,\n',
                    '   single letters, or roman numerals.\n', '\n',
                    '   .. ucomment:: AHJKLM: 93,\n', '\n',
                    '6. List items should be sequentially.\n', '\n']
    assert(test_bullet_7 == out_bullet_7)
    assert(c_root == 'AHJKLM')

    # Multi-line bullet, last item, end of file
    test_bullet_8 = ['6. List items should be sequentially\n',
                     '   numbered, but need not start at 1\n',
                     '   (although not all formatters will\n',
                     '   honour the first index).\n', ]
    test_ref = CommentRef('list_item', 1, 'BHJKLM')
    c_root = views.update_RST_with_comment(test_ref, '94', test_bullet_8)
    out_bullet_8 = ['6. List items should be sequentially\n',
                    '   numbered, but need not start at 1\n',
                    '   (although not all formatters will\n',
                    '   honour the first index).\n', '\n',
                    '   .. ucomment:: BHJKLM: 94,\n', '\n']
    assert(test_bullet_8 == out_bullet_8)
    assert(c_root == 'BHJKLM')

    # Multi-line bullet with comment
    test_bullet_9 = ['6. List items should be sequentially\n',
                     '   numbered, but need not start at 1\n',
                     '   (although not all formatters will\n',
                     '   honour the first index).\n', '\n',
                     '   .. ucomment:: DUQFAD: 56\n']
    test_ref = CommentRef('list_item', 1, 'CHJKLM')
    c_root = views.update_RST_with_comment(test_ref, '99', test_bullet_9)
    out_bullet_9 = ['6. List items should be sequentially\n',
                    '   numbered, but need not start at 1\n',
                    '   (although not all formatters will\n',
                    '   honour the first index).\n', '\n',
                    '   .. ucomment:: DUQFAD: 56, 99,\n', '\n']
    assert(test_bullet_9 == out_bullet_9)
    assert(c_root == 'DUQFAD')

    # Multi-line bullet at the end of the document
    test_bullet_10 = ['5. Enumerators are arabic numbers,\n',
                      '   single letters, or roman numerals.\n',]
    test_ref = CommentRef('list_item', 1, 'THJKLM')
    c_root = views.update_RST_with_comment(test_ref, '98', test_bullet_10)
    out_bullet_10 = ['5. Enumerators are arabic numbers,\n',
                     '   single letters, or roman numerals.\n', '\n',
                     '   .. ucomment:: THJKLM: 98,\n', '\n']
    assert(test_bullet_10 == out_bullet_10)
    assert(c_root == 'THJKLM')

    # Last bullet
    test_bullet_11 = ['An unordered list:\n', '\n', '*\tA point.\n',
                      '*\tNext point.\n', '*\tSome other point.\n', '\n',
                      'Another paragraph.\n', '\n']
    test_ref = CommentRef('list_item', 5, 'HJKLMP')
    c_root = views.update_RST_with_comment(test_ref, '97', test_bullet_11)
    out_bullet_11 = ['An unordered list:\n', '\n', '*\tA point.\n',
                     '*\tNext point.\n', '*\tSome other point.\n', '\n',
                     ' \t.. ucomment:: HJKLMP: 97,\n',
                     '\n', 'Another paragraph.\n', '\n']
    assert(test_bullet_11 == out_bullet_11)
    assert(c_root == 'HJKLMP')

    # Hierarchical bullet list: commenting on "Two"
    test_bullet_12 = ['**Notes**\n', '\n', '\t#.\tOne.\n','\t#.\tTwo.\n',
                      '\n', '\t\t+\tSub-two-A.\n','\t\t+\tSub-two-B.\n']
    test_ref = CommentRef('list_item', 4, 'THJKLM')
    c_root = views.update_RST_with_comment(test_ref, '87', test_bullet_12)
    out_bullet_12 = ['**Notes**\n', '\n', '\t#.\tOne.\n','\t#.\tTwo.\n', '\n',
                     '\t  \t.. ucomment:: THJKLM: 87,\n', '\n',
                     '\t\t+\tSub-two-A.\n', '\t\t+\tSub-two-B.\n',
                     '\n']
    assert(test_bullet_12 == out_bullet_12)
    assert(c_root == 'THJKLM')

    # Hierarchical bullet list: commenting on "Sub-two-A"
    test_bullet_13 = ['**Notes**\n', '\n', '\t#.\tOne.\n','\t#.\tTwo.\n',
                      '\n', '\t\t+\tSub-two-A.\n','\t\t+\tSub-two-B.\n']
    test_ref = CommentRef('list_item', 6, 'GHJKLM')
    c_root = views.update_RST_with_comment(test_ref, '92', test_bullet_13)
    out_bullet_13 = ['**Notes**\n', '\n', '\t#.\tOne.\n','\t#.\tTwo.\n',
                     '\n', '\t\t+\tSub-two-A.\n', '\n',
                     '\t\t \t.. ucomment:: GHJKLM: 92,\n', '\n',
                     '\t\t+\tSub-two-B.\n', '\n']
    assert(test_bullet_13 == out_bullet_13)
    assert(c_root == 'GHJKLM')

    # Bullet points, where bullet is a compound element

    test_bullet_14 = ['Some text.\n', '\n', '*\tParagraph one.\n','\n',
                      '\tParagraph two of bullet one.\n', '\n',
                      '*\tParagraph one of bullet two.\n']
    test_ref = CommentRef('paragraph', 5, 'KLPMQD')
    c_root = views.update_RST_with_comment(test_ref, '9a', test_bullet_14)
    out_bullet_14 = ['Some text.\n', '\n', '*\tParagraph one.\n','\n',
                     '\tParagraph two of bullet one.\n', '\n',
                     '\t.. ucomment:: KLPMQD: 9a,\n', '\n',
                     '*\tParagraph one of bullet two.\n', '\n']
    assert(test_bullet_14 == out_bullet_14)
    assert(c_root == 'KLPMQD')




    # TODO(KGD): attempt to comment on both paragraph 1 and 2 in the bullet
    #
    # 1.    Paragraph one of the bullet point.
    #
    #       Paragraph two follow.

    # Math block: at left edge; no previous comment
    test_math_1 = ['Heading\n', '========\n', '\n', 'Paragraph of text.\n',
                   '\n', '.. math::\n', '\ta &= b + c\n', '\n', 'More text.\n']
    test_ref = CommentRef('displaymath', 6, 'HJKLMN')
    c_root = views.update_RST_with_comment(test_ref, '93', test_math_1)
    out_math_1 = ['Heading\n', '========\n', '\n', 'Paragraph of text.\n',
                  '\n', '.. math::\n', '\ta &= b + c\n', '\n',
                  '.. ucomment:: HJKLMN: 93,\n', '\n', 'More text.\n', '\n']
    assert(test_math_1 == out_math_1)
    assert(c_root == 'HJKLMN')

    # Math block, at left edge, with a previous comment
    test_math_2 = ['Heading\n', '========\n', '\n', 'Paragraph of text.\n',
                   '\n', '.. math::\n', '\ta &= b + c\n', '\n',
                   '.. ucomment:: HJKLMN: 93,\n', '\n', 'More text.\n']
    test_ref = CommentRef('displaymath', 6, 'HJKLMN')
    c_root = views.update_RST_with_comment(test_ref, '94', test_math_2)
    out_math_2 = ['Heading\n', '========\n', '\n', 'Paragraph of text.\n',
                  '\n', '.. math::\n', '\ta &= b + c\n', '\n',
                  '.. ucomment:: HJKLMN: 93, 94,\n', '\n', 'More text.\n', '\n']
    assert(test_math_2 == out_math_2)
    assert(c_root == 'HJKLMN')

    # Math block: indented
    test_math_3 = ['Heading\n', '========\n', '\n', '#.\tPoint one.\n',
                   '\n', '\t.. math::\n', '\t\ta &= b + c\n']
    test_ref = CommentRef('displaymath', 6, 'JKLMNP')
    c_root = views.update_RST_with_comment(test_ref, '94', test_math_3)
    out_math_3 = ['Heading\n', '========\n', '\n', '#.\tPoint one.\n',
                  '\n', '\t.. math::\n', '\t\ta &= b + c\n', '\n',
                  '\t.. ucomment:: JKLMNP: 94,\n', '\n']
    assert(test_math_3 == out_math_3)
    assert(c_root == 'JKLMNP')

    # Math block: with spaces in environment
    test_math_4 = ['Heading\n', '========\n', '\n', '#.\tPoint one.\n',
                   '\n', '\t.. math::\n', '\n', '\t\ta &= b + c\\\\\n', '\n',
                   '\t\td &= d + e\n']
    test_ref = CommentRef('displaymath', 6, 'JKLMNP')
    c_root = views.update_RST_with_comment(test_ref, '90', test_math_4)
    out_math_4 = ['Heading\n', '========\n', '\n', '#.\tPoint one.\n',
                  '\n', '\t.. math::\n', '\n', '\t\ta &= b + c\\\\\n', '\n',
                  '\t\td &= d + e\n', '\n',
                  '\t.. ucomment:: JKLMNP: 90,\n', '\n']
    assert(test_math_4 == out_math_4)
    assert(c_root == 'JKLMNP')

    # Math block: with spaces in environment
    test_math_5 = ['Heading\n', '========\n', '\n', '#.\tPoint one.\n',
                   '\n', '\t.. math::\n', '\n', '\t\ta &= b + c\\\\\n', '\n',
                   '\t\td &= d + e\n', '\n', '#. Point two.\n']
    test_ref = CommentRef('displaymath', 6, 'AKLMNP')
    c_root = views.update_RST_with_comment(test_ref, '90', test_math_5)
    out_math_5 = ['Heading\n', '========\n', '\n', '#.\tPoint one.\n',
                  '\n', '\t.. math::\n', '\n', '\t\ta &= b + c\\\\\n', '\n',
                  '\t\td &= d + e\n', '\n', '\t.. ucomment:: AKLMNP: 90,\n',
                  '\n', '#. Point two.\n', '\n']
    assert(test_math_5 == out_math_5)
    assert(c_root == 'AKLMNP')

    # Math block: with spaces in environment and a previous ucomment directive
    test_math_6 = ['Heading\n', '========\n', '\n', '#.\tPoint one.\n',
                   '\n', '\t.. math::\n', '\n', '\t\ta &= b + c\\\\\n', '\n',
                   '\t\td &= d + e\n', '\n', '\t.. ucomment:: BKLMNP: a2\n',
                   '#. Point two.\n']
    test_ref = CommentRef('displaymath', 6, 'ZYLMNP')
    c_root = views.update_RST_with_comment(test_ref, '90', test_math_6)
    out_math_6 = ['Heading\n', '========\n', '\n', '#.\tPoint one.\n',
                  '\n', '\t.. math::\n', '\n', '\t\ta &= b + c\\\\\n', '\n',
                  '\t\td &= d + e\n', '\n', '\t.. ucomment:: BKLMNP: a2, 90,\n',
                  '#. Point two.\n', '\n']
    assert(test_math_6 == out_math_6)
    assert(c_root == 'BKLMNP')

    # Math block: with spaces in environment and a previous ucomment directive
    test_math_7 = ['Indented environment', '\n', '  .. math::\n', '\n',
                   '    a &= b + c\\\\\n', '\n', '    d &= f + e\n', '\n',
                   '  .. ucomment:: CKLMNP: a3\n']
    test_ref = CommentRef('displaymath', 3, 'ABCDEF')
    c_root = views.update_RST_with_comment(test_ref, '96', test_math_7)
    out_math_7 = ['Indented environment', '\n', '  .. math::\n', '\n',
                  '    a &= b + c\\\\\n', '\n', '    d &= f + e\n', '\n',
                  '  .. ucomment:: CKLMNP: a3, 96,\n', '\n']
    assert(test_math_7 == out_math_7)
    assert(c_root == 'CKLMNP')


    # Source code: at left edge
    test_code_1 = ['Paragraph of text.\n', '\n', '.. code-block:: s\n', '\n',
                   '\tsum_function <- function(x,y)\n', '\t{\n',
                   '\t\treturn(x+y)\n','\t}\n']
    test_ref = CommentRef('literal_block', 3, 'KLMNPQ')
    c_root = views.update_RST_with_comment(test_ref, '95', test_code_1)
    out_code_1 = ['Paragraph of text.\n', '\n', '.. code-block:: s\n', '\n',
                  '\tsum_function <- function(x,y)\n', '\t{\n',
                  '\t\treturn(x+y)\n','\t}\n', '\n',
                  '.. ucomment:: KLMNPQ: 95,\n', '\n']
    assert(test_code_1 == out_code_1)
    assert(c_root == 'KLMNPQ')

    # Source code: indented
    test_code_2 = ['Similarly, the covariance is calculated as:\n', '\n',
                   '\t.. code-block:: text\n', '\n',
                   '\t\t> p.centered <- p - mean(p)\n',
                   '\t\t> h.centered <- h - mean(h)\n',
                   '\t\t> product <- h.centered * p.centered\n',
                   '\t\t> mean(product)\n', '\n', 'Another paragraph.\n']
    test_ref = CommentRef('literal_block', 3, 'LMNPQR')
    c_root = views.update_RST_with_comment(test_ref, '96', test_code_2)
    out_code_2 = ['Similarly, the covariance is calculated as:\n', '\n',
                  '\t.. code-block:: text\n', '\n',
                  '\t\t> p.centered <- p - mean(p)\n',
                  '\t\t> h.centered <- h - mean(h)\n',
                  '\t\t> product <- h.centered * p.centered\n',
                  '\t\t> mean(product)\n', '\n',
                  '\t.. ucomment:: LMNPQR: 96,\n', '\n',
                  'Another paragraph.\n', '\n']
    assert(test_code_2 == out_code_2)
    assert(c_root == 'LMNPQR')

    # Source code: line number too low
    test_code_3 = ['Paragraph of text.\n', '\n', '.. code-block:: s\n', '\n',
                   '\tsum_function <- function(x,y)\n', '\t{\n',
                   '\t\treturn(x+y)\n','\t}\n', '\n', '\n', 'Next line.\n']
    test_ref = CommentRef('literal_block', 3, 'MNPQRS')
    c_root = views.update_RST_with_comment(test_ref, '96', test_code_3)
    out_code_3 = ['Paragraph of text.\n', '\n', '.. code-block:: s\n', '\n',
                  '\tsum_function <- function(x,y)\n', '\t{\n',
                  '\t\treturn(x+y)\n','\t}\n', '\n',
                  '.. ucomment:: MNPQRS: 96,\n', '\n', '\n', 'Next line.\n',
                  '\n']
    assert(test_code_3 == out_code_3)
    assert(c_root == 'MNPQRS')

    # Source code: with existing comment
    test_code_4 = ['Paragraph of text.\n', '\n', '\t.. code-block:: s\n', '\n',
                   '\t\tsum_function <- function(x,y)\n', '\t\t{\n',
                   '\t\t\treturn(x+y)\n','\t\t}\n', '\n', '\n',
                   '\t.. ucomment:: QRSTUV: ab,\n']
    test_ref = CommentRef('literal_block', 3, 'MNPQRS')
    c_root = views.update_RST_with_comment(test_ref, '99', test_code_4)
    out_code_4 = ['Paragraph of text.\n', '\n', '\t.. code-block:: s\n', '\n',
                  '\t\tsum_function <- function(x,y)\n', '\t\t{\n',
                  '\t\t\treturn(x+y)\n','\t\t}\n', '\n', '\n',
                  '\t.. ucomment:: QRSTUV: ab, 99,\n', '\n']
    assert(test_code_4 == out_code_4)
    assert(c_root == 'QRSTUV')

    # Source code with double colons, spaces
    test_code_5 = ['A source code example::\n', '\n',
                   '    from os import path, getcwd\n', '\n',
                   '    print(path.exists(getcwd())\n']
    test_ref = CommentRef('literal_block', 3, 'PNPQRS')
    c_root = views.update_RST_with_comment(test_ref, '99', test_code_5)
    out_code_5 = ['A source code example::\n', '\n',
                  '    from os import path, getcwd\n', '\n',
                  '    print(path.exists(getcwd())\n', '\n',
                  '.. ucomment:: PNPQRS: 99,\n', '\n']
    assert(test_code_5 == out_code_5)
    assert(c_root == 'PNPQRS')

    # TODO(KGD): Table comments.
    test_table_1 = ['Paragraph of text.\n', '\n',
                    '.. list-table:: Frozen Delights!\n',
                    '   :widths: 15 10 30\n',
                    '   :header-rows: 1\n',
                    '\n',
                    '   * - Treat\n',
                    '     - Quantity\n',
                    '     - Description\n',
                    '   * - Albatross\n',
                    '     - 2.99\n',
                    '     - On a stick!\n',
                    '\n',
                    'Next paragraph.\n']
    test_ref = CommentRef('table', 3, 'PAANFS')
    c_root = views.update_RST_with_comment(test_ref, '92', test_table_1)
    out_table_1 = ['Paragraph of text.\n', '\n',
                   '.. list-table:: Frozen Delights!\n',
                   '   :widths: 15 10 30\n',
                   '   :header-rows: 1\n',
                   '\n',
                   '   * - Treat\n',
                   '     - Quantity\n',
                   '     - Description\n',
                   '   * - Albatross\n',
                   '     - 2.99\n',
                   '     - On a stick!\n',
                   '\n',
                   '.. ucomment:: PAANFS: 92,\n', '\n',
                   'Next paragraph.\n', '\n']
    assert(test_table_1 == out_table_1)
    assert(c_root == 'PAANFS')


    test_table_2 = ['A table:\n',
                '\n',
                '.. tabularcolumns:: |l|c|c|c|\n',
                '\n',
                '.. table::\n'
                '\n',
                '    +-----------+-------+---------------+-----------------+\n',
                '    | Experiment| Order | Header entry1 | Header entry 2  |\n',
                '    +===========+=======+===============+=================+\n',
                '    | 1         | 3     | |-|           | |-|             |\n',
                '    +-----------+-------+---------------+-----------------+\n',
                '    | 2         | 2     | |+|           | |-|             |\n',
                '    +-----------+-------+---------------+-----------------+\n',
                '    | 3         | 4     | |-|           | |+|             |\n',
                '    +-----------+-------+---------------+-----------------+\n']

    test_ref = CommentRef('table', 5, 'TABLE2')
    c_root = views.update_RST_with_comment(test_ref, '92', test_table_2)
    out_table_2 = ['A table:\n',
                '\n',
                '.. tabularcolumns:: |l|c|c|c|\n',
                '\n',
                '.. table::\n'
                '\n',
                '    +-----------+-------+---------------+-----------------+\n',
                '    | Experiment| Order | Header entry1 | Header entry 2  |\n',
                '    +===========+=======+===============+=================+\n',
                '    | 1         | 3     | |-|           | |-|             |\n',
                '    +-----------+-------+---------------+-----------------+\n',
                '    | 2         | 2     | |+|           | |-|             |\n',
                '    +-----------+-------+---------------+-----------------+\n',
                '    | 3         | 4     | |-|           | |+|             |\n',
                '    +-----------+-------+---------------+-----------------+\n',
                '\n',
                '.. ucomment:: TABLE2: 92,\n','\n']
    assert(test_table_2 == out_table_2)
    assert(c_root == 'TABLE2')



    # TODO(KGD): Figures

    # TODO(KGD): table, figures, paragraphs and math that appear in a list item?

    # TODO(KGD): handle these sort of lists
    # :Author: A.B. Curruthers
    # :Release: 23
    # :Date: 45 June 2010

    # TODO(KGD): source codes

    # TODO(KGD): bullet point ending with `::` source code

    #Here is an example::

    #from django.http import HttpResponse

        #def index(request):
        #return HttpResponse("Hello, world. You're at the poll index.")

#Or another example follows below, indented with spaces.

#::

    #Whitespace, newlines, blank lines, and
    #all kinds of markup (like *this* or
    #\this) is preserved by literal blocks.

    #The paragraph containing only '::'
    #will be omitted from the result.

#And another type of code inclusion, indented with tabs: ::

#print "More source code"
#print("I love source code")

